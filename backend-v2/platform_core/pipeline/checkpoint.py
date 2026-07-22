"""
Checkpoint Manager
==================
Persists pipeline state after each step completion so pipelines can
resume from the last checkpoint after a server crash.

Current problem (workflow.py):
    Uses Mistral Workflows SDK's Temporal Cloud for durability.
    If the server restarts, all in-flight workflows are lost.

New approach:
    State is saved to the database after each step. On restart,
    the pipeline engine queries for incomplete pipelines and resumes them.
"""

import json
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages pipeline checkpoints using the database.

    Usage:
        mgr = CheckpointManager(db_operations)
        await mgr.save(pipeline_id="doc123", step_index=2, step_name="classify", context={...})
        checkpoint = await mgr.load("doc123")
        await mgr.clear("doc123")
    """

    def __init__(self, db_operations=None):
        """
        Args:
            db_operations: Database operations module (db.operations).
                          If None, uses in-memory storage (for testing/dev).
        """
        self._db = db_operations
        self._memory_store: dict[str, dict] = {}  # Fallback for dev/testing

    async def save(
        self,
        pipeline_id: str,
        step_index: int,
        step_name: str,
        context: dict,
    ) -> None:
        """
        Save a checkpoint after a step completes successfully.

        The context dict is serialized to JSON. Non-serializable values
        (like raw_response objects) are stripped.
        """
        checkpoint = {
            "pipeline_id": pipeline_id,
            "completed_step_index": step_index,
            "completed_step_name": step_name,
            "context": self._sanitize_context(context),
            "timestamp": time.time(),
        }

        if self._db:
            # Save to database
            try:
                await self._db.save_checkpoint(
                    pipeline_id, json.dumps(checkpoint)
                )
            except Exception as e:
                logger.error(f"[Checkpoint] Failed to save to DB: {e}")
                # Fallback to memory
                self._memory_store[pipeline_id] = checkpoint
        else:
            # In-memory storage (dev mode)
            self._memory_store[pipeline_id] = checkpoint

        logger.info(
            f"[Checkpoint] Saved: pipeline={pipeline_id}, "
            f"step={step_index}:{step_name}"
        )

    async def load(self, pipeline_id: str) -> dict | None:
        """
        Load the most recent checkpoint for a pipeline.

        Returns None if no checkpoint exists.
        """
        if self._db:
            try:
                raw = await self._db.load_checkpoint(pipeline_id)
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.error(f"[Checkpoint] Failed to load from DB: {e}")

        # Try memory store
        return self._memory_store.get(pipeline_id)

    async def clear(self, pipeline_id: str) -> None:
        """Remove the checkpoint after pipeline completes successfully."""
        if self._db:
            try:
                await self._db.clear_checkpoint(pipeline_id)
            except Exception as e:
                logger.warning(f"[Checkpoint] Failed to clear from DB: {e}")

        self._memory_store.pop(pipeline_id, None)
        logger.info(f"[Checkpoint] Cleared: pipeline={pipeline_id}")

    async def list_incomplete(self) -> list[dict]:
        """
        List all pipelines that have checkpoints (i.e., incomplete).
        Used on server startup to resume interrupted pipelines.
        """
        if self._db:
            try:
                rows = await self._db.list_checkpoints()
                return [json.loads(r) for r in rows]
            except Exception as e:
                logger.error(f"[Checkpoint] Failed to list from DB: {e}")

        return list(self._memory_store.values())

    @staticmethod
    def _sanitize_context(context: dict) -> dict:
        """
        Remove non-JSON-serializable objects from the context
        before persisting. Keeps the checkpoint lean and reliable.
        """
        clean = {}
        for key, value in context.items():
            # Skip internal/non-serializable keys
            if key.startswith("_registry") or key.startswith("_engine"):
                continue
            try:
                json.dumps(value)
                clean[key] = value
            except (TypeError, ValueError):
                # Skip non-serializable values (e.g., raw_response objects)
                clean[key] = f"<non-serializable: {type(value).__name__}>"
        return clean
