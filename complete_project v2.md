# PROJECT V2 DOCUMENTATION — Complete Technical Blueprint

> **Document AI Platform — Intelligent Document Processing (IDP)**
> Reverse-engineered specification for Frontend V2 + Backend V2.
> This document is the single source of truth for recreating the entire project.

---

# Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Complete Folder Structure](#3-complete-folder-structure)
4. [Frontend V2 Architecture](#4-frontend-v2-architecture)
5. [Backend V2 Architecture](#5-backend-v2-architecture)
6. [File-by-File Documentation](#6-file-by-file-documentation)
7. [Function-Level Documentation](#7-function-level-documentation)
8. [Feature Documentation](#8-feature-documentation)
9. [Frontend ↔ Backend Interaction](#9-frontend--backend-interaction)
10. [API Documentation](#10-api-documentation)
11. [Database Documentation](#11-database-documentation)
12. [AI Architecture](#12-ai-architecture)
13. [Authentication & Authorization](#13-authentication--authorization)
14. [External Integrations](#14-external-integrations)
15. [Configuration](#15-configuration)
16. [Business Logic](#16-business-logic)
17. [Error Handling](#17-error-handling)
18. [Performance](#18-performance)
19. [Design Patterns](#19-design-patterns)
20. [Security Analysis](#20-security-analysis)
21. [Deployment](#21-deployment)
22. [Data Flow & Sequence Diagrams](#22-data-flow--sequence-diagrams)
23. [Recreation Guide](#23-recreation-guide)
24. [Improvement Suggestions](#24-improvement-suggestions)

---

# 1. Project Overview

## Purpose

The **Document AI Platform** is an enterprise-grade **Intelligent Document Processing (IDP)** system that automates the ingestion, classification, extraction, validation, and verification of documents using AI agents. It additionally supports a complete **Insurance Claim Processing** workflow where multiple specialized AI agents evaluate claims across integrity, medical, treatment, disability, and litigation dimensions.

## Problem Being Solved

Insurance companies, banks, and enterprises process thousands of documents daily — claim forms, medical reports, invoices, identity proofs, disability certificates, legal letters. Manual processing is:
- **Slow**: Human reviewers take 10-30 minutes per document
- **Error-prone**: Misread fields, missed fraud signals, inconsistent validation
- **Expensive**: Requires large teams of data entry operators and claim adjusters

This platform replaces manual processing with an AI-powered pipeline that:
1. Automatically classifies documents by type
2. Extracts structured data using OCR + LLM
3. Validates fields against business rules
4. Detects fraud via signature/face verification
5. Routes low-confidence documents to human reviewers
6. Processes insurance claims through 5 specialized AI agents
7. Generates structured reports with approval/rejection recommendations

## Target Users

| User Role | Activities |
|-----------|-----------|
| **Document Operators** | Upload documents, monitor processing status |
| **Data Quality Reviewers** | Review flagged documents, correct extracted data |
| **Claim Adjusters** | Create claims, upload supporting docs, review AI-generated reports |
| **System Administrators** | Configure templates, normalization rules, agent settings |
| **DevOps Engineers** | Deploy, monitor, scale the platform |

## Core Workflows

1. **Document Processing Pipeline**: Upload → Intake → Pre-Validate → Preprocess → Classify → Fraud Check → Extract → Validate → Auto-Verify → Review → Output
2. **Claim Processing Pipeline**: Create Claim → Upload Documents → OCR Extraction → 5-Agent Evaluation → Report Generation → Human Decision
3. **Template Management**: Generate extraction templates from sample documents using AI vision
4. **Settings Management**: Configure normalization rules, classification types, confidence thresholds

## Key Features

- Multi-format document upload (PDF, JPEG, PNG, WEBP, DOCX)
- Batch upload (up to 20 files)
- AI-powered document classification (11+ document types)
- OCR with word-level confidence scoring
- LLM-driven structured data extraction with template support
- KYC-specific fraud detection (document tampering)
- Signature verification using DINOv2 embeddings + Vision LLM
- Face photo verification with multi-agent morphological analysis
- Human-in-the-Loop (HITL) review with pipeline pause/resume
- Duplicate document detection
- Insurance claim processing with 5 specialized AI agents
- Configurable confidence thresholds and auto-approval
- Real-time status polling and toast notifications
- Dark/light theme support
- Collapsible sidebar navigation
- Responsive mobile-friendly layout
- OpenTelemetry tracing + Prometheus metrics
- Structured JSON logging
- Docker Compose deployment with PostgreSQL + Redis

## Technology Stack

### Frontend V2
| Technology | Purpose |
|-----------|---------|
| **React 19** | UI framework |
| **React Router 7** | Client-side routing |
| **Vite 8** | Build tool & dev server |
| **Axios** | HTTP client |
| **Lucide React** | Icon library |
| **Vanilla CSS** | Styling (tokens + components + animations + layout) |
| **Context API + useReducer** | State management |

### Backend V2
| Technology | Purpose |
|-----------|---------|
| **Python 3.12** | Runtime |
| **FastAPI** | Web framework |
| **SQLAlchemy 2.0** | ORM (async) |
| **SQLite / PostgreSQL** | Database |
| **Redis + arq** | Task queue for background processing |
| **Mistral AI SDK** | LLM, OCR, Vision providers |
| **Mistral Workflows SDK** | Managed cloud workflow orchestration |
| **PyMuPDF (fitz)** | PDF rendering |
| **Pillow / OpenCV** | Image preprocessing |
| **DINOv2 (PyTorch)** | Embedding model for signature/face verification |
| **Pydantic** | Request/response validation |
| **Alembic** | Database migrations |
| **OpenTelemetry** | Distributed tracing |
| **Prometheus** | Metrics |

## Design Philosophy

The platform was architectured with these principles:

1. **Provider Agnosticism**: All AI capabilities (LLM, OCR, Vision, Embedding, Storage) are accessed through abstract interfaces. Switching from Mistral to OpenAI requires only a config change — no code modifications.

2. **Pipeline-as-Code**: Document and claim processing flows are defined as ordered step sequences (`PipelineDefinition`), not hardcoded in a monolithic function. Steps can be conditionally skipped, timed out, or paused.

3. **Resilience First**: Every provider call goes through a `FallbackChain` with circuit breakers, automatic failover, and exponential backoff retries.

4. **Human-in-the-Loop Native**: The pipeline engine has first-class support for pausing execution and resuming after human input (duplicate decisions, manual review).

5. **Dual Execution Engines**: The same pipeline can execute either locally (via `PipelineEngine` + arq/Redis) or on Mistral's managed cloud (via Mistral Workflows SDK), controlled by a single config flag.

6. **Separation of Concerns**: Activities contain business logic, tools define LLM-callable functions, the pipeline engine handles orchestration, and providers handle vendor communication.

---

# 2. System Architecture

## High-Level Architecture

```mermaid
graph TB
    subgraph "Frontend V2 (React)"
        UI[React SPA<br/>Vite + React Router]
        Store[AppStore<br/>Context + useReducer]
        APIClient[API Client<br/>Axios]
    end

    subgraph "Backend V2 (FastAPI)"
        API[API Layer<br/>FastAPI Routers v1]
        Pipeline[Pipeline Engine<br/>Step Orchestration]
        Activities[Activities Layer<br/>Business Logic]
        AgentLoop[Agent Loop<br/>LLM Conversation]
        Registry[Provider Registry<br/>Singleton]
    end

    subgraph "Provider Layer"
        LLM[LLM Provider<br/>Mistral / OpenAI]
        OCR[OCR Provider<br/>Mistral OCR]
        Vision[Vision Provider<br/>Pixtral]
        Embed[Embedding Provider<br/>DINOv2]
        Storage[Storage Provider<br/>Local / S3]
    end

    subgraph "Resilience Layer"
        Fallback[Fallback Chains]
        CB[Circuit Breakers]
        Retry[Retry Policies]
        Health[Health Monitor]
    end

    subgraph "Data Layer"
        DB[(SQLite / PostgreSQL)]
        Redis[(Redis)]
        FileStore[File Storage<br/>./storage/]
    end

    subgraph "External Services"
        MistralAPI[Mistral AI API]
        MistralWorkflows[Mistral Workflows<br/>Managed Cloud]
        GoogleDocAI[Google Document AI]
    end

    UI --> Store
    UI --> APIClient
    APIClient -->|HTTP REST| API
    API --> Pipeline
    API -->|Enqueue| Redis
    Redis -->|Dequeue| Worker[arq Worker]
    Worker --> Pipeline
    Pipeline --> Activities
    Activities --> AgentLoop
    AgentLoop --> Registry
    Registry --> Fallback
    Fallback --> CB
    Fallback --> LLM
    Fallback --> OCR
    Fallback --> Vision
    Registry --> Embed
    Registry --> Storage
    Activities --> DB
    Pipeline --> DB
    LLM --> MistralAPI
    OCR --> MistralAPI
    Vision --> MistralAPI
    Worker -.->|Optional| MistralWorkflows
    Health --> Registry
```

## Component Communication Flow

```mermaid
graph LR
    A[User Browser] -->|HTTP| B[FastAPI App :8000]
    B -->|Enqueue Job| C[Redis :6379]
    C -->|Consume Job| D[arq Worker]
    D -->|Run Pipeline| E[PipelineEngine]
    E -->|Step 1-10| F[Activities]
    F -->|Tool Calls| G[LLM Provider]
    F -->|OCR| H[OCR Provider]
    F -->|Verify| I[DINOv2 + Vision]
    E -->|Checkpoint| J[(Database)]
    F -->|Save Results| J
    B -->|Poll Status| J
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Docker Compose"
        APP[app container<br/>FastAPI :8000]
        WORKER[worker container<br/>arq Worker]
        PG[postgres container<br/>PostgreSQL :5432]
        RD[redis container<br/>Redis :6379]
    end

    APP --> PG
    APP --> RD
    WORKER --> PG
    WORKER --> RD
    APP -.->|Shared Volume| FS[./storage]
    WORKER -.->|Shared Volume| FS
```

---

# 3. Complete Folder Structure

```
Document-AI/
├── frontend-v2/                    # React SPA (Vite)
│   ├── index.html                  # HTML entry point with SVG favicon
│   ├── package.json                # Dependencies: React 19, Axios, Lucide, React Router 7
│   ├── vite.config.js              # Vite configuration
│   ├── eslint.config.js            # ESLint configuration
│   ├── .env                        # VITE_API_BASE_URL
│   ├── public/                     # Static assets
│   ├── dist/                       # Production build output
│   └── src/
│       ├── main.jsx                # React entry: imports CSS design system, renders <App/>
│       ├── App.jsx                 # Router definition: 12 routes under AppShell
│       ├── App.css                 # App-level overrides
│       ├── index.css               # Root CSS resets
│       ├── api/
│       │   └── client.js           # Axios API client (30+ functions covering all endpoints)
│       ├── store/
│       │   └── AppStore.jsx        # Context + useReducer global state management
│       ├── hooks/
│       │   ├── useDocumentPoller.js # Polls /status every 2.5s until terminal state
│       │   └── useDocumentList.js   # Fetches and syncs document list to AppStore
│       ├── pages/
│       │   ├── Dashboard.jsx       # Overview with stats, charts, recent documents
│       │   ├── Upload.jsx          # Drag-and-drop + batch upload with progress
│       │   ├── Processing.jsx      # Real-time pipeline monitoring
│       │   ├── Extraction.jsx      # Side-by-side document preview + extracted data editor
│       │   ├── Validation.jsx      # Human review queue with approve/reject actions
│       │   ├── Documents.jsx       # Document list with search, filter, pagination
│       │   ├── Agents.jsx          # AI agent status and configuration
│       │   ├── Analytics.jsx       # Processing analytics and metrics
│       │   ├── Settings.jsx        # System configuration (thresholds, normalization, classification)
│       │   ├── Templates.jsx       # Template management with AI-powered generation
│       │   ├── ClaimProcess.jsx    # Claim creation and document upload workflow
│       │   ├── ClaimWorkflow.jsx   # Claim AI processing and report viewing
│       │   └── claimData.js        # Mock/seed data for claim workflows
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppShell.jsx    # Main layout: Sidebar + TopBar + Outlet + Toast
│       │   │   ├── Sidebar.jsx     # Collapsible navigation with sections and badges
│       │   │   └── TopBar.jsx      # Top bar with theme toggle, breadcrumbs, search
│       │   └── ui/
│       │       ├── ConfidenceBar.jsx    # Visual confidence percentage bar
│       │       ├── DonutChart.jsx       # SVG donut chart for dashboard stats
│       │       ├── Modal.jsx            # Reusable modal dialog
│       │       ├── PipelineSteps.jsx    # Pipeline step visualization
│       │       ├── RegionSelector.jsx   # Drag-to-select image regions (KYC boxes)
│       │       ├── StatCard.jsx         # Dashboard stat card with icon
│       │       ├── StatusBadge.jsx      # Color-coded status badges
│       │       └── ToastContainer.jsx   # Toast notification container
│       └── styles/
│           ├── tokens.css          # CSS design tokens (colors, spacing, typography, breakpoints)
│           ├── animations.css      # Keyframe animations (fade, slide, pulse, shimmer)
│           ├── layout.css          # Layout system (sidebar, main-wrapper, grid)
│           └── components.css      # All component styles (~82KB)
│
├── backend-v2/                     # FastAPI + Python 3.12
│   ├── main.py                     # FastAPI app entrypoint with lifespan management
│   ├── config.py                   # Pydantic Settings (env vars, agent IDs)
│   ├── worker.py                   # arq background worker (document + claim pipelines)
│   ├── logging_config.py           # Structured JSON logging configuration
│   ├── observability.py            # OpenTelemetry + Prometheus setup
│   ├── requirements.txt            # Python dependencies (~100 packages)
│   ├── Dockerfile                  # Python 3.12-slim container
│   ├── docker-compose.yml          # 4-service compose: app, worker, postgres, redis
│   ├── alembic.ini                 # Alembic migration configuration
│   ├── .env.example                # Template for environment variables
│   ├── .env                        # Active environment (not committed)
│   │
│   ├── config/
│   │   └── platform.yaml           # Master config: providers, chains, pipelines, CORS
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── queue.py                # Redis/arq connection pool factory
│   │   └── routers/
│   │       ├── __init__.py
│   │       └── v1/
│   │           ├── __init__.py     # Mounts all v1 routers under /api/v1
│   │           ├── documents.py    # Upload, status, extracted data, file, retry, delete
│   │           ├── claims.py       # Create, list, status, run workflow, report, decision
│   │           ├── workflow.py     # HITL resume endpoints (duplicate, review)
│   │           └── settings.py     # Normalization, classification, templates, agents
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py             # Async SQLAlchemy engine, session factory, init_db()
│   │   ├── models.py               # 8 ORM models (Document, Claim, ClaimReport, etc.)
│   │   ├── operations.py           # Document CRUD + pipeline checkpoint operations
│   │   └── claim_operations.py     # Claim CRUD, document linking, report persistence
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── documents.py            # Pydantic models for document API
│   │   └── claims.py               # Pydantic models for claim API
│   │
│   ├── platform_core/
│   │   ├── __init__.py
│   │   ├── config.py               # YAML config loader with ${ENV_VAR} resolution
│   │   ├── registry.py             # Singleton ProviderRegistry (LLM, OCR, Vision, etc.)
│   │   ├── agent_loop.py           # Reusable multi-turn agent conversation loop
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── interfaces.py       # Abstract base classes: LLMProvider, OCRProvider, etc.
│   │   │   ├── llm/                # LLM implementations (MistralLLM, etc.)
│   │   │   ├── ocr/                # OCR implementations (MistralOCR, etc.)
│   │   │   ├── vision/             # Vision implementations (MistralVision, etc.)
│   │   │   ├── embedding/          # Embedding implementations (DINOv2Embedding)
│   │   │   └── storage/            # Storage implementations (LocalStorage)
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # PipelineEngine: step orchestration, checkpoints, HITL
│   │   │   ├── definitions.py      # Document + Claim pipeline step sequences
│   │   │   ├── checkpoint.py       # CheckpointManager: persistence for crash recovery
│   │   │   └── mistral_workflow.py # Mistral Workflows SDK integration (alternative engine)
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          # PromptManager: loads .md prompt files
│   │   │   ├── classifier.md       # System prompt for classifier agent
│   │   │   ├── extractor.md        # System prompt for extractor agent
│   │   │   ├── validator.md        # System prompt for validator agent
│   │   │   ├── reviewer.md         # System prompt for reviewer agent
│   │   │   ├── intake.md           # System prompt for intake agent
│   │   │   ├── pre_validator.md    # System prompt for pre-validator agent
│   │   │   ├── preprocessor.md     # System prompt for preprocessor agent
│   │   │   ├── fraud_checker.md    # System prompt for fraud checker agent
│   │   │   ├── auto_verifier.md    # System prompt for auto-verifier agent
│   │   │   ├── output.md           # System prompt for output agent
│   │   │   ├── claim_integrity.md  # System prompt for claim integrity agent
│   │   │   ├── claim_medical.md    # System prompt for claim medical agent
│   │   │   ├── claim_treatment.md  # System prompt for claim treatment agent
│   │   │   ├── claim_disability.md # System prompt for claim disability agent
│   │   │   ├── claim_litigation.md # System prompt for claim litigation agent
│   │   │   ├── claim_report.md     # System prompt for claim report agent
│   │   │   ├── signature_vision.md # System prompt for signature vision agent
│   │   │   ├── signature_judge.md  # System prompt for signature judge agent
│   │   │   ├── face_morphology1.md # System prompt for face morphology part 1
│   │   │   ├── face_morphology2.md # System prompt for face morphology part 2
│   │   │   ├── face_age.md         # System prompt for face age variation agent
│   │   │   └── face_judge.md       # System prompt for face judge agent
│   │   ├── isolation/
│   │   │   ├── __init__.py
│   │   │   └── sandbox.py          # StepSandbox: scoped provider access per step
│   │   └── resilience/
│   │       ├── __init__.py
│   │       ├── circuit_breaker.py  # CircuitBreaker: CLOSED → OPEN → HALF_OPEN
│   │       ├── fallback.py         # FallbackChain: tries providers in order
│   │       ├── retry.py            # RetryPolicy: exponential backoff + jitter
│   │       └── health.py           # HealthMonitor: background provider health checks
│   │
│   ├── activities/                 # Business logic for each pipeline step
│   │   ├── __init__.py
│   │   ├── intake.py               # Duplicate detection
│   │   ├── pre_validator.py        # Image quality checks
│   │   ├── preprocessor.py         # Skew/brightness/noise correction
│   │   ├── classifier.py           # Document type classification
│   │   ├── fraud_checker.py        # KYC fraud detection
│   │   ├── extractor.py            # OCR + LLM field extraction
│   │   ├── validator.py            # Field validation
│   │   ├── auto_verifier.py        # Signature + face verification coordinator
│   │   ├── reviewer.py             # Confidence-based review routing
│   │   ├── output.py               # Final result persistence
│   │   ├── claim_integrity.py      # Claim completeness validation
│   │   ├── claim_medical.py        # Medical record validation
│   │   ├── claim_treatment.py      # Treatment-diagnosis alignment
│   │   ├── claim_disability.py     # Disability certificate validation
│   │   └── claim_litigation.py     # Litigation/fraud detection
│   │
│   ├── tools/                      # LLM-callable tool definitions
│   │   ├── __init__.py
│   │   ├── classifier.py           # get_supported_document_types, get_document_text
│   │   ├── extractor.py            # extract_text_from_document, crop_kyc_images
│   │   ├── validator.py            # validate_field_value
│   │   ├── reviewer.py             # get_review_status
│   │   ├── intake.py               # check_duplicate
│   │   ├── pre_validator.py        # check_image_quality
│   │   ├── preprocessor.py         # preprocess_image
│   │   ├── fraud_checker.py        # check_document_fraud
│   │   ├── auto_verifier.py        # find_customer_reference, verify_signature, verify_face
│   │   ├── output.py               # save_final_output
│   │   └── claim_tools.py          # fetch_claim_documents, fetch_claimant_history, etc.
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── file_handler.py         # File save + hash + base64 utilities
│   │   ├── ocr.py                  # OCR provider wrapper (Mistral OCR)
│   │   ├── preprocessor.py         # OpenCV image preprocessing pipeline
│   │   ├── norm_config.py          # Normalization config load/save
│   │   ├── classification_config.py # Classification types config
│   │   ├── templates.py            # Template load/save/generate
│   │   ├── signature_extractor.py  # Signature crop extraction
│   │   ├── signature_verifier.py   # DINOv2 + Vision signature verification
│   │   ├── face_verifier.py        # Multi-agent face verification pipeline
│   │   └── perf_logger.py          # Performance logging utilities
│   │
│   ├── storage/                    # File storage directory
│   │   ├── crops/                  # Cropped signature/photo images
│   │   ├── ocr_blocks/             # OCR bounding box JSON files
│   │   └── preprocessed/           # Preprocessed document images
│   │
│   ├── migrations/                 # Alembic migration scripts
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │
│   ├── tests/
│   │   └── load/                   # Load testing scripts
│   │
│   └── archive/                    # Legacy/reference code
│       ├── agents_config.py        # Agent creation scripts for Mistral Studio
│       ├── claim_workflow.py       # Legacy claim workflow (pre-pipeline)
│       ├── create_or_update_agents.py
│       └── workflow.py             # Legacy document workflow (pre-pipeline)
```

### Folder Responsibilities

| Folder | Purpose | Interacts With |
|--------|---------|---------------|
| `api/routers/v1/` | HTTP endpoints, request validation, response formatting | `db/`, `platform_core/pipeline/`, `schemas/` |
| `platform_core/` | Core platform abstractions — providers, pipelines, resilience | Everything |
| `platform_core/pipeline/` | Pipeline orchestration engine with checkpointing | `activities/`, `db/`, `platform_core/resilience/` |
| `platform_core/providers/` | Vendor-agnostic provider implementations | External APIs (Mistral, etc.) |
| `platform_core/resilience/` | Circuit breakers, fallback chains, retries, health checks | `platform_core/providers/` |
| `platform_core/prompts/` | System prompt management (markdown files) | `activities/` |
| `activities/` | Business logic for each pipeline step | `tools/`, `db/`, `platform_core/` |
| `tools/` | LLM-callable function definitions and implementations | `utils/`, `db/` |
| `utils/` | Low-level utilities (OCR, preprocessing, verification) | External libraries (PyMuPDF, OpenCV, DINOv2) |
| `db/` | Database models, session management, CRUD operations | SQLAlchemy, SQLite/PostgreSQL |
| `schemas/` | Pydantic request/response models | `api/routers/` |
| `config/` | Platform YAML configuration | `platform_core/config.py` |

---

# 4. Frontend V2 Architecture

> **This section was verified line-by-line against the actual `frontend-v2/src` source in this repository (2026-07-28) so that rebuilding from this document reproduces the same UI.** Where the original spec's assumptions were wrong (e.g. dark-as-default theme, generic page descriptions), they are corrected below and called out explicitly.

## Routing

React Router 7 (`react-router-dom` `^7.15.1`) via `createBrowserRouter` + `<RouterProvider>`. A single top-level route (`/`) renders `<AppShell />`; every page is a nested child rendered through `<Outlet />`. `App.jsx` wraps the router in `<AppProvider>` (the AppStore context provider).

| Path | Component | Sidebar Entry | Notes |
|------|-----------|----------------|-------|
| `/` (index) | `Dashboard` | Main → Dashboard | |
| `/upload` | `Upload` | Main → Upload | |
| `/processing` | `Processing` | Main → Processing | |
| `/extraction` | `Extraction` | Data → Extraction | |
| `/validation` | `Validation` | Data → Validation | |
| `/documents` | `Documents` | Data → Documents | |
| `/agents` | `Agents` | Intelligence → Agents | |
| `/analytics` | `Analytics` | Intelligence → Analytics | |
| `/templates` | `Templates` | Intelligence → Templates | |
| `/settings` | `Settings` | System → Settings | |
| `/claim-process` | `ClaimProcess` | Claims → Claim Process | |
| `/claim-workflow` | `ClaimWorkflow` | **None** | Reached only by navigating from ClaimProcess (`/claim-workflow?claim_id=...`, optionally `&view_report=1`) — it has no sidebar link |

12 routes total, but **only 11 appear in the sidebar** — `ClaimWorkflow` is a detail view, not a nav destination. Getting this wrong (adding a "Claim Workflow" sidebar item) is a common source of UI drift from the real app.

## Sidebar (`components/layout/Sidebar.jsx`)

Five nav sections, in this exact order, each item as `label — lucide-react icon — path`:

| Section | Items |
|---|---|
| **Main** | Dashboard — `LayoutDashboard` — `/` · Upload — `Upload` — `/upload` · Processing — `Cpu` — `/processing` |
| **Data** | Extraction — `FileSearch` — `/extraction` · Validation — `CheckCircle` — `/validation` · Documents — `FileText` — `/documents` |
| **Intelligence** | Agents — `Bot` — `/agents` · Analytics — `BarChart2` — `/analytics` · Templates — `FileCode` — `/templates` |
| **Claims** | Claim Process — `ClipboardList` — `/claim-process` |
| **System** | Settings — `Settings` — `/settings` |

- **Badges**: "Validation" shows `reviewDocs.length` (docs with status `awaiting_review`/`duplicate`); "Processing" shows `pendingDocs.length`. No other item ever shows a badge.
- **Collapse**: toggled by a `ChevronLeft`/`ChevronRight` button, persisted to `localStorage['sidebar-collapsed']` (`'true'`/`'false'`). Expanded width `220px` (`--sidebar-w`), collapsed `64px` (`--sidebar-collapsed-w`).
- **Mobile (< 768px)**: sidebar becomes a fixed off-canvas drawer (class `.mobile-open`) with a dimming `.sidebar-overlay`, opened by the TopBar hamburger; auto-closes on route change and on Escape.
- **Logo block**: inline 20×20 SVG mark + two-line wordmark "Intelligent Document" / "Processing" + tagline "IDP Platform · v2.0".
- **Footer**: static text "10 Agents Active" / "All systems nominal" with a pulsing dot — this is hardcoded, **not** derived from the live agent count.

## TopBar (`components/layout/TopBar.jsx`)

- Per-route breadcrumb title/sub from a static `PAGE_META` map: `/` → "Dashboard" / "Overview & live stats", `/upload` → "Upload" / "Add documents to the pipeline", `/processing` → "Processing" / "Live workflow orchestration", `/extraction` → "Extraction" / "AI-extracted structured data", `/validation` → "Validation" / "Human review queue", `/documents` → "Documents" / "All processed files", `/agents` → "Agents" / "Multi-agent system overview", `/analytics` → "Analytics" / "Processing metrics & trends", `/settings` → "Settings" / "Configure system preferences". Routes **not** in this map (`/templates`, `/claim-process`, `/claim-workflow`) fall back to the generic title "IDP Platform" with an empty subtitle — a known gap in the real app, not an oversight to "fix" when recreating it.
- A spinning "syncing" indicator shows while `useDocumentList().loading` is true.
- **Theme toggle** (`Sun` when dark / `Moon` when light) writes `document.documentElement.dataset.theme` and persists to `localStorage['idp-theme']`. `getInitialTheme()`/`applyTheme()` are exported and also called once at module load in `AppShell.jsx` (before first paint) to avoid a flash of the wrong theme; default follows OS `prefers-color-scheme` if nothing is stored.
- **Notification bell** shows a dot badge when `reviewDocs.length > 0`; click opens a dropdown listing up to 5 pending-review documents (each click navigates to `/validation`), with a "View all N →" row if there are more than 5.
- **User avatar**: a styled circle with a `User` icon — decorative only, not a functional menu (there is no authentication in this app; see Section 13).

## Component Hierarchy

```mermaid
graph TB
    App["App<br/>createBrowserRouter + AppProvider"]
    Shell["AppShell<br/>Layout wrapper"]
    SB["Sidebar<br/>5 sections, collapsible, mobile drawer"]
    TB["TopBar<br/>Theme toggle + breadcrumb + notifications"]
    Toast["ToastContainer"]
    Outlet["Outlet"]

    App --> Shell
    Shell --> SB
    Shell --> TB
    Shell --> Outlet
    Shell --> Toast

    Outlet --> Dashboard
    Outlet --> Upload
    Outlet --> Processing
    Outlet --> Extraction
    Outlet --> Validation
    Outlet --> Documents
    Outlet --> Agents
    Outlet --> Analytics
    Outlet --> Templates
    Outlet --> Settings
    Outlet --> ClaimProcess
    Outlet --> ClaimWorkflow
```

`AppShell.jsx`'s exact JSX (order matters for CSS/z-index — reproduce verbatim):
```jsx
<>
  <Sidebar mobileOpen={mobileOpen} onMobileClose={closeMobile} />
  <div className="main-wrapper">
    <TopBar onMobileMenuToggle={openMobile} />
    <main className="main-content"><Outlet /></main>
    <div className="sunset-stripe" aria-hidden="true" />
  </div>
  <ToastContainer />
</>
```

## Layout System

- `#root { display:flex; height:100vh; overflow:hidden }` — sidebar + `.main-wrapper` as a flex row.
- `.main-wrapper { flex:1; display:flex; flex-direction:column; min-width:0; overflow:hidden }`.
- `.main-content { flex:1; overflow-y:auto; padding:24px }` (16px under 768px).
- `.topbar { height:60px (--topbar-h); position:sticky; top:0; backdrop-filter:blur(16px) }`.
- Responsive breakpoints: `1100px` (stat/grid rows collapse to 2 columns), `800px` (3-col grids → 2-col), `768px` (sidebar becomes the off-canvas drawer described above, hamburger appears), `600px` (grids collapse further to 1–2 columns).

## Design System

Four CSS files, loaded in this **exact order** by `main.jsx` — order matters because later files override earlier ones and nothing is scoped/modularized:

```js
import './styles/tokens.css'
import './styles/animations.css'
import './styles/layout.css'
import './styles/components.css'
import App from './App.jsx'
```

1. **`tokens.css`** (290 lines) — design tokens, font imports, both theme palettes.
2. **`animations.css`** (169 lines) — keyframes + animation utility classes.
3. **`layout.css`** (341 lines) — sidebar/topbar dimensions, `.main-wrapper`, grid utilities, responsive rules.
4. **`components.css`** (2222 lines) — every card/button/form/table/badge/modal/chart/page-specific style.

Two other CSS files exist but are **not part of the design system and should not be recreated as if they mattered**: `index.css` is intentionally near-empty (`body { margin: 0 }` — its own comment says imports are handled in `main.jsx`) and is not even imported by `main.jsx`; `App.css` is unused leftover `create-vite` scaffold CSS (`.hero`, `#docs`, `.ticks`, etc.) targeting markup that no longer exists in the app.

**Fonts** (Google Fonts `@import` in `tokens.css`): `Playfair Display` (serif — weights 400/500/700 + italic 400 — used for display headings via `.font-display`), `Inter` (variable weight — primary UI font, `--font-ui`), `JetBrains Mono` (`--font-mono` — code/JSON blocks). This 3-font pairing is a specific, deliberate choice — substituting generic system fonts will visibly change the app's character (the serif display font in particular is used for hero numbers/titles).

**Theme model — corrected from the original spec**: **Light is the default theme** (`:root` selector), a warm palette internally named "Mistral Warm Sunset." Dark mode is the override, selected via `[data-theme="dark"]`. There is **no** `[data-theme="light"]` block — light IS `:root`. (The original version of this document incorrectly assumed dark-as-default; that produced a visibly wrong color scheme when rebuilt.)

Key token values (light `:root` / dark `[data-theme="dark"]`):

| Token | Light | Dark |
|---|---|---|
| `--bg` | `#fffaeb` | `#110a00` |
| `--surface` | `#ffffff` | `#1a1008` |
| `--card` | `#ffffff` | `#1e1306` |
| `--border` | `#e6d5a8` | `#3a2810` |
| `--text` | `#1f1f1f` | `#f5e8d0` |
| `--text-dim` | `#4a4a4a` | `#b8956a` |
| `--muted` | `#8a8a8a` | `#7a6040` |
| `--accent` (brand) | `#fa520f` | `#fb6b2d` |
| `--accent-hover` | `#cc3a05` | `#fa520f` |
| `--accent2` | `#ff8105` | `#ff9420` |
| `--accent3` | `#ffb83e` | `#ffc14a` |
| `--accent4` | `#ffd900` | `#ffe050` |
| `--success` | `#10b981` | `#10b981` |
| `--warn` | `#f59e0b` | `#fbbf24` |
| `--danger` | `#ef4444` | `#f87171` |
| `--info` | `#3b82f6` | `#60a5fa` |
| `--grad-brand` | `linear-gradient(135deg,#fa520f 0%,#ff8105 100%)` | `linear-gradient(135deg,#fb6b2d 0%,#ff9420 100%)` |
| `--grad-sunset` | `linear-gradient(90deg,#fa520f 0%,#ffa110 30%,#ffb83e 60%,#ffd900 80%,#fff8e0 100%)` | same |

Layout tokens (theme-independent): `--sidebar-w: 220px`, `--sidebar-collapsed-w: 64px`, `--topbar-h: 60px`, `--radius: 12px`, `--radius-sm: 8px`, `--radius-lg: 16px`, `--radius-xl: 20px`. Base font size `14px` on `<html>`. Motion: `--dur: 160ms`, `--dur-md: 240ms`, `--dur-lg: 360ms` with `cubic-bezier` easing curves.

Keyframes defined in `animations.css`: `border-rotate`, `pulse`, `ping`, `spin`, `shimmer`, `shimmer-line`, `slide-in`, `slide-right`, `slide-up`, `fade-in`, `toast-in`, `progress-fill`, `glow-pulse`, `float`, `nav-indicator-in`, `count-pop`, plus a `prefers-reduced-motion: reduce` block that collapses every animation/transition to `0.01ms`.

## State Management

Context API + `useReducer` in `store/AppStore.jsx`.

### State Shape (exact defaults)
```javascript
{
  documents: [],
  activeDocId: null,
  pollingIds: new Set(),
  toasts: [],
  loading: false,
  confidenceMode: localStorage.getItem('idp-confidence-mode') || 'word',  // 'word' | 'page' | 'both'
  fieldHighlightThreshold: 95,   // localStorage key 'idp-field-highlight-threshold'
  autoApproveThreshold: 80,      // localStorage key 'idp-auto-approve-threshold'
  confHighThreshold: 90,         // localStorage key 'idp-conf-high-threshold'
  confMedThreshold: 70,          // localStorage key 'idp-conf-med-threshold'
}
```
(`confidenceMode` supports a third value, `'both'`, not just `'word'`/`'field'` as previously documented — see Settings page below.)

### Reducer Actions (exact type strings)
`SET_DOCUMENTS`, `ADD_DOCUMENT`, `UPDATE_DOCUMENT`, `REMOVE_DOCUMENT`, `SET_ACTIVE_DOC`, `ADD_POLLING`, `REMOVE_POLLING`, `ADD_TOAST`, `REMOVE_TOAST`, `SET_LOADING`, `SET_CONFIDENCE_MODE`, `SET_FIELD_HIGHLIGHT_THRESHOLD`, `SET_AUTO_APPROVE_THRESHOLD`, `SET_CONF_HIGH_THRESHOLD`, `SET_CONF_MED_THRESHOLD`.

### Exposed API (`useApp()` — throws `Error('useApp must be inside AppProvider')` if used outside `<AppProvider>`)
`setDocuments`, `addDocument`, `updateDocument`, `removeDocument`, `setActiveDoc`, `addPolling`, `removePolling`, `toast(msg, type='info', duration=4000)` (module-level incrementing id, auto-dismisses via `setTimeout`), `dismissToast(id)`, `setConfidenceMode`, `setFieldHighlightThreshold`, `setAutoApproveThreshold`, `setConfHighThreshold`, `setConfMedThreshold`.

### Derived State (recomputed every render, not stored in reducer state)
```js
pendingDocs   = documents.filter(d => ['pending','pre_validating','processing','preprocessing','classifying','fraud_checking','extracting','validating'].includes(d.status))
reviewDocs    = documents.filter(d => ['awaiting_review','duplicate'].includes(d.status))
completedDocs = documents.filter(d => d.status === 'completed')
```

Only the 5 threshold/mode fields persist to `localStorage`; `documents`, `toasts`, and `pollingIds` are session-only.

## API Integration

`src/api/client.js` — Axios instance, base URL `import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'`, 30s default timeout (longer per-call overrides: 300s for batch upload, 120s for template generation / signature verification / claim document upload). A response interceptor normalizes every error to `err.response.data.detail || err.response.data.message || err.message`.

**Exactly 30 exported functions** (not "30+"):

| Function | Method + Path |
|---|---|
| `uploadDocument(file, onProgress)` | `POST /documents/upload` |
| `uploadDocumentsBatch(files, onProgress)` | `POST /documents/upload/batch` |
| `getStatus(documentId)` | `GET /documents/{id}/status` |
| `listDocuments(page=1, limit=50)` | `GET /documents` |
| `getExtractedData(documentId)` | `GET /documents/{id}/extracted` |
| `updateExtractedData(documentId, validatedData)` | `PUT /documents/{id}/extracted` |
| `resumeDuplicate(workflowRunId, override)` | `POST /workflow/{id}/resume/duplicate` |
| `resumeReview(workflowRunId, approved, corrections, rejectionReason)` | `POST /workflow/{id}/resume/review` |
| `getAgents()` | `GET /agents` |
| `deleteDocument(documentId)` | `DELETE /documents/{id}` |
| `getDocumentFileUrl(documentId)` | URL builder only → `/documents/{id}/file` |
| `getOcrBlocks(documentId)` | `GET /documents/{id}/ocr-blocks` |
| `getTemplates()` | `GET /templates` |
| `saveTemplates(templatesData)` | `PUT /templates` |
| `generateTemplateFromSample(name, file, isKyc, kycBoxes)` | `POST /templates/generate` |
| `deleteTemplate(name)` | `DELETE /templates/{name}` |
| `getCropUrl(documentId, filename)` | URL builder only → `/documents/{id}/crops/{filename}` |
| `verifySignature(documentId, referenceFile, verificationType='signature')` | `POST /documents/{id}/verify-signature` |
| `getNormConfig()` | `GET /settings/normalization` |
| `saveNormConfig(config)` | `PUT /settings/normalization` |
| `getClassificationConfig()` | `GET /settings/classification` |
| `saveClassificationConfig(docTypes)` | `PUT /settings/classification` |
| `createClaim(payload)` | `POST /claims` |
| `listClaims()` | `GET /claims` |
| `getClaimStatus(claimId)` | `GET /claims/{id}/status` |
| `runClaimWorkflow(claimId)` | `POST /claims/{id}/run` |
| `getClaimReport(claimId)` | `GET /claims/{id}/report` |
| `submitClaimDecision(claimId, decision, notes='')` | `POST /claims/{id}/decision` |
| `deleteClaim(claimId)` | `DELETE /claims/{id}` |
| `uploadClaimDocument(claimId, file, docType, onProgress)` | `POST /documents/upload?claim_id&doc_type` |

### Custom Hooks

- **`useDocumentPoller(documentId)`** — on mount, registers via `addPolling(documentId)`, then polls `getStatus` every **2500ms**, pushing results into AppStore via `updateDocument`. Fires a toast only on a status *transition* (not on every poll): `completed` → success "Document processed successfully!"; `awaiting_review` → warn "Document needs human review."; `rejected` → error with the rejection reason; `error` → error with the message. Stops and calls `removePolling` at terminal statuses (`completed`, `rejected`, `error`, `deleted`). On a failed request it does **not** exponentially back off — it retries once at a fixed `2500ms × 2 = 5000ms`, then returns to normal cadence on the next successful poll. Returns nothing; it's a pure side-effect hook.
- **`useDocumentList()`** — `refresh(page=1, limit=100)` calls `listDocuments`, writes results into AppStore via `setDocuments`, toasts on failure. No internal interval — callers (Dashboard, Analytics) set up their own `setInterval`. Returns `{ refresh, loading, error }`.

## Reusable UI Components (`components/ui/`)

| Component | Props | Behavior |
|---|---|---|
| `ConfidenceBar` | `label`, `value` (0–1), `color?` | Labeled bar; auto-colors green ≥90%, amber ≥70%, else red, unless `color` overrides |
| `DonutChart` | `data: {label,value}[]` | Canvas-drawn donut (120×120), 7-color fixed palette cycling by index, center total, legend list; shows a "No data yet" empty state when total is 0 |
| `Modal` | `title`, `subtitle?`, `onClose?`, `children`, `footer?`, `wide?` | Overlay dialog, click-outside-to-close (only if `onClose` given), scrollable body capped at 70vh |
| `PipelineSteps` | `status` (document status string) | 8-node tracker: Intake → Pre-Validate → Preprocess → Classify → Extract → Validate → Review → Output, each step `done`/`running`/pending based on a status→index map |
| `RegionSelector` | `imageUrl`, `regions: {signature,photo}`, `onChange` | Percentage-based drag-to-draw box selector (min 2% w/h) for marking KYC signature/photo regions before template generation |
| `StatCard` | `icon`, `iconVariant?`, `label`, `value`, `unit?`, `delta?`, `deltaType?` | Icon chip + label + big value + optional delta with trend icon |
| `StatusBadge` | `status` | Maps 14 known document statuses (+ gray fallback) to a label/color-class/icon — see table below |
| `ToastContainer` | — (reads AppStore) | Renders `toasts`, icon per type (`success`/`error`/`warn`/`info`), dismiss button |

`StatusBadge` status map (exact): `pending`→"Pending" gray · `pre_validating`→"Pre-Validating" cyan (`Shield`) · `preprocessing`→"Preprocessing" purple (`Wand2`) · `processing`→"Intake" blue (`Upload`) · `classifying`→"Classifying" blue (`Bot`) · `fraud_checking`→"Fraud Checking" blue (`Shield`) · `extracting`→"Extracting" blue (`FileSearch`) · `validating`→"Validating" blue (`CheckCircle`) · `awaiting_review`→"Needs Review" yellow (`AlertTriangle`) · `duplicate`→"Duplicate" yellow (`AlertTriangle`) · `completed`→"Completed" green (`Check`) · `rejected`→"Rejected" red (`X`) · `failed`→"Failed" red (`AlertCircle`) · `error`→"Error" red (`AlertCircle`) · `deleted`→"Deleted" gray.

## Pages — Exact Content

*Each page's real headings, sections, and behavior — the previous one-line-per-page summary undershot enough detail to reproduce the actual UI. Reference implementation: `frontend-v2/src/pages/*.jsx`.*

### `/` — Dashboard (300 lines)
Hero eyebrow "IDP Platform · v2.0", live-computed title (`"{n} document(s) processed"`) and subtitle (`"{success%} success · {n} pending review · {n} errors"`). Sections: **Recent Documents** table (click row → `/extraction`), **Document Types** `DonutChart`, **Active Pipeline** (only rendered while a document is mid-processing — shows `PipelineSteps` + a pulsing "Live" chip), **Processing Status Breakdown** (4 `ConfidenceBar` rows: Completed/In Review/Processing/Errors), **Recent Activity** feed (last 8 docs, clickable). 4 `StatCard`s: Total Documents, Success Rate, Pending Review, Errors. Polls/refreshes every 10s via `setInterval`.

### `/upload` — Upload (569 lines)
No `<h1>` — the dropzone itself is the hero: "Drag & drop documents here or **browse files**" + description + a "Batch Ingestion Mode (Up to 20 files) · Concurrently Processed via Mistral AI" badge strip. Accepts PDF/JPG/PNG/WEBP/DOCX, hard cap `MAX_BATCH = 20`. On file selection, an **Upload Queue** card appears (per-file rows, batch progress bar with %, "Send N File(s) as Batch to AI Pipeline" button), followed post-upload by a **Batch Result** card (Submitted/Failed/Total stats, "View Processing →" / "Back to Dashboard" / conditional "Retry N Failed" buttons). When the queue is empty, a static **AI Processing Pipeline** info card lists the 6 stages: Intake, Classify, Extract, Validate, Review, Output (each with a one-line description). Uses `uploadDocumentsBatch`; mounts one `useDocumentPoller` per successfully uploaded id.

### `/processing` — Processing (200 lines)
**Live Processing Pipeline** card — `PipelineSteps` for the current "featured" active document, with an empty state ("No active processing… Upload Documents" button) when nothing is running. **Processing Queue** table — only pending/in-flight docs, with a "Refresh" button. **All Documents** mini table — first 10 documents with a "Full List →" link to `/documents`. Rejection/error/failed rows use an `ExpandableReason` component (80-char truncation + "Show more"/"Show less").

### `/extraction` — Extraction (2076 lines, the most complex page)
Document tabs across `completedDocs` (up to 8). Two-column **sticky** layout: **left** = `DocumentViewer` (PDF via `<object>`/iframe fallback, image, or unsupported-file placeholder; for images, a `<canvas>` overlay draws blue OCR bounding-box highlights for whichever field is currently hovered) plus a confidence banner (green "High Confidence" / amber "Review Recommended"); **right** = **Extracted Data** panel with Edit Fields / Copy JSON / Export actions, fields auto-grouped into collapsible sections (Vendor, Billing, Financial, Header, Other — grouped by key-name heuristics), and a **Raw Extraction (OCR)** JSON dump. For KYC documents, an **Identity Verification** section adds signature/photo crop cards with drag-drop reference-image upload and full forensic verdict panels: `SignatureVerdictPanel` (DINOv2 + LLM combined score, 5-dimension structural analysis, 4-dimension spatial analysis, 5 authenticity flags, unique-feature notes) and `FaceVerdictPanel` (3-module: geometry/eyes/nose, mouth/ears/jaw, age-variation analysis, plus a final accept/review/reject recommendation). A "full-screen" toggle expands the document viewer over the whole page. Table-shaped and array-shaped fields get specialized inline editors (add/remove row, add/remove chip) when editing.

### `/validation` — Validation (652 lines)
**Pending Human Review** — one `ReviewCard` per `reviewDocs` entry, each showing up to 8 extracted key/value pairs and action buttons: Approve / Reject / Edit & Approve (or Override Duplicate / Reject for duplicate-flagged docs). Reject opens a confirmation modal with an optional reason textarea. Edit & Approve opens `InlineCorrectionsEditor` — tracks only changed fields, shows a "reset" affordance per changed field and an "Original: {value}" hint. Empty state: "All clear! No documents are currently awaiting review." Sidebar cards: static **Validation Rules** checklist (4 rules) and a **How Review Works** explainer.

### `/documents` — Documents (206 lines)
Single card "All Documents", status filter pill bar (`all/pending/processing/awaiting_review/completed/rejected/failed/error`, each showing a live count), paginated table (20/page: `LIMIT=20`) with filename (click → `/extraction`) / type / status / truncated id / delete action (native `confirm()` + per-row spinner). Expandable long error/rejection reasons.

### `/agents` — Agents (462 lines)
Live-fetched (`GET /agents`) grid of `AgentCard`s (step badge, icon, name/role/description, tools rendered as `λ tool_name()`, and — for real Mistral agents — a deep link to the Mistral Studio playground). A skeleton grid shows while loading. Bottom section: **Agent Collaboration Graph** — a vertical 10-node pipeline built dynamically from whichever agent keys the backend actually returns (Intake → Pre-Validate → Preprocess(conditional) → Classify → Fraud Check(conditional, "KYC Only") → extractor group(conditional fan-out) → Validate → Auto-Verify(conditional, "KYC Only") → Review("‖ Human Review" tag) → Output).

### `/analytics` — Analytics (119 lines)
4 `StatCard`s (Total Documents, Success Rate %, Rejection Rate %, In Pipeline), side-by-side **Document Types** `DonutChart` and **Status Distribution** local bar chart, and a **Performance Breakdown** card with 4 `ConfidenceBar` rows (Success/Rejection/Review/Error rate). Everything is derived client-side from `documents` already in the store — there is no dedicated analytics API endpoint.

### `/templates` — Templates (835 lines)
Per-document-type tabs (label = Title-Cased key + " Template", KYC types get a "KYC" chip). Header stat pills: Total/Required/Optional field counts, "Create Template" button. Fields table (Field Name/Key, Type, Description, Highlight Threshold, Required, Actions) with a live search filter. **Add/Edit Extraction Field** modal: field key (snake_case validated, locked once editing), display label, data type select (`Text`/`Number`/`Date`/`Boolean`/`Array of Text`/`Array of Objects`), description, custom highlight threshold override, required checkbox. **Create Template from Sample Document** modal: template name, "KYC Identity Document" checkbox, sample file dropzone, and — only for KYC + image samples — a `RegionSelector` panel to draw signature/photo regions before calling `generateTemplateFromSample`.

### `/settings` — Settings (1124 lines)
`<h1>` "Settings" + "Reset defaults" button. Left nav, 4 sections (`NAV`, exact labels): **Confidence Scores** ("Granularity & display mode" — toggle cards for word-wise / page-wise, both can be active simultaneously — `confidenceMode` supports `'word' | 'page' | 'both'`), **Thresholds** ("Highlight & approval limits" — Auto-Approve Threshold slider [50–100, presets 70/75/80/85/90], Field Value Highlight slider [50–100, presets 80/85/90/95/100], High/Medium confidence-badge-color sliders with cross-validation that High > Medium), **Normalization Format** ("Date, number & name rules" — date format picker [ISO/US/EU/Keep Raw], number format [float/integer/string], name casing [Title/UPPER/Keep Raw], name order [6 options], custom rules textarea, live prompt preview — persisted via `/settings/normalization`, independent of AppStore), **Classification Types** ("Supported document types" — add/remove doc types with snake_case normalization, persisted via `/settings/classification`; default/reset list of 11: `invoice, pan_card, claim_form, policy_document, id_proof, medical_report, lab_reports, prescription_records, bills_invoices, disability_certificate, legal_letter`).

### `/claim-process` — Claim Process (574 lines)
Chip "Claims Dashboard", title "Claim Approval **Requests**" (gradient-styled word), "+ Create New Request" button. 4 stat tiles: Total Claims, Pending/Ready, Processing, Total Value (compact currency ₹). Claim cards (avatar, name, claim ID, priority dot, `{claim_type} · Policy {number} · {date}`, status pill with 14 status→label/icon mappings, expand/delete/process/view-report actions). Expanded panel lists per-document extraction status ("Documents (N/M extracted)"). **Create New Claim Request** modal: claimant name, priority select (Low/Medium/High/Urgent), description textarea, multi-file drag-drop upload (no manual doc-type picker — classification happens automatically server-side). Polls the claim list every **6000ms** while any claim is mid-pipeline, and the expanded claim's status every **5000ms**. This page does **not** use AppStore — it's entirely local component state.

### `/claim-workflow` — Claim Workflow (806 lines, no sidebar entry)
Reached via `?claim_id=...` (optionally `&view_report=1` to view a finished report directly). Renders the live 6-agent pipeline as a node graph (Claim Integrity → Medical Check → Treatment Review → Disability Check → Litigation Scan → Report Generation) with running/completed/waiting states and animated connectors, plus an **Agent Inspector** panel with 3 tabs (Agent Thought, Output, Metadata) and a step-jump dropdown. Polls claim status every **4000ms** until terminal. On completion, renders a **Claim Analysis Complete** summary: overall status badge (Approve/green, Reject/red, "Review Before Approval"/amber), an **Agent Results** accordion (PASS/FAIL/FLAG per agent), an **AI Suggestion** box, and an **Adjuster Decision** panel (Accept Claim / Reject Claim buttons → `submitClaimDecision`). This page also does not use AppStore. Note: it imports `INITIAL_STEPS`/`stepDuration` from `pages/claimData.js`, but those are unused mock/demo data left over from an earlier prototype — the real UI is entirely driven by live API responses (`getClaimStatus`, `getClaimReport`); do not recreate the fake step timings/output when rebuilding this page.

---

# 5. Backend V2 Architecture

## Layered Architecture

```mermaid
graph TB
    subgraph "Layer 0: API"
        R1[documents.py]
        R2[claims.py]
        R3[workflow.py]
        R4[settings.py]
    end
    
    subgraph "Layer 1: Pipeline"
        PE[PipelineEngine]
        PD[PipelineDefinitions]
        CP[CheckpointManager]
        MW[MistralWorkflow]
    end
    
    subgraph "Layer 2: Activities"
        A1[intake]
        A2[pre_validator]
        A3[classifier]
        A4[extractor]
        A5[validator]
        A6[reviewer]
        A7[output]
        A8[auto_verifier]
        A9["claim agents (5)"]
    end
    
    subgraph "Layer 3: Agent Loop"
        AL[run_agent_loop]
        SC[run_simple_completion]
    end
    
    subgraph "Layer 4: Provider Registry"
        REG[ProviderRegistry]
        FC[FallbackChain]
        CB2[CircuitBreaker]
    end
    
    subgraph "Layer 5: Providers"
        P1[MistralLLM]
        P2[MistralOCR]
        P3[MistralVision]
        P4[DINOv2Embedding]
        P5[LocalStorage]
    end
    
    R1 --> PE
    R2 --> PE
    R3 --> PE
    PE --> PD
    PD --> A1 & A2 & A3 & A4 & A5 & A6 & A7 & A8 & A9
    A3 & A4 & A5 & A6 & A8 --> AL
    A9 --> AL & SC
    AL --> REG
    SC --> REG
    REG --> FC
    FC --> CB2
    FC --> P1 & P2 & P3
    REG --> P4 & P5
```

## API Layer

Four versioned routers mounted under `/api/v1`:

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| `documents.py` | `/documents` | POST `/upload`, POST `/upload/batch`, GET `/{id}/status`, GET ``, GET `/{id}/extracted`, PUT `/{id}/extracted`, GET `/{id}/file`, GET `/{id}/ocr-blocks`, POST `/{id}/retry`, DELETE `/{id}` |
| `claims.py` | `/claims` | POST ``, GET ``, GET `/{id}/status`, POST `/{id}/run`, GET `/{id}/report`, POST `/{id}/decision`, DELETE `/{id}` |
| `workflow.py` | `/workflow` | POST `/{id}/resume/duplicate`, POST `/{id}/resume/review` |
| `settings.py` | (none) | GET/PUT `/settings/normalization`, GET/PUT `/settings/classification`, GET/PUT/DELETE `/templates`, POST `/templates/generate`, GET `/agents` |

## Service Layer (Activities)

Each activity is an `async def` function that:
1. Obtains the LLM provider from `ProviderRegistry.get()`
2. Loads the system prompt from `PromptManager.get("agent_name")`
3. Defines tool executor callbacks
4. Calls `run_agent_loop()` or `run_simple_completion()`
5. Parses the JSON result
6. Updates the database on success/failure

## Pipeline Engine

The `PipelineEngine` is the orchestration core. It:
- Accepts a `PipelineDefinition` (ordered list of `StepDefinition`)
- Executes steps sequentially with timeout enforcement
- Evaluates step conditions (e.g., only run fraud_check for KYC docs)
- Merges step outputs into a shared context dict
- Saves checkpoints to DB after each successful step
- Handles `HumanInputRequired` by pausing and saving state
- Handles `PipelineRejected` by failing with reason
- Records OpenTelemetry spans and Prometheus metrics per step
- Supports resume from checkpoint after crash

### Document Pipeline Steps (10 steps)

| # | Step | Status Label | Required | Condition |
|---|------|-------------|----------|-----------|
| 1 | intake | processing | Yes | Always |
| 2 | pre_validate | pre_validating | No | `enable_pre_validation` config |
| 2.5 | preprocess | preprocessing | No | `enable_preprocessing` config |
| 3 | classify | classifying | Yes | Always |
| 3.5 | fraud_check | fraud_checking | No | KYC document type |
| 4 | extract | extracting | Yes | Always |
| 5 | validate | validating | Yes | Always |
| 5.5 | auto_verify | auto_verifying | No | KYC document type |
| 6 | review | reviewing | Yes | Always |
| 7 | output | finalizing | Yes | Always |

### Claim Pipeline Steps (7 steps)

| # | Step | Status Label | Required |
|---|------|-------------|----------|
| 1 | claim_integrity | checking_integrity | Yes |
| 2 | claim_medical | checking_medical | Yes |
| 3 | claim_treatment | checking_treatment | Yes |
| 4 | claim_disability | checking_disability | Yes |
| 5 | claim_litigation | checking_litigation | Yes |
| 6 | claim_report | generating_report | Yes |
| 7 | save_claim_report | saving_report | Yes |

## Provider Registry

Singleton pattern. Initialized from `config/platform.yaml` at startup. Manages:
- **LLM providers**: Chat completions with tool calling
- **OCR providers**: Document text extraction with bounding boxes
- **Vision providers**: Image analysis
- **Embedding providers**: Vector embeddings (DINOv2)
- **Storage providers**: File storage (local, S3)

Each provider type has:
- Direct access: `registry.get_llm("mistral")`
- Fallback chain access: `registry.get_llm_chain("classifier")` → tries providers in configured order

## Resilience Layer

### Circuit Breaker
Three states: CLOSED → OPEN → HALF_OPEN.
- Opens after 5 consecutive failures (configurable)
- Recovers after 60 seconds (configurable)
- Half-open allows 1 probe call

### Fallback Chain
Wraps multiple providers of the same type. Tries in order, skipping providers with open circuit breakers.

### Retry Policy
Exponential backoff with jitter: `delay = min(base * 2^attempt + random(0,1), max_delay)`.
Default: 3 retries, 1s base delay, 30s max delay.

### Health Monitor
Background asyncio task that checks all provider health every 30 seconds with a 15-second timeout.

---

# 6. File-by-File Documentation

## Backend V2 — Core Files

### `main.py`
- **Purpose**: FastAPI application entrypoint
- **Responsibilities**: Initializes database, provider registry, health monitor, Redis pool, CORS, and mounts all API routers
- **Lifespan**: Uses `@asynccontextmanager` for startup/shutdown lifecycle
- **Startup sequence**: init_db → init_claim_tables → load_config → ProviderRegistry.from_config → HealthMonitor.start → preload DINOv2 → init Redis pool
- **Shutdown sequence**: stop HealthMonitor → close Redis pool
- **Key detail**: Swagger docs use custom CDN URLs for swagger-ui assets
- **Depends on**: `config`, `db`, `platform_core`, `api.routers.v1`, `observability`, `logging_config`

### `config.py`
- **Purpose**: Application-level settings from environment variables
- **Responsibilities**: Defines all env vars with defaults, validates required vars at import time
- **Key fields**: 25+ agent IDs, database URL, storage dir, Mistral API key, Google Doc AI credentials
- **Design choice**: Uses Pydantic `BaseSettings` with `.env` file support. Exits on validation error to fail fast.
- **Constants**: `SUPPORTED_DOCUMENT_TYPES` list of 11 document categories

### `worker.py`
- **Purpose**: Background task processing via arq (Redis-based task queue)
- **Responsibilities**: Runs document and claim pipelines asynchronously
- **Key logic**: `_should_use_mistral_workflow()` decides between Mistral Workflows SDK and local PipelineEngine based on config
- **Two execution modes**:
  - **Mistral**: Triggers workflow via REST API (`workflows.execute_workflow_async()`)
  - **Local**: Runs `PipelineEngine.run()` directly
- **Worker settings**: 10 max concurrent jobs, parses Redis URL for arq

### `platform_core/registry.py`
- **Purpose**: Singleton provider registry — central access point for all AI providers
- **Responsibilities**: Registration, direct access, fallback chain construction, health checks
- **Factory method**: `from_config()` reads `platform.yaml`, instantiates provider classes, registers them
- **Auto-discovery**: `_register_builtin_providers()` imports all known provider classes at startup
- **Pattern**: Singleton via class variable `_instance`

### `platform_core/agent_loop.py`
- **Purpose**: Reusable multi-turn LLM conversation loop with tool calling
- **Why it exists**: All 16 activity files had identical conversation loop boilerplate. This extracts the pattern into a single function.
- **Flow**: Send message → if tool_calls → execute tools → append results → repeat → parse final JSON
- **Key functions**:
  - `run_agent_loop()`: Full tool-calling loop (max 10 iterations)
  - `run_simple_completion()`: Single-turn completion without tools
  - `_parse_json_response()`: Robust JSON extraction from LLM output (handles code blocks, trailing text)
- **JSON recovery**: Tries full text → markdown code block → first `{` to last `}` → first `[` to last `]`

### `platform_core/pipeline/engine.py`
- **Purpose**: Core pipeline orchestration engine
- **Responsibilities**: Sequential step execution, checkpointing, HITL support, timeout, status tracking
- **Key classes**:
  - `PipelineEngine`: Runs a `PipelineDefinition` with checkpoint support
  - `StepDefinition`: Defines a step (name, handler, condition, timeout, required)
  - `StepResult`: Step execution outcome
  - `HumanInputRequired`: Exception that pauses the pipeline
  - `PipelineRejected`: Exception that terminates the pipeline
- **Observability**: Records `pipeline_step_duration_seconds`, `pipeline_step_total`, and `pipeline_run_duration_seconds` Prometheus metrics. Creates OpenTelemetry spans per step.

### `platform_core/pipeline/definitions.py`
- **Purpose**: Defines the concrete step sequences for document and claim pipelines
- **Key functions**:
  - `build_document_pipeline(config)`: Returns 10-step document pipeline
  - `build_claim_pipeline(config)`: Returns 7-step claim pipeline
- **Step handlers**: Each `_step_*` function is a thin wrapper that imports the activity, calls it, and returns results for context merging
- **Helper**: `_is_kyc_document()` checks if doc_type is an identity document
- **Fallback**: `_fallback_claim_suggestion()` generates rule-based report when LLM is unavailable

### `platform_core/pipeline/checkpoint.py`
- **Purpose**: Pipeline state persistence for crash recovery
- **Storage**: Database (via `db.operations`) or in-memory dict (dev mode)
- **Operations**: save, load, clear, list_incomplete
- **Sanitization**: `_sanitize_context()` strips non-JSON-serializable objects before persistence

### `platform_core/pipeline/mistral_workflow.py`
- **Purpose**: Alternative execution engine using Mistral's managed cloud
- **How it works**: Defines activities with `@workflows.activity` decorators and a workflow class with `@workflows.workflow.define`. Activities wrap existing functions from `activities/*.py`.
- **Managed cloud**: Uses Mistral's Temporal-as-a-Service. Workflows appear in Mistral Studio dashboard.
- **Trade-off**: More durable (managed cloud) but vendor-locked to Mistral

### `platform_core/providers/interfaces.py`
- **Purpose**: Abstract base classes defining provider contracts
- **Provider types**: `LLMProvider`, `OCRProvider`, `StorageProvider`, `EmbeddingProvider`, `VisionProvider`
- **Response types**: `LLMResponse`, `OCRResponse`, `EmbeddingResponse` — standardized dataclasses
- **Health status**: `ProviderStatus` enum (HEALTHY, DEGRADED, DOWN)

## Backend V2 — Database

### `db/models.py`
- **8 ORM models** (see section 11 for full documentation)
- `CustomerReference`, `Document`, `ExtractedData` — document pipeline
- `Claim`, `ClaimDocument`, `ClaimantHistory`, `PolicyDetails`, `ClaimReport`, `ClaimDocumentLink` — claim pipeline
- `PipelineCheckpoint` — pipeline crash recovery

### `db/database.py`
- **Purpose**: Async SQLAlchemy setup
- **Engine**: `create_async_engine` with `aiosqlite` (SQLite) or `asyncpg` (PostgreSQL)
- **SQLite optimizations**: WAL mode, NORMAL synchronous (via PRAGMA events)
- **init_db()**: Creates all tables + defensive ALTER TABLE migrations for columns added after initial schema
- **init_claim_tables()**: Same pattern for claim-related tables

### `db/operations.py`
- **Purpose**: Document CRUD and pipeline checkpoint operations
- **Functions**: `update_status`, `update_doc_type`, `update_error`, `check_duplicate_filename`, `check_duplicate_hash`, `get_document`, `save_checkpoint`, `load_checkpoint`, `clear_checkpoint`

### `db/claim_operations.py`
- **Purpose**: Claim-specific database operations
- **Functions**: `create_claim`, `get_all_claims`, `get_claim_with_docs`, `get_claim_extraction_status`, `link_document_to_claim`, `get_claim_documents_data`, `get_claimant_history`, `get_policy_details`, `save_claim_report`, `upsert_agent_result`, `update_claim_status`, `delete_claim`
- **Key logic**: `get_claim_extraction_status()` checks if all linked documents have finished OCR and transitions claim status to "ready" when complete

## Frontend V2 — Key Files

> Full per-page and per-component breakdown (exact headings, state, API calls, hardcoded lists) lives in Section 4 — this subsection covers the app-shell/infrastructure files only.

### `src/App.jsx` (44 lines)
- **Purpose**: Router definition via `createBrowserRouter` + `<RouterProvider>`
- **12 routes** nested under a single root route rendering `<AppShell />` (see routing table in Section 4)
- **State**: Entire tree wrapped in `<AppProvider>` for global context

### `src/components/layout/AppShell.jsx` (37 lines)
- **Purpose**: Master layout — `<Sidebar>` + `.main-wrapper` (`<TopBar>` + `<main><Outlet/></main>` + decorative `.sunset-stripe`) + `<ToastContainer>`
- Calls `applyTheme(getInitialTheme())` once at module load, before first render, to avoid a flash of the wrong theme
- Local `mobileOpen` state for the sidebar drawer; closes on Escape key

### `src/components/layout/Sidebar.jsx` (171 lines)
- **Purpose**: Collapsible left nav, 5 sections (Main/Data/Intelligence/Claims/System), 11 items total (see Section 4 for the exact list)
- Collapse state in `localStorage['sidebar-collapsed']`; badges on Validation (`reviewDocs.length`) and Processing (`pendingDocs.length`) only

### `src/components/layout/TopBar.jsx` (212 lines)
- **Purpose**: Breadcrumb title/sub (static `PAGE_META` map, 9 of 12 routes covered), theme toggle (`localStorage['idp-theme']`), sync spinner, notification bell/dropdown (top 5 `reviewDocs`), decorative user avatar
- Exports `applyTheme`/`getInitialTheme`, reused by `AppShell.jsx`

### `src/api/client.js` (381 lines)
- **Purpose**: Backend API client — single Axios instance, base URL `VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`), 30s default timeout
- **Exactly 30 exported functions** covering documents, claims, workflow, settings, templates (full method+path table in Section 4)
- **Error normalization**: response interceptor extracts `detail` → `message` → generic Axios error, in that priority order

### `src/store/AppStore.jsx` (165 lines)
- **Purpose**: Global state management — React Context + `useReducer`, 10 initial-state fields, 15 action types (full list in Section 4)
- **Persistence**: only the 5 confidence/threshold fields go to `localStorage`; `documents`/`toasts`/`pollingIds` are session-only
- **Derived state**: `pendingDocs`, `reviewDocs`, `completedDocs` recomputed every render from `documents` (not stored in reducer state)

### `src/hooks/useDocumentPoller.js` (62 lines) / `src/hooks/useDocumentList.js` (31 lines)
- See "Custom Hooks" in Section 4 for exact polling interval (2500ms), backoff behavior (fixed 2× retry, not exponential), and terminal-status set

---

# 7. Function-Level Documentation

## Core Pipeline Functions

### `PipelineEngine.run(pipeline, context, on_status_change)`
- **Purpose**: Execute a pipeline from beginning or resume from checkpoint
- **Parameters**: `pipeline` (PipelineDefinition), `context` (mutable dict), `on_status_change` (optional callback)
- **Return**: Final context dict with all step results
- **Flow**: Load checkpoint → skip completed steps → for each remaining step: check condition → update status → execute with timeout → merge results → save checkpoint
- **Side effects**: Database reads/writes (checkpoint), Prometheus metrics, OpenTelemetry spans

### `run_agent_loop(llm, system_prompt, user_message, tools_schema, tool_executor, ...)`
- **Purpose**: Multi-turn LLM conversation with tool calling
- **Parameters**: LLM provider, system prompt, user message, tools schema, tool executor callback, temperature, max_tokens, max_iterations, json_mode
- **Return**: Parsed JSON dict from final LLM response
- **Flow**: Send user message → if tool_calls: execute each tool → append results → call LLM again → repeat until text-only response → parse JSON
- **Error handling**: If JSON parsing fails and json_mode=True, sends a follow-up request asking for JSON reformatting

### `ProviderRegistry.from_config(config)`
- **Purpose**: Factory method to build a fully initialized registry from YAML config
- **Side effects**: Registers builtin providers, instantiates configured providers, sets fallback chains, stores as singleton
- **Error handling**: Logs warnings for unknown provider types or initialization failures (non-fatal)

### `FallbackChain.call(method, **kwargs)`
- **Purpose**: Try each provider in order until one succeeds
- **Flow**: For each provider: check circuit breaker → if open: skip → try call → on success: record_success → on failure: record_failure, try next
- **Raises**: `AllProvidersFailedError` if every provider fails

---

# 8. Feature Documentation

## Feature 1: Document Upload & Processing

### Purpose
Allow users to upload one or more documents and automatically process them through the AI pipeline.

### Frontend Components
- `Upload.jsx`: Drag-and-drop dropzone, file selection, batch upload support
- `Processing.jsx`: Real-time pipeline step monitoring with status badges
- `useDocumentPoller`: Polls status every 2.5s

### Backend Services
- `api/routers/v1/documents.py`: Upload endpoints
- `platform_core/pipeline/definitions.py`: 10-step pipeline
- `platform_core/pipeline/engine.py`: Step orchestration

### User Workflow
1. User drops file(s) on Upload page
2. Frontend sends POST `/documents/upload` or `/documents/upload/batch`
3. Backend saves file, creates Document record, enqueues pipeline job
4. Worker picks up job, runs 10-step pipeline
5. Frontend polls status every 2.5s, shows step progress
6. On completion, data appears in Extraction page

## Feature 2: Human-in-the-Loop Review

### Purpose
Route low-confidence documents to human reviewers for correction or approval.

### How it works
1. Pipeline step 6 (review) checks if confidence exceeds threshold
2. If below threshold: raises `HumanInputRequired`, pipeline pauses
3. Document status changes to `awaiting_review`
4. Reviewer sees document in Validation page
5. Reviewer approves, corrects, or rejects
6. Frontend calls POST `/workflow/{id}/resume/review`
7. Pipeline resumes from checkpoint

## Feature 3: Insurance Claim Processing

### Purpose
Process insurance claims through 5 specialized AI agents that evaluate different aspects.

### Components
- `ClaimProcess.jsx`: Create claim, upload documents
- `ClaimWorkflow.jsx`: Monitor processing, view reports
- 5 claim activities: integrity, medical, treatment, disability, litigation
- Claim report generation with LLM or rule-based fallback

### User Workflow
1. User creates a claim with claimant info
2. User uploads supporting documents (claim form, medical reports, etc.)
3. Each document goes through the standard OCR pipeline
4. When all documents are extracted, claim becomes "ready"
5. User triggers claim processing
6. 5 specialized agents run sequentially, each saving results incrementally
7. Report agent generates final suggestion
8. Adjuster reviews report and makes approve/reject decision

## Feature 4: Template Management

### Purpose
Define extraction schemas per document type and generate them from sample documents using AI.

### How Template Generation Works
1. User uploads sample document on Templates page
2. Backend converts PDF to image (if needed)
3. Vision provider analyzes the image
4. LLM generates a field schema (name, type, description)
5. Template is saved for future extraction

## Feature 5: Signature & Face Verification

### Purpose
Verify that signatures and face photos on KYC documents match reference records.

### How it works
1. During extraction, `crop_kyc_images` tool extracts signature/photo regions
2. Auto-verifier activity coordinates verification
3. **Signature**: DINOv2 embeddings compute cosine similarity + Vision LLM judges visual match
4. **Face**: 4-agent pipeline (morphology1 → morphology2 → age variation → judge)
5. Results stored in ExtractedData record

---

# 9. Frontend ↔ Backend Interaction

## Document Upload Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend (React)
    participant API as FastAPI
    participant Redis
    participant Worker as arq Worker
    participant Pipeline as PipelineEngine
    participant DB as Database
    participant LLM as Mistral LLM

    U->>FE: Drop file on Upload page
    FE->>API: POST /api/v1/documents/upload (multipart)
    API->>DB: INSERT Document (status=pending)
    API->>Redis: enqueue_job("run_document_pipeline")
    API-->>FE: {document_id, status: "pending"}
    
    FE->>FE: Start useDocumentPoller(id)
    
    Worker->>Redis: Dequeue job
    Worker->>Pipeline: run(document_pipeline, context)
    
    loop Each Pipeline Step
        Pipeline->>DB: Update status
        Pipeline->>LLM: Agent conversation
        LLM-->>Pipeline: Tool calls / final response
        Pipeline->>DB: Save checkpoint
    end
    
    Pipeline->>DB: Save ExtractedData
    Pipeline->>DB: Update status = completed
    
    FE->>API: GET /api/v1/documents/{id}/status (poll)
    API->>DB: SELECT Document
    API-->>FE: {status: "completed", extracted_data: {...}}
    FE->>FE: Show toast "Document processed successfully!"
```

## Claim Processing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant DB as Database
    participant Pipeline as PipelineEngine
    participant Agents as Claim Agents (5)

    U->>FE: Fill claim form
    FE->>API: POST /api/v1/claims
    API->>DB: INSERT Claim (status=creating)
    API-->>FE: {claim_id}
    
    U->>FE: Upload documents
    FE->>API: POST /upload?claim_id=X&doc_type=Y
    API->>DB: Create ClaimDocumentLink
    API->>DB: Claim status → extracting
    
    Note over API,DB: OCR pipeline runs for each document
    
    FE->>API: GET /claims/{id}/status (poll)
    API->>DB: Check all doc statuses
    API-->>FE: {ready_to_process: true}
    
    U->>FE: Click "Process Claim"
    FE->>API: POST /claims/{id}/run
    API->>DB: Claim status → processing
    API->>Pipeline: run(claim_pipeline, context)
    
    loop 5 Agent Steps
        Pipeline->>Agents: Run agent activity
        Agents->>DB: upsert_agent_result()
    end
    
    Pipeline->>DB: save_claim_report()
    Pipeline->>DB: Claim status → completed
    
    FE->>API: GET /claims/{id}/report
    API-->>FE: {agent_results, suggestion, overall_status}
    
    U->>FE: Click Approve/Reject
    FE->>API: POST /claims/{id}/decision
```

---

# 10. API Documentation

## Document Endpoints

| Method | URL | Purpose | Auth | Request | Response |
|--------|-----|---------|------|---------|----------|
| POST | `/api/v1/documents/upload` | Upload single document | None | `multipart/form-data` (file, customer_id?, claim_id?, doc_type?) | `{document_id, filename, status, message, workflow_run_id}` |
| POST | `/api/v1/documents/upload/batch` | Batch upload (≤20 files) | None | `multipart/form-data` (files[]) | `{total, succeeded, failed, results[]}` |
| GET | `/api/v1/documents` | List documents | None | `?page=1&limit=20` | `[{id, filename, status, doc_type, workflow_run_id, message}]` |
| GET | `/api/v1/documents/{id}/status` | Get processing status | None | — | `{document_id, status, doc_type, confidence_score, extracted_data, message}` |
| GET | `/api/v1/documents/{id}/extracted` | Get extracted data | None | — | `{document_id, raw_extracted, validated_data, confidence_score, reviewer_corrections, signature_verification, photo_verification, fraud_check}` |
| PUT | `/api/v1/documents/{id}/extracted` | Update extracted data | None | `{validated_data: {}}` | `{success, document_id, validated_data, reviewer_corrections}` |
| GET | `/api/v1/documents/{id}/file` | Serve original file | None | — | File binary |
| GET | `/api/v1/documents/{id}/ocr-blocks` | Get OCR bounding boxes | None | — | `{blocks[], available}` |
| POST | `/api/v1/documents/{id}/retry` | Retry failed processing | None | — | `{message}` |
| DELETE | `/api/v1/documents/{id}` | Soft-delete document | None | — | `{message}` |

## Claim Endpoints

| Method | URL | Purpose | Auth | Request | Response |
|--------|-----|---------|------|---------|----------|
| POST | `/api/v1/claims` | Create claim | None | `{claimant_name, claim_type, policy_number, description?, priority?, amount?}` | `{claim_id, ...}` |
| GET | `/api/v1/claims` | List claims | None | — | `[{id, claim_type, status, created_at, ...}]` |
| GET | `/api/v1/claims/{id}/status` | Get claim status | None | — | `{claim_id, status, total_docs, completed_docs, ready_to_process}` |
| POST | `/api/v1/claims/{id}/run` | Start claim workflow | None | — | `{message, claim_id}` |
| GET | `/api/v1/claims/{id}/report` | Get claim report | None | — | `{claim_id, agent_results, suggestion, overall_status}` |
| POST | `/api/v1/claims/{id}/decision` | Submit adjuster decision | None | `{decision, notes?}` | `{message}` |
| DELETE | `/api/v1/claims/{id}` | Delete claim | None | — | `{message}` |

## Workflow Endpoints (HITL)

| Method | URL | Purpose | Request |
|--------|-----|---------|---------|
| POST | `/api/v1/workflow/{id}/resume/duplicate` | Resume after duplicate decision | `{override: bool}` |
| POST | `/api/v1/workflow/{id}/resume/review` | Resume after human review | `{approved: bool, corrections?: {}, rejection_reason?: str}` |

## Settings & Template Endpoints

| Method | URL | Purpose |
|--------|-----|---------|
| GET/PUT | `/api/v1/settings/normalization` | Get/set field normalization rules |
| GET/PUT | `/api/v1/settings/classification` | Get/set supported document types |
| GET/PUT | `/api/v1/templates` | Get/set extraction templates |
| DELETE | `/api/v1/templates/{name}` | Delete a template |
| POST | `/api/v1/templates/generate` | AI-generate template from sample doc |
| GET | `/api/v1/agents` | List provider registry summary |

## System Endpoints

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/health` | System health check + provider status |
| GET | `/metrics` | Prometheus metrics |
| GET | `/docs` | Swagger UI |

---

# 11. Database Documentation

## Entity-Relationship Diagram

```mermaid
erDiagram
    CustomerReference ||--o{ Document : "has"
    Document ||--o| ExtractedData : "has"
    Claim ||--o{ ClaimDocument : "has"
    Claim ||--o| ClaimReport : "has"
    ClaimDocumentLink }o--|| Claim : "links to"
    ClaimDocumentLink }o--|| Document : "links to"

    CustomerReference {
        string id PK
        string customer_id UK
        string full_name
        string national_id
        string reference_signature
        string reference_photo
        datetime created_at
    }

    Document {
        string id PK
        string filename
        string file_path
        string file_hash
        string doc_type
        string status
        string workflow_run_id
        json error_details
        string customer_id FK
        datetime created_at
        datetime updated_at
    }

    ExtractedData {
        string id PK
        string document_id FK UK
        json raw_extracted
        json validated_data
        float confidence_score
        json reviewer_corrections
        json signature_verification
        json photo_verification
        json fraud_check
        datetime created_at
    }

    Claim {
        string id PK
        string claim_id UK
        string claimant_id
        string policy_id
        string claimant_name
        string claim_type
        float amount
        string priority
        text description
        datetime submitted_at
        string status
        string workflow_run_id
        datetime created_at
        datetime updated_at
    }

    ClaimDocument {
        string id PK
        string claim_id FK
        string doc_type
        json fields
        datetime created_at
    }

    ClaimReport {
        string id PK
        string claim_id FK UK
        string claimant_name
        json agent_results
        text suggestion
        string overall_status
        datetime processed_at
    }

    ClaimDocumentLink {
        string id PK
        string claim_id FK
        string document_id FK
        string doc_type
        string synced
        datetime created_at
    }

    PipelineCheckpoint {
        string id PK
        string pipeline_id UK
        text data
        datetime created_at
        datetime updated_at
    }
```

## Document Status Flow

```
pending → processing → pre_validating → preprocessing → classifying →
fraud_checking → extracting → validating → auto_verifying →
reviewing → awaiting_review → finalizing → completed
                                          → rejected
                                          → failed
                                          → deleted
                                          → duplicate
```

## Claim Status Flow

```
creating → extracting → ready → processing → checking_integrity →
checking_medical → checking_treatment → checking_disability →
checking_litigation → generating_report → saving_report → completed
                                                        → approved
                                                        → rejected
                                                        → failed
```

---

# 12. AI Architecture

## Overview

The platform uses **16+ specialized AI agents**, each with a specific role. All agents are orchestrated through the `run_agent_loop()` function, which handles multi-turn conversations with tool calling.

## Agent Inventory

### Document Processing Agents

| Agent | Prompt File | Tools | Purpose |
|-------|------------|-------|---------|
| Intake | `intake.md` | `check_duplicate` | Detect duplicate documents by filename/hash |
| Pre-Validator | `pre_validator.md` | `check_image_quality` | Check blur, brightness, readability |
| Preprocessor | `preprocessor.md` | `preprocess_image` | Skew correction, CLAHE, noise removal |
| Classifier | `classifier.md` | `get_supported_document_types`, `get_document_text` | Classify into 11+ document types |
| Fraud Checker | `fraud_checker.md` | `check_document_fraud` | Detect KYC document tampering |
| Extractor | `extractor.md` | `extract_text_from_document`, `crop_kyc_images` | OCR + structured field extraction |
| Validator | `validator.md` | `validate_field_value` | Validate extracted fields |
| Auto-Verifier | `auto_verifier.md` | `find_customer_reference`, `verify_signature`, `verify_face` | Signature + face matching |
| Reviewer | `reviewer.md` | `get_review_status` | Confidence-based review routing |
| Output | `output.md` | `save_final_output` | Final result persistence |

### Claim Processing Agents

| Agent | Prompt File | Purpose |
|-------|------------|---------|
| Integrity | `claim_integrity.md` | Completeness, dates, policy, duplicates |
| Medical | `claim_medical.md` | Diagnosis, ICD codes, provider validation |
| Treatment | `claim_treatment.md` | Treatment-diagnosis alignment, billing |
| Disability | `claim_disability.md` | Disability certificate, severity |
| Litigation | `claim_litigation.md` | Attorney involvement, fraud red flags |
| Report | `claim_report.md` | Final suggestion paragraph |

### Verification Agents

| Agent | Prompt File | Purpose |
|-------|------------|---------|
| Signature Vision | `signature_vision.md` | Visual signature comparison |
| Signature Judge | `signature_judge.md` | Final signature verdict |
| Face Morphology 1 | `face_morphology1.md` | Geometry, eyes, nose analysis |
| Face Morphology 2 | `face_morphology2.md` | Mouth, ears, secondary features |
| Face Age | `face_age.md` | Age variation analysis |
| Face Judge | `face_judge.md` | Final face verdict |

## LLM Conversation Flow

```mermaid
sequenceDiagram
    participant Activity
    participant AgentLoop
    participant LLM as LLM Provider
    participant Tool as Tool Executor

    Activity->>AgentLoop: run_agent_loop(llm, prompt, message, tools, executor)
    AgentLoop->>LLM: chat(messages, system_prompt, tools)
    LLM-->>AgentLoop: {tool_calls: [{name, arguments}]}
    AgentLoop->>Tool: execute_tool(name, args)
    Tool-->>AgentLoop: {result data}
    AgentLoop->>LLM: chat(messages + tool_results)
    LLM-->>AgentLoop: {content: "JSON response"}
    AgentLoop->>AgentLoop: _parse_json_response(content)
    AgentLoop-->>Activity: Parsed JSON dict
```

## OCR + Extraction Pipeline

1. **OCR**: Mistral OCR processes the document → raw text + word confidences + bounding boxes
2. **Template matching**: If a template exists for the doc type, structured extraction is applied
3. **LLM extraction**: Extractor agent receives OCR text and generates structured fields
4. **Normalization**: Fields are normalized (dates, currencies, names) per configured rules
5. **Confidence calculation**: Per-field confidence computed from word-level OCR scores

## Signature Verification Pipeline

1. **Crop extraction**: Signature region cropped from document image
2. **DINOv2 embeddings**: Both document signature and reference signature encoded as vectors
3. **Cosine similarity**: Embedding similarity computed (threshold-based)
4. **Vision LLM analysis**: Pixtral compares visual characteristics
5. **Judge LLM**: Final verdict combining embedding score + visual analysis

## Face Verification Pipeline (4-agent)

1. **Morphology Agent 1**: Analyzes geometry, eye shape, nose structure
2. **Morphology Agent 2**: Analyzes mouth, ears, secondary features
3. **Age Agent**: Evaluates age-related variations between photos
4. **Judge Agent**: Combines all analyses into final match verdict

---

# 13. Authentication & Authorization

## Current State

> **The platform currently has NO authentication or authorization implemented.**

- All API endpoints are publicly accessible
- No JWT, OAuth, sessions, or API keys
- No role-based access control
- CORS is configured to allow specific origins (localhost:5173, localhost:3000)

## Why

This is a development/PoC stage application. Authentication was not implemented to allow rapid iteration. The `.env.example` includes comments suggesting production deployment would require auth.

## Recommendations

See Section 24 (Improvement Suggestions) for recommended auth implementation.

---

# 14. External Integrations

### Mistral AI API
- **Purpose**: LLM chat completions, OCR, Vision analysis
- **Auth**: API key via `MISTRAL_API_KEY` env var
- **Models used**: `mistral-large-latest` (LLM), `mistral-ocr-latest` (OCR), `pixtral-12b-2409` (Vision)
- **Retry**: Via FallbackChain + CircuitBreaker
- **Timeout**: 5-minute per activity

### Mistral Workflows SDK
- **Purpose**: Managed cloud workflow orchestration (Temporal-as-a-Service)
- **Auth**: `MISTRAL_API_KEY` + `DEPLOYMENT_NAME`
- **Connection**: `TEMPORAL_SERVER_URL=wf-scheduler.mistral.ai:443`
- **Usage**: Alternative to local PipelineEngine (configurable)

### Google Document AI
- **Purpose**: Identity document proofing (optional)
- **Auth**: Service account JSON key (`GOOGLE_APPLICATION_CREDENTIALS`)
- **Config**: Project ID, Location, Processor ID

### DINOv2 (Hugging Face)
- **Purpose**: Image embeddings for signature/face verification
- **Model**: `facebook/dinov2-small`
- **Runtime**: Local PyTorch inference (CPU default)
- **Preloaded**: At server startup

### Redis
- **Purpose**: Task queue for arq background workers
- **Default**: `redis://localhost:6379/0`
- **Fallback**: If Redis unavailable, pipelines run as `asyncio.create_task` directly

---

# 15. Configuration

## Backend Configuration

### Environment Variables (`.env`)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MISTRAL_API_KEY` | Yes | — | Mistral AI API key |
| `STORAGE_DIR` | No | `./storage` | File storage directory |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./doc_workflow.db` | Database connection |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection |
| `APP_HOST` | No | `0.0.0.0` | Server host |
| `APP_PORT` | No | `8000` | Server port |
| `DEBUG` | No | `true` | Debug mode |
| `DEPLOYMENT_NAME` | No | `document-ai-pipeline` | Mistral Workflows deployment |
| `CLASSIFIER_AGENT_ID` | Yes | — | Mistral Studio agent ID |
| `VALIDATOR_AGENT_ID` | Yes | — | Mistral Studio agent ID |
| `REVIEWER_AGENT_ID` | Yes | — | Mistral Studio agent ID |
| `SIGNATURE_VISION_AGENT_ID` | Yes | — | Mistral Studio agent ID |
| `SIGNATURE_JUDGE_AGENT_ID` | Yes | — | Mistral Studio agent ID |
| ... (25+ more agent IDs) | | | |

### Platform YAML (`config/platform.yaml`)

Master configuration file controlling all platform behavior:

- **`providers`**: LLM, OCR, Storage, Embedding, Vision provider definitions
- **`fallback_chains`**: Per-purpose provider ordering (e.g., `llm.classifier: [mistral]`)
- **`resilience`**: Circuit breaker thresholds, retry policies, health check intervals
- **`pipelines`**: Document/claim processing settings (workflow_engine, step_timeout, confidence threshold)
- **`cors`**: Allowed origins
- **`database`**: Pool size, overflow settings
- **`observability`**: Tracing, metrics, logging configuration
- **`document_types`**: Supported document type list

### Frontend Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend API base URL |

### Build Tools

- **Vite 8**: Frontend build tool with React plugin
- **ESLint**: Code linting with React Hooks and Refresh plugins

---

# 16. Business Logic

## Document Classification Logic

The classifier agent receives OCR text and a list of supported document types. It determines which type the document belongs to. The platform supports 11 types:
`invoice`, `pan_card`, `claim_form`, `policy_document`, `id_proof`, `medical_report`, `lab_reports`, `prescription_records`, `bills_invoices`, `disability_certificate`, `legal_letter`

**WHY this exists**: Without classification, the system wouldn't know which extraction template to apply. KYC-specific steps (fraud check, signature verification) only run for identity documents.

## Field Confidence Calculation

Each extracted field's confidence is computed by matching field text words against OCR word-level confidence scores. Words are matched by exact text or substring containment. The average confidence of matched words becomes the field confidence.

**WHY this exists**: Users need to know which fields are reliable and which need manual verification. Fields below the `fieldHighlightThreshold` are highlighted amber in the UI.

## Auto-Approval vs. Review Routing

The reviewer agent checks if the overall extraction confidence exceeds `review_confidence_threshold` (default: 80%). If yes, the document is auto-approved. If no, the pipeline pauses for human review via `HumanInputRequired`.

**WHY this exists**: High-confidence documents don't need human review, saving time. Low-confidence documents are routed to experts.

## Claim Evaluation Logic

Five specialized agents evaluate a claim from different angles. Each returns a status (PASS/FAIL/FLAG) with detailed checks. The report agent combines all 5 results into a final suggestion (APPROVE / REVIEW BEFORE APPROVAL / REJECT).

**Fallback**: If the report LLM fails, a rule-based function determines the verdict based on FAIL/FLAG counts.

**WHY this exists**: Insurance claim processing requires multi-dimensional validation that no single agent can handle reliably.

---

# 17. Error Handling

## Backend Error Handling

### API Layer
- FastAPI `HTTPException` for client errors (400, 404, 409)
- Catch-all `try/except` blocks with `500` responses and logging
- Pydantic validation errors auto-returned as 422

### Pipeline Engine
- `HumanInputRequired`: Pauses pipeline, saves checkpoint, returns partial context
- `PipelineRejected`: Marks document as rejected with reason
- `asyncio.TimeoutError`: Step timeout → marks step as failed
- General exceptions: Logged, optional step skip if not required

### Activities
- Each activity wraps its logic in try/except
- On failure: calls `db.update_error(document_id, {...})` to persist error details
- Re-raises exception for pipeline engine to handle

### Agent Loop
- JSON parse failures: Attempts markdown code block extraction, brace matching
- JSON reformat: If json_mode=True, asks LLM to reformat as valid JSON
- Max iterations: Raises `AgentLoopError` after 10 iterations

### Circuit Breaker
- Opens after 5 consecutive failures
- Prevents cascade failures to unhealthy providers

## Frontend Error Handling

### API Client
- Axios response interceptor normalizes error messages from `detail`, `message`, or generic
- All API calls wrapped in try/catch in components

### Toast Notifications
- Success: Green toast on document completion
- Warning: Amber toast for review-required
- Error: Red toast for failures with error message
- Auto-dismiss after 4 seconds

### Polling
- Error backoff: Doubles poll interval on failure (5s instead of 2.5s)
- Continues polling on error (doesn't stop)

---

# 18. Performance

## Frontend Performance

- **Code splitting**: React Router lazy loading (implicit via separate page components)
- **Memoization**: `useCallback` for all dispatch wrappers in AppStore
- **localStorage**: Threshold values cached locally to avoid re-renders
- **CSS Design System**: Single stylesheet load, no runtime CSS generation
- **Polling optimization**: Stops polling at terminal statuses

## Backend Performance

- **Async throughout**: FastAPI + async SQLAlchemy + async provider calls
- **Background processing**: Pipeline runs in arq workers, not in request thread
- **Fallback with no Redis**: `asyncio.create_task()` for inline processing
- **Database**: SQLite WAL mode for concurrent reads, NORMAL synchronous for speed
- **DINOv2 preloading**: Model loaded at startup, not per-request
- **Checkpoint optimization**: Context sanitized before JSON serialization
- **Batch upload**: Concurrent processing via `asyncio.gather()`
- **Pipeline checkpointing**: Resumes from last completed step after crash

## Metrics

Custom Prometheus metrics tracked:
- `pipeline_step_duration_seconds` — per step latency
- `pipeline_step_total` — step execution counts by status
- `pipeline_run_duration_seconds` — total pipeline time
- `provider_call_duration_seconds` — provider call latency
- `provider_call_total` — provider call counts
- `circuit_breaker_state` — current breaker states
- `queue_depth` — background task queue size
- `agent_loop_iterations` — LLM loop iterations per call
- `agent_loop_tool_calls_total` — total tool calls

---

# 19. Design Patterns

## Singleton Pattern
- **Where**: `ProviderRegistry._instance`
- **Why**: One registry per process ensures consistent provider state across all handlers

## Factory Pattern
- **Where**: `ProviderRegistry.from_config(config)` builds the registry from YAML
- **Why**: Decouples configuration from instantiation

## Strategy Pattern
- **Where**: `LLMProvider`, `OCRProvider`, `VisionProvider` abstract interfaces with multiple implementations
- **Why**: Provider-agnostic design — swap Mistral for OpenAI via config

## Chain of Responsibility
- **Where**: `FallbackChain` tries providers in order
- **Why**: Automatic failover without caller awareness

## Pipeline Pattern
- **Where**: `PipelineDefinition` + `PipelineEngine`
- **Why**: Document processing as an ordered sequence of independent steps

## Observer Pattern
- **Where**: `useDocumentPoller` observes document status changes
- **Why**: Real-time UI updates without WebSocket complexity

## Template Method
- **Where**: `run_agent_loop()` defines the conversation flow, activities provide tools/prompts
- **Why**: Eliminates boilerplate across 16 activity files

## Repository Pattern
- **Where**: `db/operations.py` and `db/claim_operations.py` encapsulate all DB access
- **Why**: Separates data access from business logic

## Circuit Breaker Pattern
- **Where**: `CircuitBreaker` class wrapping each provider
- **Why**: Prevents cascade failures when a provider goes down

---

# 20. Security Analysis

## Current Security Posture

| Area | Status | Notes |
|------|--------|-------|
| Authentication | ❌ None | No user authentication |
| Authorization | ❌ None | No role-based access |
| Input validation | ✅ Partial | Pydantic schema validation, file type whitelist |
| Secrets management | ⚠️ Basic | `.env` file, `${ENV_VAR}` resolution |
| File upload security | ✅ Yes | MIME type whitelist (PDF, JPEG, PNG, WEBP, DOCX) |
| SQL injection | ✅ Protected | SQLAlchemy ORM parameterized queries |
| XSS prevention | ✅ Partial | React auto-escapes, no `dangerouslySetInnerHTML` |
| CSRF prevention | ⚠️ Partial | CORS origin whitelist, but no CSRF tokens |
| Rate limiting | ❌ None | No request rate limiting |
| API key exposure | ⚠️ Risk | Mistral API key in `.env`, could be logged |
| File storage | ⚠️ Basic | Files stored on disk with hash-based naming |
| PII handling | ⚠️ Minimal | Extracted data stored in DB, no encryption at rest |
| Batch upload limit | ✅ Yes | 20 file maximum |

---

# 21. Deployment

## Development Setup

### Backend
```bash
cd backend-v2
python -m venv venv
venv\Scripts\activate         # Windows
pip install -r requirements.txt
cp .env.example .env          # Edit with your API keys
python main.py                # Starts on :8000
```

### Frontend
```bash
cd frontend-v2
npm install
cp .env.example .env          # Set VITE_API_BASE_URL if needed
npm run dev                   # Starts on :5173
```

### Background Worker (optional)
```bash
cd backend-v2
arq worker.WorkerSettings     # Requires Redis running
```

## Docker Compose Deployment

```bash
cd backend-v2
docker-compose up -d
```

Services:
1. **postgres** (port 5432): PostgreSQL 15 with health check
2. **redis** (port 6379): Redis 7 with persistence
3. **app** (port 8000): FastAPI application
4. **worker**: arq background worker

Volumes:
- `postgres_data`: Database persistence
- `redis_data`: Redis persistence
- `./storage`: Shared file storage between app and worker
- `./config`: Platform configuration
- `./migrations`: Alembic migrations

## Production Considerations

- Switch `DATABASE_URL` to PostgreSQL: `postgresql+asyncpg://user:pass@host/db`
- Set `DEBUG=false`
- Configure proper CORS origins
- Add authentication middleware
- Set up OTLP exporter for distributed tracing
- Configure Redis for persistence and sentinel

---

# 22. Data Flow & Sequence Diagrams

## Overall Architecture Flow

```mermaid
flowchart TB
    subgraph "Client"
        Browser[React SPA]
    end
    
    subgraph "API Gateway"
        FastAPI[FastAPI :8000]
    end
    
    subgraph "Queue"
        Redis[(Redis)]
    end
    
    subgraph "Workers"
        ARQ[arq Worker]
    end
    
    subgraph "Pipeline"
        Engine[PipelineEngine]
        Steps[10 Pipeline Steps]
    end
    
    subgraph "AI"
        Loop[Agent Loop]
        LLM[Mistral LLM]
        OCR[Mistral OCR]
        Vision[Pixtral Vision]
        DINOv2[DINOv2 Embeddings]
    end
    
    subgraph "Storage"
        DB[(SQLite/PostgreSQL)]
        Files[File System]
    end
    
    Browser <-->|REST API| FastAPI
    FastAPI -->|Enqueue| Redis
    Redis -->|Dequeue| ARQ
    ARQ --> Engine
    Engine --> Steps
    Steps --> Loop
    Loop --> LLM
    Steps --> OCR
    Steps --> Vision
    Steps --> DINOv2
    Steps --> DB
    Steps --> Files
    FastAPI --> DB
```

## Document Upload to Completion

```mermaid
stateDiagram-v2
    [*] --> pending: Upload received
    pending --> processing: Worker starts
    processing --> pre_validating: Step 2
    pre_validating --> preprocessing: Step 2.5
    pre_validating --> rejected: Failed quality
    preprocessing --> classifying: Step 3
    classifying --> fraud_checking: KYC document
    classifying --> extracting: Non-KYC document
    fraud_checking --> rejected: Fraud detected
    fraud_checking --> extracting: Passed
    extracting --> validating: Step 5
    validating --> auto_verifying: KYC document
    validating --> reviewing: Non-KYC document
    auto_verifying --> reviewing: Step 6
    reviewing --> awaiting_review: Low confidence
    reviewing --> finalizing: High confidence
    awaiting_review --> finalizing: Human approved
    awaiting_review --> rejected: Human rejected
    finalizing --> completed: Step 7
    completed --> [*]
    rejected --> [*]
```

## Authentication Flow (Planned)

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant Auth as Auth Provider
    
    U->>FE: Login credentials
    FE->>Auth: Authenticate
    Auth-->>FE: JWT token
    FE->>FE: Store token
    FE->>API: Request + Authorization: Bearer {token}
    API->>API: Validate JWT
    API-->>FE: Response
```

---

# 23. Recreation Guide

## Prerequisites

- Python 3.12+
- Node.js 18+
- Redis (optional, for background workers)
- Mistral AI API key

---

## Backend V2 Recreation

### Step 1: Project Initialization

```bash
mkdir backend-v2 && cd backend-v2
python -m venv venv
venv\Scripts\activate
```

Create `requirements.txt` with these core packages:
```
fastapi==0.119.1
uvicorn[standard]==0.30.6
sqlalchemy==2.0.41
aiosqlite==0.22.1
pydantic==2.12.5
pydantic-settings==2.14.0
mistralai==2.5.0
mistralai-workflows==3.4.0
arq
redis
pyyaml
pillow==12.2.0
pymupdf==1.28.0
python-multipart==0.0.20
python-dotenv==1.2.1
opentelemetry-api==1.39.1
opentelemetry-sdk==1.39.1
opentelemetry-instrumentation-fastapi
prometheus-client
transformers
torch
torchvision
opencv-python-headless
alembic
```

### Step 2: Configuration Layer

1. Create `config.py` with Pydantic `BaseSettings` — 25+ agent ID fields, database URL, storage dir, Mistral API key
2. Create `config/platform.yaml` — master YAML config with providers, fallback chains, resilience, pipeline settings
3. Create `platform_core/config.py` — YAML loader with `${ENV_VAR}` resolution from `.env`
4. Create `.env.example` with all required variables

### Step 3: Database Layer

1. Create `db/database.py` — async SQLAlchemy engine with `create_async_engine`, session factory, `init_db()`, `init_claim_tables()`
2. Create `db/models.py` — 8 ORM models: CustomerReference, Document, ExtractedData, Claim, ClaimDocument, ClaimantHistory, PolicyDetails, ClaimReport, ClaimDocumentLink, PipelineCheckpoint
3. Create `db/operations.py` — Document CRUD + checkpoint operations
4. Create `db/claim_operations.py` — Claim CRUD, document linking, report persistence

### Step 4: Provider Interfaces

1. Create `platform_core/providers/interfaces.py` — ABC classes: LLMProvider, OCRProvider, StorageProvider, EmbeddingProvider, VisionProvider
2. Create response dataclasses: LLMResponse, OCRResponse, EmbeddingResponse
3. Create provider implementations under `platform_core/providers/llm/`, `ocr/`, `vision/`, `embedding/`, `storage/`

### Step 5: Resilience Layer

1. Create `platform_core/resilience/circuit_breaker.py` — 3-state circuit breaker
2. Create `platform_core/resilience/fallback.py` — FallbackChain with generic type parameter
3. Create `platform_core/resilience/retry.py` — RetryPolicy with exponential backoff
4. Create `platform_core/resilience/health.py` — HealthMonitor background task

### Step 6: Provider Registry

1. Create `platform_core/registry.py` — Singleton ProviderRegistry with registration, access, factory, and diagnostic methods

### Step 7: Agent Loop

1. Create `platform_core/agent_loop.py` — `run_agent_loop()` and `run_simple_completion()` with robust JSON parsing

### Step 8: Pipeline Engine

1. Create `platform_core/pipeline/engine.py` — PipelineEngine with checkpointing, HITL, and metrics
2. Create `platform_core/pipeline/checkpoint.py` — CheckpointManager with DB or memory storage
3. Create `platform_core/pipeline/definitions.py` — Document pipeline (10 steps) + Claim pipeline (7 steps)
4. Create `platform_core/pipeline/mistral_workflow.py` — Mistral Workflows SDK integration

### Step 9: Prompt Files

Create 23 markdown prompt files in `platform_core/prompts/`:
- classifier, extractor, validator, reviewer, intake, pre_validator, preprocessor, fraud_checker, auto_verifier, output
- claim_integrity, claim_medical, claim_treatment, claim_disability, claim_litigation, claim_report
- signature_vision, signature_judge, face_morphology1, face_morphology2, face_age, face_judge

### Step 10: Activities & Tools

1. Create tool definition files in `tools/` — OpenAI-compatible function schemas + implementations
2. Create activity files in `activities/` — Business logic calling ProviderRegistry + PromptManager + AgentLoop

### Step 11: Utilities

1. Create `utils/file_handler.py` — File save with SHA-256 hashing
2. Create `utils/ocr.py` — OCR provider wrapper
3. Create `utils/preprocessor.py` — OpenCV image preprocessing
4. Create `utils/signature_extractor.py` — Signature region cropping
5. Create `utils/signature_verifier.py` — DINOv2 + Vision verification
6. Create `utils/face_verifier.py` — Multi-agent face verification
7. Create `utils/norm_config.py`, `classification_config.py`, `templates.py`

### Step 12: API Layer

1. Create `schemas/documents.py` and `schemas/claims.py` — Pydantic models
2. Create `api/queue.py` — Redis pool factory
3. Create `api/routers/v1/documents.py` — 10 document endpoints
4. Create `api/routers/v1/claims.py` — 7 claim endpoints
5. Create `api/routers/v1/workflow.py` — 2 HITL resume endpoints
6. Create `api/routers/v1/settings.py` — Settings + templates endpoints
7. Create `api/routers/v1/__init__.py` — Mount all routers under `/api/v1`

### Step 13: Observability

1. Create `logging_config.py` — JSONFormatter for structured logs
2. Create `observability.py` — OpenTelemetry + Prometheus setup with custom metrics

### Step 14: Application Entry

1. Create `main.py` — FastAPI app with lifespan, CORS, router mounting, health endpoint
2. Create `worker.py` — arq worker with Mistral/local engine detection

### Step 15: Docker

1. Create `Dockerfile` — Python 3.12-slim with pip install
2. Create `docker-compose.yml` — 4 services (app, worker, postgres, redis)

---

## Frontend V2 Recreation

### Step 1: Project Initialization

```bash
npx -y create-vite@latest frontend-v2 -- --template react
cd frontend-v2
npm install axios react-router-dom lucide-react
```

### Step 2: Design System (CSS)

**Critical for matching the real UI — get this step wrong and the whole app looks different even if every component is structurally correct.**

1. Create `src/styles/tokens.css` — CSS custom properties for **light-as-default** (`:root`) and dark override (`[data-theme="dark"]`, NOT `[data-theme="light"]`). Light theme is the "Mistral Warm Sunset" palette: `--bg:#fffaeb`, `--accent:#fa520f`, `--text:#1f1f1f`, warm cream/orange surfaces throughout (full token table in Section 4). Import 3 Google Fonts: `Playfair Display` (display headings), `Inter` (UI, variable weight), `JetBrains Mono` (code/JSON).
2. Create `src/styles/animations.css` — 16 keyframes (`border-rotate`, `pulse`, `ping`, `spin`, `shimmer`, `shimmer-line`, `slide-in`, `slide-right`, `slide-up`, `fade-in`, `toast-in`, `progress-fill`, `glow-pulse`, `float`, `nav-indicator-in`, `count-pop`) + a `prefers-reduced-motion` override
3. Create `src/styles/layout.css` — sidebar (220px expanded / 64px collapsed), `.main-wrapper`, 60px sticky topbar, grid utilities, breakpoints at 1100/800/768/600px
4. Create `src/styles/components.css` — All component styles (~2200 lines in the reference app)
5. Do **not** wire up `index.css` beyond `body { margin: 0 }`, and do not build on top of the default Vite `App.css` boilerplate — both are effectively unused in the reference app and importing them can leak stray styles

### Step 3: Entry Points

1. Update `index.html` — title "Intelligent Document Processing — IDP Platform", meta description, `theme-color` `#080b14`, an inline data-URI SVG favicon (document icon, blue→violet gradient with a cyan checkmark badge — not a separate favicon file)
2. Create `src/main.jsx` — import CSS in this exact order (`tokens.css` → `animations.css` → `layout.css` → `components.css`), then render `<App />` inside `<StrictMode>`

### Step 4: State Management

1. Create `src/store/AppStore.jsx` — Context + `useReducer`, 10-field initial state, 15 action types, 5 `localStorage`-persisted fields (confidence mode + 4 thresholds), 3 derived selectors (`pendingDocs`/`reviewDocs`/`completedDocs`) computed from `documents` on every render — see exact shape in Section 4

### Step 5: API Layer

1. Create `src/api/client.js` — Axios instance + exactly 30 typed API functions (see full table in Section 4), 30s default timeout with longer overrides for batch upload (300s) and template generation/signature verification/claim uploads (120s)
2. Create `src/hooks/useDocumentPoller.js` — polls every 2500ms, fixed-2× (not exponential) backoff on failure, stops at 4 terminal statuses, toasts only on status transitions
3. Create `src/hooks/useDocumentList.js` — one-shot `refresh(page, limit)`, no internal interval; callers own their own polling loop

### Step 6: Layout Components

1. Create `src/components/layout/AppShell.jsx` — exact JSX order: `Sidebar` → `.main-wrapper` (`TopBar` + `<main><Outlet/></main>` + `.sunset-stripe`) → `ToastContainer`; call `applyTheme(getInitialTheme())` at module load
2. Create `src/components/layout/Sidebar.jsx` — 5 sections (Main/Data/Intelligence/Claims/System), 11 nav items (not 12 — `ClaimWorkflow` has no sidebar entry), badges only on Validation/Processing, `localStorage['sidebar-collapsed']`
3. Create `src/components/layout/TopBar.jsx` — theme toggle (`localStorage['idp-theme']`), static `PAGE_META` breadcrumb map (only 9 routes covered — leave the rest falling back to "IDP Platform"), notification dropdown, decorative avatar

### Step 7: UI Components

1. Create 8 reusable UI components in `src/components/ui/` with the exact props/behavior in Section 4's component table:
   - `ConfidenceBar`, `DonutChart`, `Modal`, `PipelineSteps`, `RegionSelector`, `StatCard`, `StatusBadge` (14-status map), `ToastContainer`

### Step 8: Pages

1. Create 12 page components in `src/pages/` matching the exact headings/sections/behaviors documented per-page in Section 4 ("Pages — Exact Content") — generic placeholder content per page will look and behave visibly differently from the reference app:
   - Dashboard, Upload, Processing, Extraction, Validation, Documents, Agents, Analytics, Settings, Templates, ClaimProcess, ClaimWorkflow
2. `ClaimProcess.jsx` and `ClaimWorkflow.jsx` intentionally do **not** use the global `AppStore` — they're self-contained with local state and their own polling (6s claim list / 5s expanded claim / 4s workflow status)

### Step 9: Routing

1. Create `src/App.jsx` — `createBrowserRouter` with 12 routes under `AppShell`, but only 11 wired into the sidebar (see Step 6)

### Step 10: Build & Test

```bash
npm run dev     # Development
npm run build   # Production
```

---

# 24. Improvement Suggestions

## Architecture

| Area | Current | Recommended |
|------|---------|-------------|
| **Authentication** | None | Add JWT auth with refresh tokens, role-based access (admin, reviewer, operator) |
| **WebSocket** | Polling every 2.5s | Server-Sent Events or WebSocket for real-time status updates |
| **API Versioning** | v1 only | Maintain v1, prepare v2 with breaking changes |
| **Caching** | None | Redis caching for templates, classification config, frequently accessed documents |
| **Rate Limiting** | None | Per-endpoint rate limiting (e.g., 10 uploads/min) |

## Scalability

| Area | Current | Recommended |
|------|---------|-------------|
| **Database** | SQLite (dev) | PostgreSQL with connection pooling (PgBouncer) |
| **File Storage** | Local filesystem | S3-compatible object storage (already abstracted via StorageProvider) |
| **Workers** | Single arq worker | Multiple workers with priority queues |
| **Search** | None | Elasticsearch for document search |
| **Pagination** | Offset-based | Cursor-based pagination for large datasets |

## Maintainability

| Area | Current | Recommended |
|------|---------|-------------|
| **Testing** | No tests | Add pytest with ~80% coverage, API integration tests |
| **Type Safety** | Partial Python typing | Full type hints + mypy strict mode |
| **Frontend State** | Context + useReducer | Consider Zustand for simpler API |
| **Error Tracking** | Logs only | Sentry integration for error tracking |
| **API Documentation** | Auto-generated Swagger | Add OpenAPI descriptions + examples |

## Performance

| Area | Current | Recommended |
|------|---------|-------------|
| **Batch processing** | Sequential pipeline | Parallel independent steps (classify + OCR simultaneously) |
| **Model loading** | Startup preload | Lazy loading with model cache |
| **Response compression** | None | gzip middleware |
| **Database queries** | Individual selects | Batch queries with joined loads |

## Security

| Area | Current | Recommended |
|------|---------|-------------|
| **Secrets** | `.env` file | HashiCorp Vault or cloud KMS |
| **File scanning** | MIME check only | Antivirus scanning on upload |
| **Encryption** | None | TLS everywhere, encrypted DB columns for PII |
| **Audit logging** | None | Immutable audit log for all data changes |
| **Input sanitization** | Pydantic only | Additional sanitization for free-text fields |

## Developer Experience

| Area | Current | Recommended |
|------|---------|-------------|
| **Local dev** | Manual setup | Docker Compose dev profile with hot reload |
| **CI/CD** | None | GitHub Actions pipeline (lint → test → build → deploy) |
| **Documentation** | This file | Automated API docs + ADR (Architecture Decision Records) |
| **Monitoring** | Prometheus + OTEL | Grafana dashboards + PagerDuty alerts |

---

> **End of Document**
> 
> This specification contains all architectural decisions, data flows, API contracts, database schemas, AI workflows, and implementation details needed to recreate the Document AI Platform V2 from scratch.
