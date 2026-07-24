# BACKEND V2 — Complete Technical Blueprint

> **Purpose**: This document is a full architectural specification. A senior developer or AI agent should be able to recreate Backend V2 from scratch using ONLY this document, without access to the original source code.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Layers](#2-architecture-layers)
3. [Project Structure](#3-project-structure)
4. [Configuration System](#4-configuration-system)
5. [Application Entry Point & Lifecycle](#5-application-entry-point--lifecycle)
6. [Database Layer](#6-database-layer)
7. [Provider System (platform_core)](#7-provider-system-platform_core)
8. [Resilience Layer](#8-resilience-layer)
9. [Pipeline Orchestration Engine](#9-pipeline-orchestration-engine)
10. [Agent Loop (LLM Conversation Engine)](#10-agent-loop-llm-conversation-engine)
11. [Prompt Management](#11-prompt-management)
12. [Step Isolation & Sandboxing](#12-step-isolation--sandboxing)
13. [Document Processing Pipeline (Steps 1–7)](#13-document-processing-pipeline-steps-17)
14. [Claim Processing Pipeline (Steps 1–7)](#14-claim-processing-pipeline-steps-17)
15. [Activities Layer (Business Logic)](#15-activities-layer-business-logic)
16. [Tools Layer (LLM Function Calling)](#16-tools-layer-llm-function-calling)
17. [Utilities Layer](#17-utilities-layer)
18. [API Layer (FastAPI Routers)](#18-api-layer-fastapi-routers)
19. [Background Worker (arq + Redis)](#19-background-worker-arq--redis)
20. [Observability & Metrics](#20-observability--metrics)
21. [Deployment & Docker](#21-deployment--docker)
22. [Data Flow Diagrams](#22-data-flow-diagrams)
23. [Hidden Assumptions & Design Decisions](#23-hidden-assumptions--design-decisions)
24. [Environment Variables Reference](#24-environment-variables-reference)
25. [Dependencies & Requirements](#25-dependencies--requirements)

---

## 1. System Overview

### What It Is

Backend V2 is an **AI-powered document processing and insurance claim adjudication platform**. It ingests documents (PDFs, images, DOCX), runs them through a multi-step AI pipeline (OCR → Classification → Extraction → Validation → Review → Output), and optionally links those documents to insurance claims that are evaluated by a 5-agent AI jury.

### Why It Exists

The platform replaces manual document processing and claim review workflows. It automates:

1. **Document Intelligence**: Upload a scan → get structured, validated, normalized data out.
2. **Insurance Claim Processing**: Upload claim documents → get a PASS/FAIL/REVIEW recommendation with per-agent reasoning.

### Core Design Philosophy

| Principle | Implementation |
|---|---|
| **Provider Agnostic** | All AI calls go through abstract interfaces (`LLMProvider`, `OCRProvider`, etc.). Swap Mistral for OpenAI with a YAML change. |
| **Dual Execution Engine** | Document pipelines run on either Mistral's managed cloud (Temporal-as-a-Service) OR a local `PipelineEngine` with checkpointing. |
| **Resilient** | Circuit breakers, fallback chains, retry with exponential backoff, and health monitoring protect every provider call. |
| **LLM-as-Orchestrator** | Every pipeline step is an "agent": an LLM with a system prompt, tools, and a conversation loop. Even simple steps like duplicate detection use an LLM to interpret tool results. |

### Tech Stack

| Layer | Technology |
|---|---|
| HTTP Framework | FastAPI (Python 3.12) |
| Database | SQLite (aiosqlite) with SQLAlchemy async ORM |
| Background Tasks | arq (Redis-based async task queue) |
| AI Provider | Mistral AI SDK (`mistralai`) — LLM, OCR, Vision |
| Embedding Model | Facebook DINOv2 (`facebook/dinov2-small` via HuggingFace `transformers`) |
| Image Processing | OpenCV (`cv2`), Pillow, PyMuPDF (`fitz`), scikit-image |
| Observability | Prometheus (metrics), OpenTelemetry (tracing) |
| Containerization | Docker + docker-compose (Postgres, Redis, App, Worker) |
| Workflow Engine (optional) | Mistral Workflows SDK (Temporal-as-a-Service) |

---

## 2. Architecture Layers

The system uses a strict 4-layer architecture. Dependencies flow **downward only**.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         LAYER 4: API                                 │
│  FastAPI routers (documents, claims, settings, workflow)              │
│  Pydantic request/response schemas                                   │
│  Redis task enqueue                                                  │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────┐
│                  LAYER 3: PIPELINE ORCHESTRATION                     │
│  PipelineEngine (local) OR Mistral Workflows SDK (cloud)             │
│  Step definitions, checkpoint manager, HITL support                  │
│  Background worker (arq) dispatches pipeline tasks                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────┐
│                  LAYER 2: ACTIVITIES (Business Logic)                 │
│  16 activity files — each wraps an LLM agent conversation            │
│  Agent Loop: send prompt → get tool calls → execute → loop           │
│  Tools: data fetchers that the LLM invokes during reasoning          │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────┐
│                  LAYER 1: PLATFORM CORE                              │
│  Provider Registry (singleton) — manages all AI providers            │
│  Abstract interfaces: LLMProvider, OCRProvider, VisionProvider, etc. │
│  Concrete implementations: MistralLLM, MistralOCR, DINOv2, etc.     │
│  Resilience: CircuitBreaker, FallbackChain, RetryPolicy              │
│  Config loader, Prompt Manager, Health Monitor                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
backend-v2/
├── main.py                          # FastAPI app entry point + lifespan
├── config.py                        # Pydantic settings (env vars)
├── worker.py                        # arq background worker
├── observability.py                 # Prometheus metrics + OpenTelemetry tracing
├── logging_config.py                # Structured JSON logging setup
│
├── config/
│   └── platform.yaml                # Master YAML config (providers, pipelines, CORS, etc.)
│
├── api/
│   ├── queue.py                     # Redis pool + task enqueue helper
│   └── routers/v1/
│       ├── __init__.py              # Mounts all v1 sub-routers under /api/v1
│       ├── documents.py             # Document upload/status/HITL endpoints
│       ├── claims.py                # Claim CRUD, document linking, processing trigger
│       ├── settings.py              # Normalization config CRUD
│       └── workflow.py              # Workflow status query (Mistral cloud)
│
├── db/
│   ├── database.py                  # SQLAlchemy async engine + session factory
│   ├── models.py                    # 9 ORM models (Document, Claim, ExtractedData, etc.)
│   ├── operations.py                # Document CRUD, checkpoint ops
│   └── claim_operations.py          # Claim CRUD, tool data fetchers, report ops
│
├── platform_core/
│   ├── __init__.py
│   ├── config.py                    # YAML config loader with ${ENV_VAR} resolution
│   ├── registry.py                  # ProviderRegistry singleton (factory from config)
│   ├── agent_loop.py                # Reusable LLM conversation loop
│   │
│   ├── providers/
│   │   ├── interfaces.py            # Abstract base classes (LLMProvider, OCRProvider, etc.)
│   │   ├── llm/
│   │   │   └── mistral.py           # MistralLLM (chat completions via SDK)
│   │   ├── ocr/
│   │   │   └── mistral_ocr.py       # MistralOCR (document text extraction)
│   │   ├── vision/
│   │   │   └── mistral_vision.py    # MistralVision (pixtral image analysis)
│   │   ├── embedding/
│   │   │   └── dinov2.py            # DINOv2Embedding (signature/face comparison)
│   │   └── storage/
│   │       └── local.py             # LocalStorage (file system)
│   │
│   ├── pipeline/
│   │   ├── engine.py                # PipelineEngine (local step orchestrator)
│   │   ├── definitions.py           # Pipeline step definitions (document + claim)
│   │   ├── checkpoint.py            # CheckpointManager (crash recovery)
│   │   └── mistral_workflow.py      # Mistral Workflows SDK integration
│   │
│   ├── resilience/
│   │   ├── circuit_breaker.py       # CircuitBreaker (CLOSED → OPEN → HALF_OPEN)
│   │   ├── fallback.py              # FallbackChain (try providers in order)
│   │   ├── retry.py                 # RetryPolicy (exponential backoff + jitter)
│   │   └── health.py                # HealthMonitor (background provider checks)
│   │
│   ├── prompts/
│   │   ├── manager.py               # PromptManager (loads .md files as system prompts)
│   │   ├── classifier.md            # System prompt for document classification
│   │   ├── extractor.md             # System prompt for data extraction
│   │   ├── validator.md             # System prompt for data validation
│   │   ├── reviewer.md              # System prompt for review decisions
│   │   ├── output.md                # System prompt for output persistence
│   │   ├── intake.md                # System prompt for duplicate detection
│   │   ├── pre_validator.md         # System prompt for quality checks
│   │   ├── preprocessor.md          # System prompt for image enhancement
│   │   ├── fraud_checker.md         # System prompt for fraud analysis
│   │   ├── auto_verifier.md         # System prompt for signature/face verification
│   │   ├── claim_integrity.md       # System prompt for claim integrity checks
│   │   ├── claim_medical.md         # System prompt for medical validation
│   │   ├── claim_treatment.md       # System prompt for treatment validation
│   │   ├── claim_disability.md      # System prompt for disability validation
│   │   ├── claim_litigation.md      # System prompt for litigation detection
│   │   └── claim_report.md          # System prompt for final claim report
│   │
│   └── isolation/
│       └── sandbox.py               # ScopedProviderRegistry + StepSandbox
│
├── activities/                      # Business logic (one file per pipeline step)
│   ├── intake.py                    # Step 1: Duplicate detection
│   ├── pre_validator.py             # Step 2: Quality pre-validation
│   ├── preprocessor.py              # Step 2.5: Image enhancement
│   ├── classifier.py                # Step 3: Document classification
│   ├── fraud_checker.py             # Step 3.5: Fraud check (KYC only)
│   ├── extractor.py                 # Step 4: Data extraction (OCR + LLM)
│   ├── validator.py                 # Step 5: Data validation
│   ├── auto_verifier.py             # Step 5.5: Signature/face verification (KYC only)
│   ├── reviewer.py                  # Step 6: Review decision
│   ├── output.py                    # Step 7: Final output persistence
│   ├── claim_integrity.py           # Claim Agent 1: Integrity
│   ├── claim_medical.py             # Claim Agent 2: Medical
│   ├── claim_treatment.py           # Claim Agent 3: Treatment
│   ├── claim_disability.py          # Claim Agent 4: Disability
│   └── claim_litigation.py          # Claim Agent 5: Litigation
│
├── tools/                           # LLM-callable tool schemas + implementations
│   ├── classifier.py                # get_supported_document_types, get_document_text
│   ├── extractor.py                 # extract_text_from_document, crop_kyc_images
│   ├── validator.py                 # get_template_fields
│   ├── reviewer.py                  # get_review_context
│   ├── output.py                    # persist_final_extraction
│   ├── intake.py                    # check_document_duplicates
│   ├── pre_validator.py             # get_file_metadata
│   ├── preprocessor.py              # enhance_document_image
│   ├── fraud_checker.py             # run_identity_proofing
│   ├── auto_verifier.py             # find_customer_reference, verify_signature, verify_face
│   └── claim_tools.py               # 3 shared claim tools + dispatcher
│
├── schemas/
│   ├── documents.py                 # Pydantic models for document API
│   └── claims.py                    # Pydantic models for claim API
│
├── utils/
│   ├── file_handler.py              # save_file, get_file_as_base64, delete_file
│   ├── ocr.py                       # extract_with_ocr (calls ProviderRegistry OCR)
│   ├── preprocessor.py              # Image preprocessing (CLAHE, skew, noise, resolution)
│   ├── norm_config.py               # Normalization rules (dates, numbers, names)
│   └── signature_verifier.py        # (Legacy) DINOv2 verifier + Mistral vision judge
│
├── Dockerfile                       # Python 3.12-slim, pip install, uvicorn
├── docker-compose.yml               # Postgres, Redis, App, Worker
├── requirements.txt                 # Python dependencies
└── .env                             # Secrets (MISTRAL_API_KEY, AGENT_IDs, etc.)
```

---

## 4. Configuration System

### Two Config Sources

The system loads configuration from TWO independent sources that serve different purposes:

#### Source 1: `config.py` → `settings` (Environment Variables)

**File**: `config.py`  
**Purpose**: Pydantic `BaseSettings` that reads from `.env`. Contains secrets, API keys, and legacy Agent IDs.

```python
class Settings(BaseSettings):
    # Core
    MISTRAL_API_KEY: str                    # Required — AI provider key
    STORAGE_DIR: str = "./storage"          # Where uploaded files are saved
    DATABASE_URL: str = "sqlite+aiosqlite:///./doc_workflow.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Mistral Workflows
    DEPLOYMENT_NAME: str = "document-ai-pipeline"  # Worker group name
    MISTRAL_WORKFLOW_ID: str = ""                  # Workflow ID from Mistral Studio
    
    # Legacy Agent IDs (16 total — one per pipeline step)
    # These are Mistral Studio-configured agents. In V2, they are being replaced
    # by local system prompts via PromptManager, but the env vars still exist
    # for backward compatibility.
    CLASSIFIER_AGENT_ID: str
    VALIDATOR_AGENT_ID: str
    REVIEWER_AGENT_ID: str
    SIGNATURE_VISION_AGENT_ID: str
    SIGNATURE_JUDGE_AGENT_ID: str
    # ... (14 more Agent IDs)
    
    # Google Document AI (fraud detection)
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    DOCUMENTAI_PROJECT_ID: str = "458272416814"
    DOCUMENTAI_PROCESSOR_ID: str = "ae6356d350bf69a6"
```

**Key Design Decision**: The `Settings` class validates on import. If required env vars are missing, the process exits with an error message immediately — no silent failures.

#### Source 2: `config/platform.yaml` → `load_config()` (Platform Configuration)

**File**: `platform_core/config.py`  
**Purpose**: Master YAML config that controls ALL platform behavior. Loaded via `load_config()`.

The YAML file supports `${ENV_VAR}` syntax for secret interpolation:

```yaml
providers:
  llm:
    mistral:
      type: mistral
      params:
        api_key: "${MISTRAL_API_KEY}"    # Resolved from .env at runtime
        model: "mistral-large-latest"
  ocr:
    mistral:
      type: mistral_ocr
      params:
        api_key: "${MISTRAL_API_KEY}"
  storage:
    local:
      type: local
      params:
        base_dir: "${STORAGE_DIR}"
  embedding:
    dinov2:
      type: dinov2
      params:
        model: "facebook/dinov2-small"
        device: "cpu"
  vision:
    mistral:
      type: mistral_vision
      params:
        api_key: "${MISTRAL_API_KEY}"
        model: "pixtral-12b-2409"

fallback_chains:
  llm.default:     [mistral]
  llm.classifier:  [mistral]
  ocr.default:     [mistral]
  vision.default:  [mistral]

pipelines:
  document_processing:
    workflow_engine: mistral          # "auto" | "mistral" | "local"
    enable_pre_validation: true
    enable_preprocessing: false
    review_confidence_threshold: 0.80
    step_timeout_seconds: 300
    max_file_size_mb: 50
  claim_processing:
    step_timeout_seconds: 120

resilience:
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout_seconds: 60
  retry:
    max_retries: 3
    base_delay_seconds: 1.0
  health_check:
    interval_seconds: 30
```

**Config Resolution Flow**:
1. `_load_dotenv()` reads `.env` into `os.environ` (custom parser, no `python-dotenv` dependency)
2. `yaml.safe_load()` parses `config/platform.yaml`
3. `_resolve_env_vars()` recursively walks the dict and replaces `${VAR}` with `os.environ.get(VAR)`
4. Returns the fully resolved dict

**Why Two Config Sources?** The `config.py` (pydantic) is legacy from V1 where every agent had a Mistral Studio Agent ID. The `platform.yaml` is the new approach for V2. Both coexist during the migration period.

---

## 5. Application Entry Point & Lifecycle

### File: `main.py`

The FastAPI app uses an async context manager (`lifespan`) for startup/shutdown:

```
STARTUP SEQUENCE (in order):
1. init_db()            — Create SQLAlchemy tables (Document, ExtractedData, PipelineCheckpoint)
2. init_claim_tables()  — Create claim-related tables (Claim, ClaimDocument, ClaimReport, etc.)
3. os.makedirs(STORAGE_DIR) — Ensure upload directory exists
4. load_config()        — Parse platform.yaml with env var resolution
5. ProviderRegistry.from_config(config) — Instantiate all providers, set singleton
6. HealthMonitor.start() — Background task: health check all providers every 30s
7. registry.get_embedding("dinov2") — Preload DINOv2 model into memory
8. get_redis_pool()     — Initialize arq Redis connection pool

SHUTDOWN SEQUENCE:
1. HealthMonitor.stop()
2. Redis pool close
```

**App Configuration**:
- `docs_url=None` — Swagger UI is served from a custom endpoint that loads JS/CSS from unpkg CDN
- CORS middleware reads `allowed_origins` from `platform.yaml` (defaults to `["*"]`)
- `setup_observability(app)` mounts `/metrics` Prometheus endpoint and instruments FastAPI with OpenTelemetry

**API Router Mounting**:
- `api_v1_router` (from `api/routers/v1/__init__.py`) is included directly on `app`
- All v1 routes are prefixed with `/api/v1`

**Health Endpoint**: `GET /health` returns provider registry summary + last health check results.

---

## 6. Database Layer

### Engine: SQLite + aiosqlite (async)

**File**: `db/database.py`

```python
engine = create_async_engine(
    settings.DATABASE_URL,  # "sqlite+aiosqlite:///./doc_workflow.db"
    echo=False,
    connect_args={"check_same_thread": False}  # SQLite-specific
)
```

**SQLite Optimizations** (applied on every connection via event listener):
- `PRAGMA journal_mode=WAL` — Write-Ahead Logging for concurrent reads during writes
- `PRAGMA synchronous=NORMAL` — Faster writes with acceptable durability

**Session Factory**: `AsyncSessionLocal` with `expire_on_commit=False` (prevents lazy-load errors after commit).

**Migration Strategy**: No formal migration tool (no Alembic). Uses defensive `ALTER TABLE ADD COLUMN` wrapped in try/except — silently ignores "column already exists" errors. Called on every startup via `init_db()` and `init_claim_tables()`.

### ORM Models (9 total)

**File**: `db/models.py`

#### Document Domain (3 models)

| Model | Table | Purpose | Key Fields |
|---|---|---|---|
| `CustomerReference` | `customer_references` | KYC customer records with reference signature/photo | `customer_id` (unique), `reference_signature` (base64), `reference_photo` (base64) |
| `Document` | `documents` | Uploaded document metadata | `id` (UUID), `filename`, `file_path`, `file_hash` (SHA-256), `doc_type`, `status`, `workflow_run_id`, `customer_id` (FK) |
| `ExtractedData` | `extracted_data` | OCR extraction + validation results | `document_id` (FK, unique), `raw_extracted` (JSON), `validated_data` (JSON), `confidence_score`, `fraud_check` (JSON), `signature_verification` (JSON) |

**Document Status Lifecycle**: `pending → processing → pre_validating → preprocessing → classifying → fraud_checking → extracting → validating → auto_verifying → reviewing → finalizing → completed`  
Also: `paused` (HITL), `rejected`, `failed`, `deleted`

#### Claim Domain (6 models)

| Model | Table | Purpose | Key Fields |
|---|---|---|---|
| `Claim` | `claims` | Insurance claim record | `claim_id` (e.g. `CLM-2026-1234`), `claimant_id`, `policy_id`, `status`, `amount`, `priority` |
| `ClaimDocument` | `claim_documents` | OCR-extracted fields per doc type per claim | `claim_id` (FK), `doc_type`, `fields` (JSON) |
| `ClaimantHistory` | `claimant_history` | Prior claims per claimant | `claimant_id`, `prior_claim_id`, `submitted_at`, `status` |
| `PolicyDetails` | `policy_details` | Insurance policy records | `policy_id` (unique), `holder_name`, `coverage_type`, `start_date`, `end_date` |
| `ClaimReport` | `claim_reports` | Final claim adjudication report | `claim_id` (FK, unique), `agent_results` (JSON — all 5 agents), `suggestion` (text), `overall_status` |
| `ClaimDocumentLink` | `claim_document_links` | Bridge: Document ↔ Claim | `claim_id` (FK), `document_id` (FK), `doc_type`, `synced` (pending/synced/failed) |

**Claim Status Lifecycle**: `creating → extracting → ready → processing → checking_integrity → checking_medical → checking_treatment → checking_disability → checking_litigation → generating_report → saving_report → completed`  
Also: `approved`, `rejected`, `failed`

#### Pipeline Support (1 model)

| Model | Table | Purpose |
|---|---|---|
| `PipelineCheckpoint` | `pipeline_checkpoints` | Crash recovery — stores pipeline state after each step | `pipeline_id` (unique), `data` (JSON text blob) |

### Database Operations

**File**: `db/operations.py` — Document-focused operations:
- `update_status(document_id, status)` — Update document status
- `update_error(document_id, error_details)` — Set status=failed + store error JSON
- `check_duplicate_hash(file_hash, exclude_id)` — Find document with same SHA-256
- `check_duplicate_filename(filename, exclude_id)` — Find document with same filename
- `get_document(document_id)` — Fetch by ID
- `save_checkpoint / load_checkpoint / clear_checkpoint / list_checkpoints` — Pipeline recovery

**File**: `db/claim_operations.py` — Claim-focused operations:
- `create_claim(...)` — Generate `CLM-YYYY-XXXX` ID, insert row
- `get_claim_extraction_status(claim_id)` — Check OCR completion across linked documents. When all docs are extracted, transitions claim to `ready` and backfills claim-level fields from claim_form/policy_document extracted data
- `link_document_to_claim(claim_id, document_id, doc_type)` — Create bridge record, transition claim to `extracting`
- `get_claim_documents_data(claim_id, doc_types)` — Fetch OCR fields via JOIN through `ClaimDocumentLink → Document → ExtractedData`
- `get_claimant_history(claimant_id)` — Fetch prior claims, compute 12-month count
- `get_policy_details(policy_id)` — Fetch policy coverage dates
- `save_claim_report(...)` — Upsert final report
- `upsert_agent_result(claim_id, agent_key, result)` — Incrementally write individual agent results as they complete (uses `flag_modified` to force SQLAlchemy JSON mutation detection)

---

## 7. Provider System (platform_core)

### Architecture: Abstract Interfaces + Concrete Implementations + Registry

The provider system is the heart of Backend V2's vendor-agnostic design.

### 7.1 Abstract Interfaces

**File**: `platform_core/providers/interfaces.py`

Five abstract provider types, each with a mandatory `health_check()` method:

#### LLMProvider
```python
class LLMProvider(ABC):
    async def chat(messages, system_prompt, tools, temperature, max_tokens, response_format) -> LLMResponse
    async def health_check() -> ProviderStatus
    @property def name -> str
```
**LLMResponse** dataclass: `content`, `tool_calls` (list of dicts), `finish_reason`, `usage` dict, `provider` name, `latency_ms`, `raw_response`.

**Why `tool_calls` is `list[dict]` not a vendor type**: Forces normalization at the provider boundary. All consumers receive the same shape: `{"id": "...", "function": {"name": "...", "arguments": "...JSON string..."}}`.

#### OCRProvider
```python
class OCRProvider(ABC):
    async def extract(file_path, pages, include_blocks, **kwargs) -> OCRResponse
```
**OCRResponse** dataclass: `raw_text`, `confidence` (0.0–1.0), `pages` list, `blocks` (bounding boxes), `word_confidences`, `document_annotation`.

**Why blocks are returned**: The frontend uses bounding box coordinates for citation highlighting — showing which part of the scanned document corresponds to each extracted field.

#### StorageProvider
```python
class StorageProvider(ABC):
    async def save(data, key, metadata) -> str
    async def get(key) -> bytes
    async def delete(key) -> None
    async def get_signed_url(key, expires_seconds) -> str
    async def exists(key) -> bool
```

#### EmbeddingProvider
```python
class EmbeddingProvider(ABC):
    async def embed(inputs) -> EmbeddingResponse
    async def embed_images(image_paths) -> EmbeddingResponse
```

#### VisionProvider
```python
class VisionProvider(ABC):
    async def analyze(images, prompt, response_format) -> LLMResponse
```
**Why VisionProvider returns LLMResponse**: Vision analysis is effectively a chat completion with image inputs. The response format (content + optional tool calls) is identical to LLM.

### 7.2 Concrete Implementations

#### MistralLLM (`platform_core/providers/llm/mistral.py`)

- Wraps `Mistral(api_key=...).chat.complete_async(**kwargs)`
- Prepends `system_prompt` as a `{"role": "system"}` message (replaces Mistral Agent's baked-in system prompt)
- Normalizes `tool_calls` from Mistral SDK objects to plain dicts
- Tracks `latency_ms` for observability
- Health check: sends `"ping"` with `max_tokens=1`

**Key Design Decision**: The V1 pattern used `client.agents.complete_async(agent_id=...)` which required pre-configured agents in Mistral Studio. V2 uses `client.chat.complete_async(model=..., messages=[system_prompt + user_message])` with locally-managed prompts. This makes the system portable — you can switch to OpenAI by implementing `OpenAILLM` with the same interface.

#### MistralOCR (`platform_core/providers/ocr/mistral_ocr.py`)

- Reads file as base64, constructs data URL with correct MIME type
- Validates PDF page ranges using `pypdf.PdfReader`
- Calls `client.ocr.process(model="mistral-ocr-latest", document=..., confidence_scores_granularity="word", include_blocks=True)`
- Parses response: extracts per-page markdown, average confidence across pages, word-level confidence scores, bounding box blocks (filtering out image blocks)
- Extracts `document_annotation` if present (supports structured extraction)

#### MistralVision (`platform_core/providers/vision/mistral_vision.py`)

- Uses `pixtral-large-latest` model for multimodal image analysis
- Builds content parts: `[{"type": "text", "text": prompt}, {"type": "image_url", ...}, ...]`
- `_resolve_image_url()` converts file paths → data URLs, raw base64 → data URLs, or passes through existing data URLs
- Used for: signature comparison, face comparison, document quality checks

#### DINOv2Embedding (`platform_core/providers/embedding/dinov2.py`)

- Loads `facebook/dinov2-small` model at initialization (HuggingFace `AutoModel`)
- Preprocessing pipeline (derived from `utils/signature_verifier.py`):
  1. Load image with OpenCV
  2. Convert to grayscale
  3. Binarize (Otsu threshold in fast mode, Sauvola with connected component filtering in quality mode)
  4. Tight crop with 10px padding
  5. Resize to 224×224 with aspect ratio preservation, pad with zeros
  6. Convert to 3-channel RGB (stack grayscale 3x)
  7. Apply ImageNet normalization: `mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]`
- Generates CLS token embeddings, L2-normalized
- Runs inference in a `ThreadPoolExecutor(max_workers=2)` to avoid blocking the async event loop
- `compare()` method: computes cosine similarity, returns `{score, decision}` with thresholds: `≥0.75 → MATCH`, `≥0.55 → REVIEW`, `<0.55 → MISMATCH`

### 7.3 Provider Registry

**File**: `platform_core/registry.py`

**Pattern**: Singleton with factory constructor.

```python
# At startup:
registry = ProviderRegistry.from_config(config)  # Sets singleton

# Anywhere in the app:
registry = ProviderRegistry.get()                 # Returns singleton
llm = registry.get_llm("mistral")                 # Direct access
chain = registry.get_llm_chain("classifier")      # Fallback chain
```

**Factory Method (`from_config`)** flow:
1. Call `_register_builtin_providers()` — imports all concrete classes into `PROVIDER_CLASSES` dict, silently skips if import fails (optional dependencies)
2. For each provider category in config (`llm`, `ocr`, `storage`, `embedding`, `vision`):
   - Look up `type` field → find matching class in `PROVIDER_CLASSES`
   - Instantiate with `**params`
   - Register in the appropriate dict
3. Load fallback chain definitions from config
4. Set as singleton

**Builtin Provider Classes** (registered by `_register_builtin_providers()`):
```python
PROVIDER_CLASSES = {
    "llm":       {"mistral": MistralLLM},
    "ocr":       {"mistral_ocr": MistralOCR},
    "vision":    {"mistral_vision": MistralVision},
    "storage":   {"local": LocalStorage},
    "embedding": {"dinov2": DINOv2Embedding},
}
```

**Adding a new provider** (e.g., OpenAI):
1. Create `platform_core/providers/llm/openai.py` implementing `LLMProvider`
2. Import in `_register_builtin_providers()`: `PROVIDER_CLASSES["llm"]["openai"] = OpenAILLM`
3. Add to `platform.yaml`:
   ```yaml
   providers:
     llm:
       openai:
         type: openai
         params:
           api_key: "${OPENAI_API_KEY}"
           model: "gpt-4o"
   fallback_chains:
     llm.default: [mistral, openai]  # Mistral first, fallback to OpenAI
   ```

---

## 8. Resilience Layer

### 8.1 Circuit Breaker

**File**: `platform_core/resilience/circuit_breaker.py`

**State Machine**:
```
CLOSED (normal) ──[5 consecutive failures]──→ OPEN (blocking)
OPEN ──[60 seconds elapsed]──→ HALF_OPEN (probe)
HALF_OPEN ──[probe succeeds]──→ CLOSED
HALF_OPEN ──[probe fails]──→ OPEN
```

**Parameters**: `failure_threshold=5`, `recovery_timeout=60s`

**How it works**: Each provider gets its own `CircuitBreaker` instance (created by `FallbackChain`). When `is_open` is checked:
- If `OPEN` and recovery timeout elapsed → transitions to `HALF_OPEN`, returns `False` (allow one probe)
- If `OPEN` and timeout not elapsed → returns `True` (skip this provider)
- If `CLOSED` → returns `False`

### 8.2 Fallback Chain

**File**: `platform_core/resilience/fallback.py`

```python
chain = FallbackChain([mistral_llm, openai_llm], purpose="classifier")
response = await chain.call(method="chat", messages=..., system_prompt=..., tools=...)
```

**Flow**:
1. Iterate through providers in order
2. Skip providers with open circuit breakers
3. Call the method on the provider
4. On success: record success on circuit breaker, return result
5. On failure: record failure on circuit breaker, log error, try next provider
6. If ALL providers fail: raise `AllProvidersFailedError` with all error details

### 8.3 Retry Policy

**File**: `platform_core/resilience/retry.py`

```python
policy = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=30.0)
result = await policy.execute(some_async_function, arg1, arg2)
```

**Backoff formula**: `delay = min(base_delay × 2^attempt + random(0,1), max_delay)`

**Retryable errors** (default): `ConnectionError, TimeoutError, asyncio.TimeoutError, OSError`  
Non-retryable errors raise immediately without consuming retries.

### 8.4 Health Monitor

**File**: `platform_core/resilience/health.py`

- Background `asyncio.Task` that runs in a loop every `interval_seconds` (default 30s)
- Calls `registry.health_check_all()` which iterates all registered providers and calls their `health_check()` method
- Results are stored in `_last_results` and logged (warnings for DOWN/DEGRADED)
- Started during FastAPI lifespan startup, cancelled during shutdown

---

## 9. Pipeline Orchestration Engine

### Dual Execution Model

Backend V2 supports two pipeline execution engines, selected per-deployment via `pipelines.document_processing.workflow_engine` in `platform.yaml`:

| Engine | When Used | Durability | Orchestration |
|---|---|---|---|
| **Mistral Workflows SDK** | `workflow_engine: "mistral"` or `"auto"` with Mistral LLM | Managed by Mistral's Temporal Cloud | Activities defined with `@workflows.activity`, workflow class with `@workflows.workflow.define` |
| **Local PipelineEngine** | `workflow_engine: "local"` or non-Mistral provider | DB-backed checkpointing | Step-by-step sequential execution with `CheckpointManager` |

### 9.1 Local PipelineEngine

**File**: `platform_core/pipeline/engine.py`

#### Core Data Structures

```python
@dataclass
class StepDefinition:
    name: str                      # e.g., "classify"
    handler: Callable              # Async function: (context) -> dict
    status_label: str              # e.g., "classifying" — sent to DB
    required: bool = True          # If False, step failure is non-fatal
    condition: Callable | None     # Dynamic skip condition: (ctx) -> bool
    timeout_seconds: int = 300

@dataclass
class PipelineDefinition:
    name: str                      # e.g., "document_processing"
    steps: list[StepDefinition]

class StepStatus(Enum):
    PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, PAUSED
```

#### Execution Flow

```python
engine = PipelineEngine(checkpoint_mgr=checkpoint_mgr)
result = await engine.run(pipeline=pipeline, context=context, on_status_change=callback)
```

1. **Load Checkpoint**: If a checkpoint exists for this `pipeline_id` (= `document_id`), skip to `completed_step_index + 1` and restore context
2. **For each step**:
   a. Check `condition` — skip if returns `False` (e.g., fraud_check only for KYC documents)
   b. Call `on_status_change` callback to update DB status label
   c. Execute step handler with `asyncio.wait_for(timeout=step.timeout_seconds)`
   d. Handle result:
      - **COMPLETED**: Merge step output into context, save checkpoint
      - **PAUSED** (HumanInputRequired): Save checkpoint at `step_index - 1` (so step re-runs on resume), return partial context with `_paused_at` and `_paused_reason`
      - **FAILED** (required=True): Set `_failed_at` and `_error`, return context
      - **FAILED** (required=False): Log warning, continue to next step
3. **All steps completed**: Clear checkpoint, record pipeline duration metric

#### Exception-Based Flow Control

Steps use exceptions to signal non-standard outcomes:
- `HumanInputRequired(reason, data)` → Step status = PAUSED
- `PipelineRejected(reason, data)` → Step status = FAILED

### 9.2 Checkpoint Manager

**File**: `platform_core/pipeline/checkpoint.py`

**Storage Strategy**: Dual-mode — database-backed (production) or in-memory dict (dev/testing).

**Checkpoint Data**:
```python
{
    "pipeline_id": "doc-uuid-123",
    "completed_step_index": 3,
    "completed_step_name": "classify",
    "context": {... serializable subset of pipeline context ...},
    "timestamp": 1719200000.0
}
```

**Context Sanitization**: Before saving, `_sanitize_context()` strips non-JSON-serializable values (e.g., raw LLM response objects) and internal keys starting with `_registry` or `_engine`.

### 9.3 Mistral Workflows SDK Integration

**File**: `platform_core/pipeline/mistral_workflow.py`

**When Used**: When `workflow_engine` is `"mistral"` or `"auto"` with Mistral as default LLM.

**Architecture**:
- Each pipeline step is defined as a `@workflows.activity` with its own timeout and retry policy
- The workflow class `DocumentProcessingWorkflow` orchestrates activities in sequence
- The workflow MUST be deterministic (Temporal replays from history on worker restart)
- Activities are NOT deterministic (they make LLM calls, DB writes)

**Activity definitions** (10 activities wrapping existing `activities/*.py` functions):
```python
@workflows.activity(start_to_close_timeout=timedelta(minutes=2), retry_policy_max_attempts=2)
async def activity_intake(document_id, filename) -> dict:
    from activities.intake import intake_activity
    return await intake_activity(document_id, filename)
```

**Workflow class**:
```python
@workflows.workflow.define(name="document-processing", execution_timeout=timedelta(minutes=30))
class DocumentProcessingWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, input: DocumentInput) -> DocumentOutput:
        # Sequential execution with conditional branching
        # IMPORTANT: Duplicate check is COMMENTED OUT (bypassed for testing)
```

**I/O Schemas** (Pydantic models):
- `DocumentInput`: `document_id`, `filename`, `file_path`, `enable_pre_validation`, `enable_preprocessing`
- `DocumentOutput`: `document_id`, `status`, `doc_type`, `error`, `paused_reason`

### 9.4 Pipeline Definitions

**File**: `platform_core/pipeline/definitions.py`

Two pipeline builders:

#### Document Processing Pipeline (9 steps)

```python
def build_document_pipeline(config) -> PipelineDefinition:
    steps = [
        StepDefinition(name="intake",        required=True),
        StepDefinition(name="pre_validate",   required=False, condition=lambda ctx: config.enable_pre_validation),
        StepDefinition(name="preprocess",     required=False, condition=lambda ctx: config.enable_preprocessing),
        StepDefinition(name="classify",       required=True),
        StepDefinition(name="fraud_check",    required=False, condition=lambda ctx: _is_kyc_document(ctx)),
        StepDefinition(name="extract",        required=True),
        StepDefinition(name="validate",       required=True),
        StepDefinition(name="auto_verify",    required=False, condition=lambda ctx: _is_kyc_document(ctx)),
        StepDefinition(name="review",         required=True),
        StepDefinition(name="output",         required=True),
    ]
```

**KYC Document Detection** (`_is_kyc_document`): Returns `True` if `doc_type` is in `{"kyc", "kyc document", "identity document", "id_proof", "pan_card"}` or template metadata has `is_kyc=True`.

#### Claim Processing Pipeline (7 steps)

```python
def build_claim_pipeline(config) -> PipelineDefinition:
    steps = [
        StepDefinition(name="claim_integrity"),
        StepDefinition(name="claim_medical"),
        StepDefinition(name="claim_treatment"),
        StepDefinition(name="claim_disability"),
        StepDefinition(name="claim_litigation"),
        StepDefinition(name="claim_report"),      # LLM generates final suggestion
        StepDefinition(name="save_claim_report"),  # Persist to DB
    ]
```

**Claim pipeline is ALWAYS local** — Mistral Workflows SDK integration is not implemented for claims.

---

## 10. Agent Loop (LLM Conversation Engine)

**File**: `platform_core/agent_loop.py`

### Why It Exists

All 16 activity files follow the exact same pattern:
1. Send user message + system prompt + tools to LLM
2. If LLM returns `tool_calls` → execute them locally, append results
3. Repeat until LLM returns a final text-only response
4. Parse the response as JSON

This module extracts that pattern into two reusable functions.

### `run_agent_loop()` — Multi-Turn with Tools

```python
result = await run_agent_loop(
    llm=registry.get_llm(),
    system_prompt=prompts.get("classifier"),
    user_message="Classify the document at ...",
    tools_schema=CLASSIFIER_TOOLS,
    tool_executor=my_tool_executor,  # async (tool_name, args_dict) -> result
    temperature=0.2,
    max_tokens=4096,
    max_iterations=10,
    json_mode=True,
)
```

**Flow**:
1. Build messages: `[{"role": "user", "content": user_message}]`
2. Call `llm.chat(messages, system_prompt, tools, ...)`
3. If NO tool_calls → parse final response as JSON
   - If parse fails and `json_mode=True` → send follow-up asking LLM to reformat as JSON with `response_format={"type": "json_object"}`
4. If tool_calls present:
   - Append assistant message with tool_calls to conversation
   - For each tool call: parse arguments JSON, call `tool_executor(name, args)`, append result as tool message
   - Loop back to step 2
5. After `max_iterations` → raise `AgentLoopError`

**JSON Parsing** (`_parse_json_response`):
1. Try `json.loads(text)` directly
2. Try extracting from markdown code block: `` ```json ... ``` ``
3. Fallback: find first `{` to last `}` and parse that substring
4. Fallback: find first `[` to last `]` and parse that substring
5. Raise `ValueError` if all fail

### `run_simple_completion()` — Single-Turn (No Tools)

```python
result = await run_simple_completion(llm, system_prompt, user_message, json_mode=True)
```

Used by agents that don't need tools: validator, claim_report, face_judge, signature_judge.

---

## 11. Prompt Management

**File**: `platform_core/prompts/manager.py`

```python
prompts = PromptManager()             # Defaults to platform_core/prompts/ directory
system_prompt = prompts.get("classifier")  # Loads classifier.md, caches in memory
```

**Design Decision**: Replaces Mistral Agent IDs (pre-configured on Mistral Studio's web interface) with local `.md` files. Benefits:
- Version controllable (Git)
- Works with any LLM provider (not Mistral-specific)
- Editable in production (`reload()` clears cache)
- Inspectable without Mistral Studio access

**Prompt Files** (16 total, one per pipeline step):
- `classifier.md`, `extractor.md`, `validator.md`, `reviewer.md`, `output.md`
- `intake.md`, `pre_validator.md`, `preprocessor.md`, `fraud_checker.md`, `auto_verifier.md`
- `claim_integrity.md`, `claim_medical.md`, `claim_treatment.md`, `claim_disability.md`, `claim_litigation.md`, `claim_report.md`

---

## 12. Step Isolation & Sandboxing

**File**: `platform_core/isolation/sandbox.py`

### ScopedProviderRegistry

A restricted view of `ProviderRegistry` that only allows access to declared provider types per step:

```python
DEFAULT_PROVIDER_ACCESS = {
    "intake":       ["llm"],
    "classify":     ["llm", "ocr"],
    "extract":      ["llm", "ocr"],
    "fraud_check":  ["llm", "ocr", "vision"],
    "auto_verify":  ["llm", "embedding", "vision"],
    "output":       ["llm", "storage"],
    # ...
}
```

Calling `get_ocr()` from the `intake` step raises `PermissionError`.

### StepSandbox

Wraps step execution with:
1. **Scoped registry** — provider access control
2. **Timeout boundary** — `asyncio.timeout(seconds)`
3. **Error boundary** — wraps all exceptions in `StepExecutionError(step_name, original)`
4. **Output validation** — step must return `dict` or `None`

**Note**: Sandbox is defined but NOT wired into the current `PipelineEngine.run()`. The engine calls step handlers directly. The sandbox infrastructure exists for future integration.

---

## 13. Document Processing Pipeline (Steps 1–7)

### Step 1: Intake (Duplicate Detection)

**Activity**: `activities/intake.py`  
**Tools**: `check_document_duplicates(document_id, filename)`  
**Flow**:
1. Send prompt to LLM asking it to check for duplicates
2. LLM calls `check_document_duplicates` tool
3. Tool queries DB for documents with same `file_hash` (SHA-256) or same `filename`
4. LLM interprets result and returns `{"is_duplicate": bool, "existing_document_id": str|null}`

**Fallback**: If the LLM loop fails, performs a direct DB duplicate check without LLM involvement.

**If duplicate found**: `HumanInputRequired` exception → pipeline pauses, waits for user override decision via API.

### Step 2: Pre-Validation (Quality Checks)

**Activity**: `activities/pre_validator.py`  
**Tools**: `get_file_metadata(file_path)`  
**Special Behavior**: This activity has a custom conversation loop (not `run_agent_loop`) because:
1. First turn: LLM calls `get_file_metadata` to get MIME type, file size, `is_visual` flag
2. If visual: the file is base64-encoded and sent as a multimodal message (image_url or document_url content block)
3. LLM performs visual quality checks (blur, brightness, skew, readability) and returns JSON verdict

**DOCX Auto-Pass**: DOCX files auto-pass with a warning — they have no visual representation.

**Output**: `{"passed": bool, "rejection_reason": str|null, "warnings": [str], "checks": {...}}`

**If failed**: `PipelineRejected` exception → pipeline terminates with rejection.

### Step 2.5: Preprocessing (Image Enhancement)

**Activity**: `activities/preprocessor.py`  
**Tools**: `enhance_document_image(file_path, output_path)`  
**Condition**: Only runs if `enable_preprocessing: true` in config.

**Enhancement Pipeline** (implemented in `utils/preprocessor.py`):
1. **Resolution Normalization**: Upscale if short side < 1000px (LANCZOS, max 3x)
2. **Brightness/CLAHE**: Adaptive histogram equalization on LAB L-channel (`clip_limit=2.0, tile_grid=(8,8)`)
3. **Noise Removal**: 3×3 Gaussian blur
4. **Skew Correction**: Canny edge detection → HoughLinesP → median angle → rotate (skip if |angle| < 0.5°)

**PDF handling**: If `preprocess_pdf=True`, rasterizes each page at 150 DPI via PyMuPDF, preprocesses each, reassembles into new PDF.

**Fallback Design**: On ANY error, returns the original file path so the pipeline is never blocked.

**Anti-Hallucination Check**: After LLM returns, verifies the `preprocessed_path` actually exists on disk. If not, falls back to original.

### Step 3: Classify

**Activity**: `activities/classifier.py`  
**Tools**: `get_supported_document_types`, `get_document_text(file_path)`

**Flow**:
1. LLM calls `get_supported_document_types` → returns list of allowed types
2. LLM calls `get_document_text` → OCR extracts text from the document
3. LLM classifies and returns `{"doc_type": str, "confidence": float, "reasoning": str}`

**Type Matching**: Returned `doc_type` is fuzzy-matched against the supported types map (handles case differences, underscores vs spaces).

**Supported Document Types** (from `config.py`):
`invoice, pan_card, claim_form, policy_document, id_proof, medical_report, lab_reports, prescription_records, bills_invoices, disability_certificate, legal_letter`

### Step 3.5: Fraud Check (KYC Only)

**Activity**: `activities/fraud_checker.py`  
**Tools**: `run_identity_proofing(file_path)`  
**Condition**: Only runs for KYC/identity documents.

**Flow**: LLM calls `run_identity_proofing` which uses Google Document AI's Identity Document Proofing processor to run forensic checks on the document image.

**If failed**: `PipelineRejected` exception → pipeline terminates.

### Step 4: Extract (OCR + LLM)

**Activity**: `activities/extractor.py`  
**Tools**: `extract_text_from_document(file_path, doc_type)`, `crop_kyc_images(file_path, doc_type)`

**This is the most complex activity** — uses a custom conversation loop because it needs to capture side-effect state from tool execution.

**Flow**:
1. Build prompt with normalization rules (from `utils/norm_config.py`)
2. LLM calls `extract_text_from_document`:
   - Calls OCR provider via `utils/ocr.py`
   - Returns `raw_text`, `structured_ocr_extraction` (via document annotation), `word_confidence_scores`
   - Activity captures `ocr_confidence` and `word_confidence_scores` from tool result
3. For KYC docs: LLM calls `crop_kyc_images` to extract signature and photo crops
4. LLM returns `{"raw_extracted": dict, "normalized_extracted": dict}`

**Post-Processing** (after LLM returns):
- **Field-level confidence**: For each extracted field, matches words against OCR word confidence scores to compute per-field confidence
- **KYC image merging**: If signature/photo crops were detected, adds `signature_image`, `photo_image`, `signature_detected`, `photo_detected`, `signer_name` to extracted data

**Normalization Rules** (from `utils/norm_config.py`):
- Date format: `YYYY-MM-DD | MM/DD/YYYY | DD/MM/YYYY | as-is`
- Number format: `float | integer | as-is`
- Name casing: `Title Case | UPPERCASE | as-is`
- Name sequence: `Firstname Lastname | Lastname, Firstname Middlename | ...` (6 options)
- Custom rules: free-text appended to the prompt

### Step 5: Validate

**Activity**: `activities/validator.py`  
**Tools**: `get_template_fields(doc_type)`

**Flow**: LLM receives extracted data + OCR confidence + field confidences, calls `get_template_fields` to get the expected schema for this document type, then validates against business rules and corrects obvious OCR errors.

### Step 5.5: Auto-Verify (KYC Only)

**Activity**: `activities/auto_verifier.py`  
**Tools**: `find_customer_reference(customer_id)`, `verify_signature(customer_id)`, `verify_face(customer_id)`

**Flow**:
1. LLM calls `find_customer_reference` to check if reference records exist for the customer
2. If reference exists: calls `verify_signature` (DINOv2 embedding comparison) and `verify_face` (Mistral Vision multimodal analysis)
3. Returns verification verdict

**Signature Verification** uses DINOv2 cosine similarity: `≥0.75 → MATCH`, `≥0.55 → REVIEW`, `<0.55 → MISMATCH`

### Step 6: Review

**Activity**: `activities/reviewer.py`  
**Tools**: `get_review_context(document_id)`

**Flow**: LLM evaluates confidence score + validation results and decides:
- `auto_approved: True` → pipeline continues to output
- `auto_approved: False` → `HumanInputRequired` exception → pipeline pauses

**Threshold**: `review_confidence_threshold: 0.80` in config.

### Step 7: Output

**Activity**: `activities/output.py`  
**Tools**: `persist_final_extraction(document_id, ...)`

**Flow**: LLM calls `persist_final_extraction` which:
1. Creates/updates `ExtractedData` row with `raw_extracted`, `validated_data`, `confidence_score`, `field_confidences`, `fraud_check`, `signature_verification`, `photo_verification`
2. Updates `Document.status` to `completed` and `Document.doc_type`
3. If document is linked to a claim: syncs extracted data to `ClaimDocument.fields` and updates `ClaimDocumentLink.synced` to `"synced"`

---

## 14. Claim Processing Pipeline (Steps 1–7)

### Overview

The claim pipeline runs 5 specialized AI agents in sequence, each evaluating a different aspect of the insurance claim. Then a 6th agent generates a final recommendation, and step 7 persists the report.

All 5 agents share the SAME 3 tools (defined in `tools/claim_tools.py`) and use the SAME `dispatch_claim_tool` dispatcher.

### Shared Claim Tools

```python
CLAIM_TOOLS = [
    {"function": {"name": "get_claim_documents_data",
     "parameters": {"claim_id": str, "doc_types": list[str]}}},
    {"function": {"name": "get_claimant_history",
     "parameters": {"claimant_id": str}}},
    {"function": {"name": "get_policy_details",
     "parameters": {"policy_id": str}}},
]
```

Each tool is a pure data fetcher — the LLM does ALL reasoning.

### Agent 1: Claim Integrity

**Activity**: `activities/claim_integrity.py`  
**Checks**: Completeness, date logic, policy validity, duplicate claims

### Agent 2: Medical

**Activity**: `activities/claim_medical.py`  
**Checks**: Diagnosis validity, ICD codes, provider credentials, documentation adequacy

### Agent 3: Treatment

**Activity**: `activities/claim_treatment.py`  
**Checks**: Treatment-diagnosis alignment, billing reasonableness

### Agent 4: Disability

**Activity**: `activities/claim_disability.py`  
**Checks**: Disability certificate validity, severity consistency

### Agent 5: Litigation

**Activity**: `activities/claim_litigation.py`  
**Checks**: Attorney involvement, claim frequency patterns, suspicious language

### Agent 6: Claim Report (Synthesis)

**Step Handler**: `_step_claim_report` in `pipeline/definitions.py`

**Flow**:
1. Collects all 5 agent results
2. Builds a summary string for the Claim Report Agent
3. Calls `run_simple_completion()` (no tools) with the `claim_report` system prompt
4. LLM generates `{"suggestion": str, "overall_status": "APPROVE"|"REVIEW BEFORE APPROVAL"|"REJECT"}`

**Rule-Based Fallback** (`_fallback_claim_suggestion`): If the LLM fails:
- Any agent status = `FAIL` → `overall_status = "REJECT"`
- Any agent status = `FLAG` → `overall_status = "REVIEW BEFORE APPROVAL"`
- All agents = `PASS` → `overall_status = "APPROVE"`

### Agent Result Persistence

Each agent's result is written incrementally to `ClaimReport.agent_results` via `upsert_agent_result()` — visible before the entire pipeline finishes. Uses SQLAlchemy's `flag_modified()` to force JSON mutation detection.

### Step 7: Save Claim Report

Persists the final report to `claim_reports` table and updates claim status to `completed`.

---

## 15. Activities Layer (Business Logic)

### Pattern

Every activity file follows this exact structure:

```python
from platform_core.registry import ProviderRegistry
from platform_core.prompts.manager import PromptManager
from platform_core.agent_loop import run_agent_loop

prompts = PromptManager()  # Module-level singleton

async def activity_name(document_id, ...) -> dict:
    try:
        registry = ProviderRegistry.get()
        llm = registry.get_llm()
        system_prompt = prompts.get("activity_name")

        async def execute_tool(name, args):
            if name == "tool_a":
                return await tool_a(...)
            elif name == "tool_b":
                return await tool_b(...)
            else:
                return {"error": f"Unknown tool: {name}"}

        result = await run_agent_loop(
            llm=llm,
            system_prompt=system_prompt,
            user_message="...",
            tools_schema=ACTIVITY_TOOLS,
            tool_executor=execute_tool,
            temperature=...,
        )
        return result

    except Exception as e:
        await db.update_error(document_id, {"error": str(e), "stage": "activity_name"})
        raise
```

### Exceptions to the Pattern

Two activities use custom conversation loops instead of `run_agent_loop()`:

1. **`extractor.py`**: Captures side-effect state (`ocr_confidence`, `word_confidence_scores`, `kyc_image_result`) from tool execution for post-processing
2. **`pre_validator.py`**: Sends multimodal content (base64 image) in a follow-up message after the initial tool call

---

## 16. Tools Layer (LLM Function Calling)

### Architecture

Each tool module exports:
1. **Schema** (`TOOL_NAME_TOOLS`): OpenAI-compatible JSON schema list passed to `llm.chat(tools=...)`
2. **Implementation functions**: Async functions called by the activity's `execute_tool` callback

### Tool Responsibilities

| Tool | Module | What It Does |
|---|---|---|
| `get_supported_document_types` | `tools/classifier.py` | Returns list of supported doc types from `SUPPORTED_DOCUMENT_TYPES` |
| `get_document_text` | `tools/classifier.py` | Calls OCR provider to extract text |
| `extract_text_from_document` | `tools/extractor.py` | OCR + structured extraction + word confidences |
| `crop_kyc_images` | `tools/extractor.py` | Extracts signature/photo regions from KYC documents |
| `get_template_fields` | `tools/validator.py` | Returns expected field schema for a doc type |
| `get_review_context` | `tools/reviewer.py` | Returns confidence score + validation summary |
| `persist_final_extraction` | `tools/output.py` | Writes final data to DB, syncs to claim if linked |
| `check_document_duplicates` | `tools/intake.py` | Checks hash + filename duplicates in DB |
| `get_file_metadata` | `tools/pre_validator.py` | Returns MIME type, file size, is_visual flag |
| `enhance_document_image` | `tools/preprocessor.py` | Runs the 4-step image enhancement pipeline |
| `run_identity_proofing` | `tools/fraud_checker.py` | Calls Google Document AI for forensic analysis |
| `find_customer_reference` | `tools/auto_verifier.py` | Looks up reference records in DB |
| `verify_signature` | `tools/auto_verifier.py` | DINOv2 embedding comparison |
| `verify_face` | `tools/auto_verifier.py` | Mistral Vision multimodal face comparison |
| `get_claim_documents_data` | `tools/claim_tools.py` | Fetches OCR fields per doc type per claim |
| `get_claimant_history` | `tools/claim_tools.py` | Fetches prior claims for a claimant |
| `get_policy_details` | `tools/claim_tools.py` | Fetches policy coverage details |

---

## 17. Utilities Layer

### `utils/ocr.py` — OCR Entry Point

Central OCR function called by tools:
- DOCX files: direct text extraction via `python-docx` (100% confidence, no OCR needed)
- All other files: calls `ProviderRegistry.get().get_ocr().extract(...)` and normalizes the response

### `utils/file_handler.py` — File Operations

- `save_file(UploadFile, storage_dir)` → saves via `aiofiles`, computes SHA-256 hash, returns `(absolute_path, hash)`
- `get_file_as_base64(file_path)` → reads file and base64-encodes
- `delete_file(file_path)` → `os.remove` if exists
- `list_stored_filenames(storage_dir)` → `os.listdir`

### `utils/preprocessor.py` — Image Enhancement

4 standalone functions + orchestrator:
1. `normalize_resolution(img)` — Upscale if short side < 1000px
2. `correct_brightness(img)` — CLAHE on LAB L-channel
3. `remove_noise(img)` — 3×3 Gaussian blur
4. `correct_skew(img)` — Hough transform angle detection + rotation

PDF handling: Rasterize each page at 150 DPI with PyMuPDF, preprocess, reassemble.

### `utils/norm_config.py` — Normalization Rules

- Configuration stored in `{STORAGE_DIR}/norm_config.json`
- Default: `date_format=YYYY-MM-DD, number_format=float, name_casing=Title Case, name_sequence=Firstname Lastname`
- `build_normalization_rules_prompt()` converts config into human-readable rules text that gets injected into the extractor's user prompt

---

## 18. API Layer (FastAPI Routers)

### Router Structure

```
/api/v1/
├── /documents/         # Document lifecycle
├── /claims/            # Claim lifecycle  
├── /settings/          # Normalization config
└── /workflow/          # Mistral workflow status
```

All routers are mounted via `api/routers/v1/__init__.py` which creates a parent `APIRouter(prefix="/api/v1")`.

### 18.1 Documents Router (`api/routers/v1/documents.py`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Upload file, save to disk, create DB record, enqueue pipeline |
| `GET` | `/api/v1/documents/{id}/status` | Get document status + extracted data |
| `PUT` | `/api/v1/documents/{id}/review` | Submit HITL review decision (approve/reject with corrections) |
| `PUT` | `/api/v1/documents/{id}/duplicate-decision` | Override duplicate detection |
| `PUT` | `/api/v1/documents/{id}/extracted-data` | Manual update of extracted data |
| `GET` | `/api/v1/documents/` | List all documents |
| `DELETE` | `/api/v1/documents/{id}` | Delete document + extracted data + file from disk |

**Upload Flow**:
1. Accept `UploadFile` + optional query params (`doc_type`, `claim_id`)
2. Save file to `STORAGE_DIR` via `file_handler.save_file()`
3. Create `Document` row (status=`pending`, store `file_hash`)
4. If `claim_id` provided: call `link_document_to_claim()`
5. Enqueue `run_document_pipeline` task via arq Redis pool
6. Return `DocumentUploadResponse` with `document_id` and `workflow_run_id`

### 18.2 Claims Router (`api/routers/v1/claims.py`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/claims/` | Create a new claim |
| `GET` | `/api/v1/claims/` | List all claims |
| `GET` | `/api/v1/claims/{id}` | Get claim with linked documents |
| `GET` | `/api/v1/claims/{id}/status` | Get extraction completion status |
| `POST` | `/api/v1/claims/{id}/process` | Trigger claim processing pipeline |
| `GET` | `/api/v1/claims/{id}/report` | Get final claim report |
| `POST` | `/api/v1/claims/{id}/decision` | Record human approve/reject decision |
| `DELETE` | `/api/v1/claims/{id}` | Delete claim + links |

**Process Flow**:
1. Check `get_claim_extraction_status()` — all docs must be completed
2. Update claim status to `processing`
3. Enqueue `run_claim_pipeline` task via arq
4. Return claim ID

### 18.3 Settings Router (`api/routers/v1/settings.py`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/settings/normalization` | Get current normalization rules |
| `PUT` | `/api/v1/settings/normalization` | Update normalization rules |

### 18.4 Workflow Router (`api/routers/v1/workflow.py`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/workflow/{run_id}/status` | Query Mistral workflow execution status |

### 18.5 Task Queue (`api/queue.py`)

```python
async def get_redis_pool():
    return await create_pool(RedisSettings(...))

async def enqueue_task(pool, function_name, *args, **kwargs):
    job = await pool.enqueue_job(function_name, *args, **kwargs)
    return job.job_id
```

---

## 19. Background Worker (arq + Redis)

**File**: `worker.py`

### Worker Architecture

The arq worker runs as a separate process (`arq worker.WorkerSettings`):

```python
class WorkerSettings:
    redis_settings = RedisSettings(host=..., port=6379)
    functions = [run_document_pipeline, run_claim_pipeline]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
```

### Startup Sequence

1. `load_config()` — Parse platform.yaml
2. `ProviderRegistry.from_config()` — Initialize all providers
3. Preload DINOv2 embedding model
4. Create `CheckpointManager` (in-memory for now)
5. Determine workflow engine:
   - If `workflow_engine: "mistral"` → start Mistral Workflows worker as background task
   - If `workflow_engine: "local"` → use local PipelineEngine

### Engine Selection Logic

```python
def _should_use_mistral_workflow(config) -> bool:
    engine = config.pipelines.document_processing.workflow_engine
    if engine == "local": return False
    if engine == "mistral": return True
    # "auto": use Mistral if the first provider in llm.default chain is "mistral"
    return fallback_chains.get("llm.default", [])[0] == "mistral"
```

### Mistral Workflow Execution

When using Mistral engine, `_run_mistral_document_pipeline()`:
1. Creates a `Mistral()` client
2. Calls `client.workflows.execute_workflow_async(workflow_identifier=MISTRAL_WORKFLOW_ID, input=..., deployment_name=...)`
3. Returns immediately with `execution_id` — execution continues on Mistral's managed cloud

**The workflow worker** (`_start_mistral_worker`):
- Runs `workflows.run_worker([DocumentProcessingWorkflow])` as a background asyncio task
- The SDK connects to Mistral's cloud using `MISTRAL_API_KEY` and `DEPLOYMENT_NAME`
- Activities are executed locally on this worker process

### Local Pipeline Execution

When using local engine, `_run_local_document_pipeline()`:
1. Build pipeline definition from config
2. Create `PipelineEngine(checkpoint_mgr=...)`
3. Run pipeline with document context
4. Returns final context dict

---

## 20. Observability & Metrics

**File**: `observability.py`

### Prometheus Metrics

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `pipeline_step_duration_seconds` | Histogram | pipeline, step | Duration of each pipeline step |
| `pipeline_step_total` | Counter | pipeline, step, status | Total steps executed (completed/failed/paused/timeout) |
| `pipeline_run_duration_seconds` | Histogram | pipeline | Total pipeline execution time |
| `provider_call_duration_seconds` | Histogram | provider_type, provider_name | Provider call latency |
| `provider_call_total` | Counter | provider_type, provider_name, status | Total provider calls |
| `circuit_breaker_state` | Gauge | provider_name | 0=closed, 1=open, 2=half_open |
| `queue_depth` | Gauge | — | Background task queue depth |
| `agent_loop_iterations` | Histogram | prompt_name | Iterations per agent loop (buckets: 1-10) |
| `agent_loop_tool_calls_total` | Counter | tool_name | Total tool calls by agent loops |

**Endpoint**: `GET /metrics` (mounted as ASGI sub-application)

### OpenTelemetry Tracing

- `TracerProvider` with `SERVICE_NAME="document-ai-platform"`
- Optional `OTLPSpanExporter` if `OTEL_EXPORTER_OTLP_ENDPOINT` is set
- `FastAPIInstrumentor` auto-instruments all HTTP endpoints
- Pipeline steps create spans: `pipeline.step.{step_name}` with `document.id` attribute

### Structured Logging

**File**: `logging_config.py`  
- JSON-formatted structured logging
- Level controlled by `settings.DEBUG` (True → DEBUG, False → INFO)

---

## 21. Deployment & Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml (4 Services)

| Service | Image | Purpose | Ports |
|---|---|---|---|
| `postgres` | `postgres:15-alpine` | Database (docker-compose uses Postgres, but code defaults to SQLite) | 5432 |
| `redis` | `redis:7-alpine` | arq task queue | 6379 |
| `app` | Custom build | FastAPI web server | 8000 |
| `worker` | Custom build | arq background worker (`arq worker.WorkerSettings`) | — |

**Shared Environment Variables** (both `app` and `worker`):
- `MISTRAL_API_KEY`, `DEPLOYMENT_NAME`, `MISTRAL_WORKFLOW_ID`
- `TEMPORAL_SERVER_URL`, `TEMPORAL_NAMESPACE`, `TEMPORAL_TLS`, `TEMPORAL_API_KEY` (for Mistral managed cloud)

**Shared Volumes**:
- `./storage:/app/storage` — Document file storage
- `./config:/app/config` — Platform YAML config
- `./migrations:/app/migrations` — Database migrations

---

## 22. Data Flow Diagrams

### Document Upload → Processing → Completion

```
USER uploads file via POST /api/v1/documents/upload
  │
  ├─→ save_file() → disk + SHA-256 hash
  ├─→ Document row created (status=pending)
  ├─→ If claim_id: ClaimDocumentLink created
  └─→ enqueue_task("run_document_pipeline", document_id, filename, file_path)
        │
        │  [arq worker picks up task]
        │
        ├─→ Mistral Workflow Engine:
        │     └─→ execute_workflow_async() → Mistral Cloud
        │           └─→ Activities run on local worker
        │
        └─→ Local PipelineEngine:
              └─→ Sequential step execution with checkpointing:
                    │
                    Step 1: intake → check_document_duplicates
                    Step 2: pre_validate → get_file_metadata → visual analysis
                    Step 2.5: preprocess → enhance_document_image
                    Step 3: classify → get_document_text → classify
                    Step 3.5: fraud_check → run_identity_proofing [KYC only]
                    Step 4: extract → extract_text_from_document → crop_kyc_images
                    Step 5: validate → get_template_fields → validate
                    Step 5.5: auto_verify → verify_signature + verify_face [KYC only]
                    Step 6: review → get_review_context → approve/pause
                    Step 7: output → persist_final_extraction
                    │
                    └─→ Document.status = "completed"
```

### Claim Processing Flow

```
USER creates claim via POST /api/v1/claims/
USER uploads documents with ?claim_id=CLM-2026-1234
  │
  └─→ Each document goes through Document Pipeline above
        └─→ On completion: output step syncs extracted data to ClaimDocument
              └─→ ClaimDocumentLink.synced = "synced"

USER checks status via GET /api/v1/claims/{id}/status
  └─→ When all docs completed → claim.status = "ready"

USER triggers processing via POST /api/v1/claims/{id}/process
  └─→ enqueue_task("run_claim_pipeline", claim_id, claimant_id, policy_id)
        │
        │  [arq worker picks up task — always local PipelineEngine]
        │
        Agent 1: claim_integrity → get_claim_documents_data, get_claimant_history, get_policy_details
        Agent 2: claim_medical → get_claim_documents_data
        Agent 3: claim_treatment → get_claim_documents_data
        Agent 4: claim_disability → get_claim_documents_data
        Agent 5: claim_litigation → get_claim_documents_data, get_claimant_history
        Agent 6: claim_report → LLM synthesizes final suggestion
        Step 7: save → persist to claim_reports table
        │
        └─→ claim.status = "completed"

USER gets report via GET /api/v1/claims/{id}/report
```

---

## 23. Hidden Assumptions & Design Decisions

### Assumption 1: LLM-for-Everything

Even trivially simple operations (like checking a filename against a DB) are mediated through an LLM conversation loop. **Why**: The LLM can interpret edge cases, provide reasoning, and handle unexpected inputs. **Tradeoff**: Latency and cost — a simple DB query could run in 1ms; routing through an LLM adds 1-5 seconds.

### Assumption 2: Single-Tenant SQLite

The system uses SQLite with WAL mode. **Why**: Simplicity, zero infrastructure. **Limitation**: Single-writer semantics, not suitable for multi-node horizontal scaling. The docker-compose includes Postgres, but the code defaults to SQLite.

### Assumption 3: Agent IDs Are Legacy

`config.py` still requires numerous Mistral Agent IDs (e.g., `CLASSIFIER_AGENT_ID`), but the actual code uses `PromptManager` to load local `.md` files. The env vars exist for backward compatibility and will cause startup failures if not provided (even though they're unused). **Workaround**: Set them to any non-empty string.

### Assumption 4: Duplicate Check Is Disabled in Mistral Workflow

In `mistral_workflow.py`, the duplicate check code is commented out (`# TEMPORARY FIX: Bypass duplicate check to allow testing`). This means documents processed via Mistral Workflows will never be flagged as duplicates.

### Assumption 5: ClaimDocument vs ClaimDocumentLink

Two separate models serve related but different purposes:
- `ClaimDocument`: Stores extracted fields per doc_type per claim (the "claim-level view" of document data)
- `ClaimDocumentLink`: Bridge table that maps Documents (from the OCR pipeline) to Claims

When a document finishes OCR processing, `persist_final_extraction` in the output tool syncs data from `ExtractedData` → `ClaimDocument` via `ClaimDocumentLink`.

### Assumption 6: Checkpoint Manager is In-Memory in Practice

While `CheckpointManager` supports database-backed storage, it's initialized in the worker with `CheckpointManager()` (no `db_operations` argument), which means it uses the in-memory fallback. Checkpoints are lost on worker restart.

### Assumption 7: No Authentication

There is no authentication or authorization on any API endpoint. All endpoints are publicly accessible. CORS is configured but with broad defaults.

### Design Decision: Temperature Settings

- Classification, validation, review: `temperature=0.2` (deterministic, consistent)
- Fraud checking, preprocessing, intake, output: `temperature=0.7` (more creative/adaptive)
- Extraction: `temperature=0.13` (very deterministic — OCR data extraction needs precision)

---

## 24. Environment Variables Reference

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `MISTRAL_API_KEY` | ✅ | — | Mistral AI API key for all AI calls |
| `STORAGE_DIR` | ❌ | `./storage` | Where uploaded files are stored |
| `DATABASE_URL` | ❌ | `sqlite+aiosqlite:///./doc_workflow.db` | Database connection string |
| `REDIS_URL` | ❌ | `redis://localhost:6379/0` | Redis for arq task queue |
| `DEPLOYMENT_NAME` | ❌ | `document-ai-pipeline` | Mistral Workflows deployment name |
| `MISTRAL_WORKFLOW_ID` | ❌ | `""` | Mistral Studio workflow ID |
| `DEBUG` | ❌ | `True` | Enable debug logging |
| `CLASSIFIER_AGENT_ID` | ✅ | — | Legacy Mistral Agent ID (required but unused) |
| `VALIDATOR_AGENT_ID` | ✅ | — | Legacy Mistral Agent ID (required but unused) |
| `REVIEWER_AGENT_ID` | ✅ | — | Legacy Mistral Agent ID (required but unused) |
| `SIGNATURE_VISION_AGENT_ID` | ✅ | — | Legacy Mistral Agent ID (required but unused) |
| `SIGNATURE_JUDGE_AGENT_ID` | ✅ | — | Legacy Mistral Agent ID (required but unused) |
| `GOOGLE_APPLICATION_CREDENTIALS` | ❌ | `""` | Google Cloud service account for Document AI |
| `DOCUMENTAI_PROJECT_ID` | ❌ | `458272416814` | Google Cloud project for fraud detection |
| `DOCUMENTAI_PROCESSOR_ID` | ❌ | `ae6356d350bf69a6` | Document AI processor for identity proofing |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ❌ | — | OpenTelemetry collector endpoint |
| `TEMPORAL_SERVER_URL` | ❌ | — | Mistral managed cloud Temporal endpoint |
| `TEMPORAL_API_KEY` | ❌ | — | Mistral managed cloud auth |

---

## 25. Dependencies & Requirements

### Core Framework
- `fastapi` — HTTP framework
- `uvicorn` — ASGI server
- `pydantic`, `pydantic-settings` — Data validation + settings

### AI / ML
- `mistralai` — Mistral AI SDK (LLM, OCR, Vision, Workflows)
- `transformers` — HuggingFace models (DINOv2)
- `torch`, `torchvision` — PyTorch for DINOv2 inference

### Database
- `sqlalchemy[asyncio]` — ORM
- `aiosqlite` — Async SQLite driver

### Background Tasks
- `arq` — Redis-based async task queue
- `redis` / `aioredis` — Redis client

### Document Processing
- `pypdf` — PDF page validation
- `PyMuPDF` (`fitz`) — PDF rasterization
- `python-docx` — DOCX text extraction
- `Pillow` — Image manipulation
- `opencv-python` (`cv2`) — Computer vision (CLAHE, skew correction, binarization)
- `scikit-image` — Sauvola thresholding (optional, quality mode)
- `numpy` — Numerical operations

### Configuration
- `pyyaml` — YAML config parsing

### Observability
- `prometheus-client` — Metrics
- `opentelemetry-api`, `opentelemetry-sdk` — Tracing
- `opentelemetry-instrumentation-fastapi` — Auto-instrumentation
- `opentelemetry-exporter-otlp-proto-grpc` — OTLP exporter (optional)

### File I/O
- `aiofiles` — Async file operations

---

*Document generated by reverse engineering the Backend V2 codebase. Every component, interface, data flow, and design decision has been documented to enable complete reconstruction from scratch.*
