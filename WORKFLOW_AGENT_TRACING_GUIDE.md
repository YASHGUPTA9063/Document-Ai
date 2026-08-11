# Complete Guide: Instrumenting Workflow Agents for Full Telemetry & Span Correlation

This guide explains how to capture, correlate, and export rich OpenTelemetry (OTel) traces for **agents running inside workflow activities** in the Mistral Observability ecosystem.

---

## 1. Structured Technical Requirements

1. **W3C Trace Context Propagation**:
   - Propagate the root workflow's `traceparent` (containing `trace_id` and `parent_span_id`) from the Temporal Workflow header into activity workers.
2. **Hierarchical Span Tree**:
   - **Root Workflow Span**: Represents the entire workflow run (`gen_ai.workflow.name`, `execution_id`).
   - **Activity Spans**: Represent each agent activity step (`gen_ai.activity.name`, `activity_id`).
   - **Agent LLM Spans**: Capture LLM calls (`model`, `prompt_tokens`, `completion_tokens`, system/user messages).
   - **Tool Execution Spans**: Capture tool calls (`gen_ai.tool.name`, arguments, return payloads).
3. **Maximum Data Enrichment**:
   - Attach metadata attributes: `workflow_execution_id`, `agent_name`, `tool_name`, `input_args`, `output_payload`, and `exception.stacktrace` on failure.

---

## 2. Telemetry Architecture

```
                          W3C traceparent (header)
               ┌──────────────────────────────────────────┐
               │ 00-23d8c10aa8e6d6a31798de6cb4a54276-... │
               └────────────────────┬─────────────────────┘
                                    │
                                    ▼
       ┌──────────────────────────────────────────────────────────┐
       │ Root Workflow Execution Span                             │
       │ trace_id: 23d8c10aa8e6d6a31798de6cb4a54276               │
       └────────────────────────────┬─────────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
   ┌─────────────────────────────┐     ┌─────────────────────────────┐
   │ Activity 1: Classifier      │     │ Activity 2: Extractor       │
   │ parent_span_id: <root_span> │     │ parent_span_id: <root_span> │
   └──────────────┬──────────────┘     └──────────────┬──────────────┘
                  │                                   │
                  ▼                                   ▼
   ┌─────────────────────────────┐     ┌─────────────────────────────┐
   │ LLM Span: mistral-small     │     │ Tool Span: extract_ocr      │
   │ prompt_tok / completion_tok │     │ args + return result        │
   └─────────────────────────────┘     └─────────────────────────────┘
```

---

## 3. Code Implementation Guide

### Step 1: Initialize Telemetry in Activity Workers

In your worker process or activity modules, initialize the Mistral Telemetry exporter:

```python
import os
import json
from mistralai.client import Mistral
from mistralai.extra.observability import configure_telemetry, get_telemetry_tracer

# Initialize Mistral Client
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

# Enable Dedicated Telemetry Exporter
configure_telemetry(client, provider="dedicated", redaction=False)

# Obtain Tracer Instance
tracer = get_telemetry_tracer(client, "workflow-agent-worker")
```

---

### Step 2: Instrument Activity Agent Functions with Rich Metadata

Wrap each activity agent execution in a span and attach all parameters for maximum visibility:

```python
def extractor_activity(workflow_execution_id: str, document_path: str, doc_type: str) -> dict:
    """
    Activity agent that extracts structured data from documents.
    """
    # Start Activity-level Span
    with tracer.start_as_current_span("extractor_activity_span") as activity_span:
        # 1. Attach Correlation Metadata
        activity_span.set_attribute("gen_ai.workflow.execution_id", workflow_execution_id)
        activity_span.set_attribute("gen_ai.activity.name", "extractor_activity")
        activity_span.set_attribute("gen_ai.agent.name", "document_extractor_agent")
        activity_span.set_attribute("document.path", document_path)
        activity_span.set_attribute("document.type", doc_type)

        try:
            # 2. Child Span: Execute Tool (e.g. OCR Tool)
            with tracer.start_as_current_span("execute_tool_ocr") as tool_span:
                tool_span.set_attribute("gen_ai.tool.name", "extract_with_ocr")
                tool_span.set_attribute("gen_ai.tool.call.arguments", json.dumps({"file_path": document_path}))
                
                # Execute actual tool logic
                ocr_text = f"Simulated OCR content for {document_path}"
                tool_span.set_attribute("gen_ai.tool.result", ocr_text)

            # 3. Child Span: LLM Completion Call
            # Standard client.chat.complete() automatically records model, tokens, and response!
            response = client.chat.complete(
                model="mistral-large-latest",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a document extraction agent. Extract JSON fields from text."
                    },
                    {
                        "role": "user",
                        "content": f"Document Type: {doc_type}\nText:\n{ocr_text}"
                    }
                ],
                response_format={"type": "json_object"}
            )

            extracted_json = response.choices[0].message.content
            
            # Record output on activity span
            activity_span.set_attribute("gen_ai.activity.result", extracted_json)
            return {"success": True, "data": json.loads(extracted_json)}

        except Exception as exc:
            # Record failure diagnostics & stack trace on activity span
            activity_span.record_exception(exc)
            activity_span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise exc
```

---

## 4. Parameter & Attribute Mapping Reference

To ensure your traces automatically map to standard OpenInference / OpenTelemetry attributes in the console, use these exact attribute keys:

| Telemetry Scope | Attribute Key | Description | Example Value |
|---|---|---|---|
| **Workflow Link** | `gen_ai.workflow.execution_id` | Execution ID of the parent workflow | `3636fed9e385...` |
| **Activity Link** | `gen_ai.activity.name` | Name of the workflow activity | `extractor_activity` |
| **Agent Identity** | `gen_ai.agent.name` | Name of the agent executing the step | `document_extractor_agent` |
| **Tool Choice** | `gen_ai.tool.name` | Name of the invoked tool | `extract_with_ocr` |
| **Tool Arguments** | `gen_ai.tool.call.arguments` | JSON string of input parameters | `{"file_path": "..."}` |
| **Tool Output** | `gen_ai.tool.result` | JSON or string return value | `{"success": true}` |
| **LLM Usage** | `gen_ai.usage.input_tokens` | Prompt tokens count (auto-captured) | `450` |
| **LLM Usage** | `gen_ai.usage.output_tokens` | Completion tokens count (auto-captured)| `120` |

---

## 5. How Correlation Works in the Console

1. **On `/workflows/$executionId`**:
   - Displays the Temporal handoff graph, activity statuses, durations, and exception stack traces.
2. **On `/traces` (`GET /api/v1/traces`)**:
   - Filter by `trace_id` or search `gen_ai.workflow.execution_id`.
   - Displays the nested flame-graph waterfall showing:
     `extractor_activity_span` → `execute_tool_ocr` → `mistral-large-latest (LLM Call)`.
   - Displays input/output token counts, system prompts, tool payloads, and model latencies.
