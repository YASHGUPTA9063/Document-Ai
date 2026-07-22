# Document-AI Detailed Component Architecture

Here is a detailed breakdown of the internal components and workflows across the Document-AI system.

```mermaid
flowchart TB
    classDef frontend fill:#61dafb,stroke:#333,stroke-width:2px,color:#000
    classDef api fill:#4caf50,stroke:#333,stroke-width:2px,color:#fff
    classDef worker fill:#ff9800,stroke:#333,stroke-width:2px,color:#fff
    classDef db fill:#336699,stroke:#333,stroke-width:2px,color:#fff
    classDef cache fill:#ff4444,stroke:#333,stroke-width:2px,color:#fff

    User(["User (Browser)"])

    %% FRONTEND SUBGRAPH
    subgraph Frontend ["Frontend Environment (React/Vite)"]
        direction TB
        UI["Pages & UI Components"]
        Hooks["React Hooks (State Management)"]
        APIClient["API Client (Axios)"]
        
        UI --> Hooks
        Hooks --> APIClient
    end
    class Frontend frontend

    %% BACKEND API SUBGRAPH
    subgraph BackendAPI ["FastAPI App Server"]
        direction TB
        APIRouters["API Routers (v1)"]
        DocRoute["/documents<br>(Upload, List, Details)"]
        ClaimRoute["/claims<br>(Claim Management)"]
        WorkflowRoute["/workflow<br>(Start/Stop Jobs)"]
        SettingsRoute["/settings<br>(Config Management)"]
        
        APIRouters --> DocRoute
        APIRouters --> ClaimRoute
        APIRouters --> WorkflowRoute
        APIRouters --> SettingsRoute
    end
    class BackendAPI api

    %% BACKGROUND WORKER SUBGRAPH
    subgraph ArqWorker ["Arq Job Worker (AI & Processing)"]
        direction TB
        WorkerManager["Worker Coordinator"]
        
        subgraph Pipeline ["Processing Pipeline (Activities)"]
            Intake["Intake & Preprocessor"]
            Classifier["Document Classifier"]
            Extractor["Data Extractor (LLM)"]
            Validators["Pre-validator & Validator"]
            Reviewer["AI Reviewer & Auto-Verifier"]
            Fraud["Fraud Checker"]
            ClaimLogic["Claim Specific Logic<br>(Medical, Litigation, etc.)"]
            
            Intake --> Classifier --> Extractor --> Validators --> Reviewer --> Fraud --> ClaimLogic
        end
        WorkerManager --> Pipeline
    end
    class ArqWorker worker

    %% DATABASES
    Postgres[("PostgreSQL<br>(Documents, Claims, Extracted Data)")]:::db
    Redis[("Redis<br>(Arq Task Queue)")]:::cache

    %% INTERACTIONS
    User -->|Interacts| UI
    APIClient -->|HTTP Requests| APIRouters
    
    DocRoute -->|Reads/Writes| Postgres
    ClaimRoute -->|Reads/Writes| Postgres
    WorkflowRoute -->|Enqueues Task| Redis
    
    Redis -->|Pulls Task| WorkerManager
    Pipeline -->|Updates Status/Data| Postgres
    Pipeline -.->|Calls| ExternalLLM(("External LLM API<br>(OpenAI/Mistral)"))

```

### Subsystem Details

#### 1. React Frontend (`frontend-v2/src`)
- **Pages & Components:** Renders the UI for document uploads, claim monitoring, and configuration.
- **Hooks & Store:** Manages local state and continuous polling to keep the UI synchronized with background job progress.
- **API Client:** An Axios-based layer that communicates securely with the FastAPI backend.

#### 2. FastAPI Backend (`backend-v2/api`)
- **Routers (`backend-v2/api/routers/v1`):**
  - `documents.py`: Handles file uploads, retrieving document status, and fetching extracted data.
  - `claims.py`: Manages claim creation, retrieval, and updates.
  - `workflow.py`: Triggers or stops background processing pipelines.
  - `settings.py`: Manages system configurations and prompts.
- **Database Layer (`backend-v2/db`):** Uses SQLAlchemy asynchronous sessions (`create_async_engine`) to interact with PostgreSQL.

#### 3. Arq Background Worker (`backend-v2/activities`)
The core intelligence of the system. Offloads heavy tasks from the API to prevent blocking.
- **Intake & Preprocessing:** Reads uploaded files and prepares them (OCR, image normalization).
- **Classifier:** Determines the type of document uploaded.
- **Extractor:** Uses Large Language Models (LLMs) to parse raw text and pull structured entities.
- **Validators & Reviewers:** Compares extracted data against rules and cross-verifies signatures/photos for authenticity.
- **Fraud Checker:** Analyzes inconsistencies or tampered metadata.
- **Claim Specific Logic:** Specialized activities for handling different claim types (Medical, Litigation, Disability, etc.).

#### 4. Infrastructure
- **Redis:** Serves as the message broker. When the API calls `/workflow`, it places a job ID in Redis. The Arq Worker listens to Redis, picks up the job, and starts the pipeline.
- **PostgreSQL:** The single source of truth. As the worker completes each activity (e.g., Classifier -> Extractor), it updates the document's state in PostgreSQL, which the frontend eventually fetches to show progress to the user.
