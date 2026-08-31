"""
Observability Setup
===================
Configures OpenTelemetry tracing and Prometheus metrics for the FastAPI app.
"""

import os
import logging
from fastapi import FastAPI

# Prometheus
from prometheus_client import make_asgi_app

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

logger = logging.getLogger(__name__)


def setup_observability(app: FastAPI, service_name: str = "document-ai-platform"):
    """
    Instrument the FastAPI application with metrics and tracing.
    """
    logger.info(f"Setting up observability for {service_name}")
    
    # 1. Prometheus Metrics Endpoint
    # Mount the prometheus ASGI app to expose /metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    # 2. OpenTelemetry Tracing
    # Create a resource identifying the service
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })
    
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otel_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            logger.info(f"Configured OTLP exporter pointing to {otel_endpoint}")
        except Exception as e:
            logger.error(f"Failed to configure OTLP exporter: {e}")
    else:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set. Tracing will not be exported.")
        # We could use a ConsoleSpanExporter for local dev, but it's very noisy.
        
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    logger.info("FastAPI instrumentation complete.")


# ─── Custom Prometheus Metrics ──────────────────────────────────────────────
# Recorded by utils/perf_logger.wrap_timing, which sits on every
# @workflows.activity() and on the Mistral client calls. The local
# PipelineEngine used to record them; Mistral Studio drives the pipeline now,
# so the timing wrapper is the hook point.

from prometheus_client import Counter, Histogram, Gauge

# Pipeline metrics
PIPELINE_STEP_DURATION = Histogram(
    "pipeline_step_duration_seconds",
    "Duration of each pipeline step",
    ["pipeline", "step"],
)
PIPELINE_STEP_TOTAL = Counter(
    "pipeline_step_total",
    "Total pipeline steps executed",
    ["pipeline", "step", "status"],
)
PIPELINE_RUN_DURATION = Histogram(
    "pipeline_run_duration_seconds",
    "Total duration of a full pipeline run",
    ["pipeline"],
)

# Provider metrics
PROVIDER_CALL_DURATION = Histogram(
    "provider_call_duration_seconds",
    "Provider call latency",
    ["provider_type", "provider_name"],
)
PROVIDER_CALL_TOTAL = Counter(
    "provider_call_total",
    "Total provider calls",
    ["provider_type", "provider_name", "status"],
)

# Circuit breaker
CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Current circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["provider_name"],
)

# Queue
QUEUE_DEPTH = Gauge(
    "queue_depth",
    "Current background task queue depth",
)

# Agent loop metrics
AGENT_LOOP_ITERATIONS = Histogram(
    "agent_loop_iterations",
    "Number of iterations per agent loop invocation",
    ["prompt_name"],
    buckets=[1, 2, 3, 4, 5, 7, 10],
)
AGENT_LOOP_TOOL_CALLS = Counter(
    "agent_loop_tool_calls_total",
    "Total tool calls executed by agent loops",
    ["tool_name"],
)

