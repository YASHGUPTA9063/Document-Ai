"""
Pipeline Engine
===============
Orchestrates multi-step document processing pipelines with:
    - Checkpointing (resume from last completed step after crash)
    - HITL (Human-in-the-Loop) pause/resume for review steps
    - Step isolation (each step gets a scoped context)
    - Status tracking (updates DB at each step transition)

Replaces the current Mistral Workflows SDK dependency:
    @workflows.workflow.define(name="document_processing_workflow")
    class DocumentProcessingWorkflow(workflows.InteractiveWorkflow): ...

With a vendor-agnostic pipeline:
    pipeline = PipelineEngine(registry, checkpoint_mgr)
    result = await pipeline.run("document_processing", context)
"""

import asyncio
import logging
import time
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

from opentelemetry import trace
from observability import PIPELINE_STEP_DURATION, PIPELINE_STEP_TOTAL, PIPELINE_RUN_DURATION

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


# ─── Step Definitions ────────────────────────────────────────────────────────

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"         # HITL — waiting for human input


@dataclass
class StepResult:
    """Result of a single pipeline step."""
    step_name: str
    status: StepStatus
    data: dict = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class StepDefinition:
    """Defines a single step in the pipeline."""
    name: str
    handler: Callable[..., Awaitable[dict]]
    status_label: str = ""             # e.g. "classifying", "extracting"
    required: bool = True              # If False, step is skipped on error
    condition: Callable[[dict], bool] | None = None  # Dynamic enable/disable
    timeout_seconds: int = 300


@dataclass
class PipelineDefinition:
    """Defines the full sequence of steps for a pipeline."""
    name: str
    steps: list[StepDefinition]


# ─── HITL Support ────────────────────────────────────────────────────────────

class HumanInputRequired(Exception):
    """Raised by a step when it needs human input to continue."""

    def __init__(self, reason: str, data: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.data = data or {}


class PipelineRejected(Exception):
    """Raised when the pipeline should terminate with a rejection."""

    def __init__(self, reason: str, data: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.data = data or {}


# ─── Pipeline Engine ─────────────────────────────────────────────────────────

class PipelineEngine:
    """
    Runs a pipeline of steps in sequence with checkpointing and HITL support.

    Usage:
        engine = PipelineEngine(checkpoint_mgr=checkpoint_mgr)
        pipeline = PipelineDefinition(name="document_processing", steps=[...])

        result = await engine.run(
            pipeline=pipeline,
            context={"document_id": "abc123", "file_path": "/path/to/file.pdf"},
            on_status_change=update_db_status,
        )
    """

    def __init__(self, checkpoint_mgr=None):
        self._checkpoint_mgr = checkpoint_mgr

    async def run(
        self,
        pipeline: PipelineDefinition,
        context: dict,
        on_status_change: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict:
        """
        Execute a pipeline from the beginning or resume from the last checkpoint.

        Args:
            pipeline: The pipeline definition with ordered steps.
            context: Mutable context dict shared across steps.
                     Steps read from and write to this dict.
            on_status_change: Optional callback for status updates.
                              Called as: await on_status_change(doc_id, "classifying")

        Returns:
            The final context dict with all step results accumulated.
        """
        pipeline_id = context.get("document_id", "unknown")
        logger.info(f"[Pipeline:{pipeline.name}] Starting for {pipeline_id}")
        start_time = time.monotonic()

        # Load checkpoint if available
        start_step = 0
        if self._checkpoint_mgr:
            checkpoint = await self._checkpoint_mgr.load(pipeline_id)
            if checkpoint:
                start_step = checkpoint.get("completed_step_index", 0) + 1
                # Restore context from checkpoint
                context.update(checkpoint.get("context", {}))
                logger.info(
                    f"[Pipeline:{pipeline.name}] Resuming from step {start_step} "
                    f"(checkpoint found)"
                )

        step_results: list[StepResult] = []

        for i, step in enumerate(pipeline.steps):
            # Skip already-completed steps (from checkpoint)
            if i < start_step:
                logger.info(f"[Pipeline:{pipeline.name}] Skipping step {i}: {step.name} (checkpointed)")
                continue

            # Check step condition
            if step.condition and not step.condition(context):
                logger.info(
                    f"[Pipeline:{pipeline.name}] Skipping step {step.name} "
                    f"(condition not met)"
                )
                step_results.append(
                    StepResult(step_name=step.name, status=StepStatus.SKIPPED)
                )
                continue

            # Update status
            if on_status_change and step.status_label:
                doc_id = context.get("document_id", "")
                await on_status_change(doc_id, step.status_label)

            # Execute step
            result = await self._execute_step(pipeline.name, step, context)
            step_results.append(result)

            if result.status == StepStatus.COMPLETED:
                # Merge step output into context for downstream steps
                context.update(result.data)

                # Save checkpoint
                if self._checkpoint_mgr:
                    await self._checkpoint_mgr.save(
                        pipeline_id=pipeline_id,
                        step_index=i,
                        step_name=step.name,
                        context=context,
                    )

            elif result.status == StepStatus.PAUSED:
                # HITL — save checkpoint and return partial result
                if self._checkpoint_mgr:
                    await self._checkpoint_mgr.save(
                        pipeline_id=pipeline_id,
                        step_index=i - 1,  # Re-run this step on resume
                        step_name=step.name,
                        context=context,
                    )
                context["_paused_at"] = step.name
                context["_paused_reason"] = result.data.get("reason", "")
                context["_step_results"] = [
                    {"name": r.step_name, "status": r.status.value} for r in step_results
                ]
                return context

            elif result.status == StepStatus.FAILED:
                if step.required:
                    context["_failed_at"] = step.name
                    context["_error"] = result.error
                    logger.error(
                        f"[Pipeline:{pipeline.name}] FAILED at step "
                        f"{step.name}: {result.error}"
                    )
                    return context
                else:
                    logger.warning(
                        f"[Pipeline:{pipeline.name}] Optional step {step.name} "
                        f"failed (continuing): {result.error}"
                    )

        # All steps completed
        context["_step_results"] = [
            {"name": r.step_name, "status": r.status.value} for r in step_results
        ]
        logger.info(f"[Pipeline:{pipeline.name}] Completed for {pipeline_id}")

        # Clear checkpoint
        if self._checkpoint_mgr:
            await self._checkpoint_mgr.clear(pipeline_id)

        # Record pipeline completion time
        elapsed_total = time.monotonic() - start_time
        PIPELINE_RUN_DURATION.labels(pipeline=pipeline.name).observe(elapsed_total)

        return context

    async def _execute_step(
        self, pipeline_name: str, step: StepDefinition, context: dict
    ) -> StepResult:
        """Execute a single step with timeout and error handling."""
        start = time.monotonic()
        logger.info(f"[Step:{step.name}] Starting")

        with tracer.start_as_current_span(f"pipeline.step.{step.name}") as span:
            span.set_attribute("pipeline.step.name", step.name)
            span.set_attribute("document.id", context.get("document_id", ""))
            
            try:
                result = await asyncio.wait_for(
                    step.handler(context),
                    timeout=step.timeout_seconds,
                )
                elapsed = (time.monotonic() - start)
                logger.info(f"[Step:{step.name}] Completed in {elapsed*1000:.0f}ms")
                
                PIPELINE_STEP_DURATION.labels(pipeline=pipeline_name, step=step.name).observe(elapsed)
                PIPELINE_STEP_TOTAL.labels(pipeline=pipeline_name, step=step.name, status="completed").inc()

                return StepResult(
                    step_name=step.name,
                    status=StepStatus.COMPLETED,
                    data=result or {},
                    duration_ms=elapsed * 1000,
                )

            except HumanInputRequired as e:
                elapsed = (time.monotonic() - start)
                logger.info(f"[Step:{step.name}] Paused for human input: {e.reason}")
                
                PIPELINE_STEP_DURATION.labels(pipeline=pipeline_name, step=step.name).observe(elapsed)
                PIPELINE_STEP_TOTAL.labels(pipeline=pipeline_name, step=step.name, status="paused").inc()
                span.set_attribute("pipeline.step.paused", True)
                
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.PAUSED,
                    data={"reason": e.reason, **e.data},
                    duration_ms=elapsed * 1000,
                )

            except PipelineRejected as e:
                elapsed = (time.monotonic() - start)
                logger.info(f"[Step:{step.name}] Pipeline rejected: {e.reason}")
                
                PIPELINE_STEP_DURATION.labels(pipeline=pipeline_name, step=step.name).observe(elapsed)
                PIPELINE_STEP_TOTAL.labels(pipeline=pipeline_name, step=step.name, status="rejected").inc()
                span.set_attribute("error", True)
                
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    data=e.data,
                    error=e.reason,
                    duration_ms=elapsed * 1000,
                )

            except asyncio.TimeoutError:
                elapsed = (time.monotonic() - start)
                error_msg = f"Step '{step.name}' timed out after {step.timeout_seconds}s"
                logger.error(f"[Step:{step.name}] {error_msg}")
                
                PIPELINE_STEP_DURATION.labels(pipeline=pipeline_name, step=step.name).observe(elapsed)
                PIPELINE_STEP_TOTAL.labels(pipeline=pipeline_name, step=step.name, status="timeout").inc()
                span.set_attribute("error", True)
                
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    error=error_msg,
                    duration_ms=elapsed * 1000,
                )

            except Exception as e:
                elapsed = (time.monotonic() - start)
                logger.error(f"[Step:{step.name}] Failed after {elapsed*1000:.0f}ms: {e}")
                
                PIPELINE_STEP_DURATION.labels(pipeline=pipeline_name, step=step.name).observe(elapsed)
                PIPELINE_STEP_TOTAL.labels(pipeline=pipeline_name, step=step.name, status="failed").inc()
                span.record_exception(e)
                span.set_attribute("error", True)
                
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    error=str(e),
                    duration_ms=elapsed * 1000,
                )

