# Document AI — backend

Multi-agent document ingestion, classification, extraction, validation and
human-in-the-loop review, plus a claim-processing pipeline.

Execution runs entirely on **Mistral Studio's managed orchestration**. Studio
owns durability, retries and the 24-hour human-input waits; this codebase owns
the workflow definition, the activities, and the HTTP surface.

---

## Process topology

Three roles, one image. They scale and fail differently, so they are separate
processes.

```
Browser ──► nginx ──► api  (FastAPI, N uvicorn workers, stateless)
                       │  POST /api/v1/documents/upload
                       │  writes the Document row, returns immediately
                       ▼
                  Redis · arq queue          [EXECUTION_MODE=queue]
                       │                     └ inline: dispatch in-request
                       ▼
                  dispatcher (arq)
                       │  execute_workflow_async(...) with retry + backoff
                       ▼
            ┌──── Mistral Studio — managed Temporal ────┐
            │   document_processing_workflow            │
            │   claim_processing_workflow               │
            └───────────────────┬───────────────────────┘
                                │ dispatches activities to DEPLOYMENT_NAME
                                ▼
                  workflow-worker  (scale this one)
                       │  activities/*.py
                       ▼
                  Postgres 15 (docker) / SQLite (venv)
```

- **api** never executes a pipeline step. It writes rows and answers queries.
- **dispatcher** only *starts* runs. Putting a queue in front of that single
  API call is what keeps a Mistral blip from failing a user's upload.
- **workflow-worker** does all the real work: OCR, vision calls, DINOv2
  inference. `docker compose up -d --scale workflow-worker=3`.

| File | Role |
|---|---|
| `main.py` | FastAPI app |
| `worker.py` | arq dispatcher (`arq worker.WorkerSettings`) |
| `workflow_worker.py` | Mistral Studio worker (`python workflow_worker.py`) |
| `bootstrap.py` | shared startup: config → registry → health → DINOv2 |
| `platform_core/dispatch.py` | the only module that starts a Studio run |
| `workflow.py` / `claim_workflow.py` | the workflow definitions |

---

## Pipeline

```
1    intake            duplicate? ──► gate ──► override / reject
1.5  splitter          multi-document packet? ──► gate ──► fan out one child per document
2    pre_validator     blur / brightness / skew / readability
2.5  preprocessor      (off by default)
3    classifier        doc_type
3.2  checklist         batch-wide barrier ──► gate ──► missing document types
3.5  fraud_checker     KYC documents only
4    extractor         fields (+ optional vLLM second pass)
5    validator         schema + confidence
5.5  auto_verifier     signature / face, KYC only
6    reviewer          score < threshold ──► gate ──► approve / correct
7    output            persist and finish
```

Each gate waits 24 hours. If nobody answers, the document ends at the terminal
`expired` status and can be retried — it does not hang.

---

## Running it

### Local venv — zero infrastructure

SQLite, inline dispatch, workflow worker hosted inside the API process.

```bash
cd backend-v2
python -m venv .venv
source .venv/Scripts/activate        # Windows; use .venv/bin/activate elsewhere
pip install -r requirements.txt

cp .env.example .env                 # then fill in MISTRAL_API_KEY + agent IDs
# .env: EXECUTION_MODE=inline
#       RUN_WORKFLOW_WORKER_IN_API=true
#       DATABASE_URL=sqlite+aiosqlite:///./doc_workflow.db

alembic upgrade head
uvicorn main:app --reload            # single worker only in this mode
```

Frontend: `cd ../frontend-v2 && npm install && npm run dev` — the Vite dev
server proxies `/api` to `localhost:8000`.

To run the pieces separately (closer to production, still no Docker):

```bash
# terminal 1
uvicorn main:app --reload            # EXECUTION_MODE=queue, RUN_WORKFLOW_WORKER_IN_API=false
# terminal 2
arq worker.WorkerSettings
# terminal 3
python workflow_worker.py
# plus a Redis on REDIS_URL
```

### Docker — Postgres, queued dispatch, separated processes

```bash
docker compose up -d --build
docker compose logs -f workflow-worker    # should show the SDK connecting to Studio
docker compose logs -f dispatcher         # should show execute_workflow_async dispatches
docker compose up -d --scale workflow-worker=3
```

Frontend on `:5173`, API on `:8000`. nginx proxies `/api/` straight through —
no prefix rewriting.

### Tests

```bash
pytest                    # from backend-v2/; conftest.py supplies all env vars
```

---

## Mistral Studio setup

The `*_AGENT_ID` values in `.env` are what bind this code to Studio. Create them
once:

```bash
python create_or_update_agents.py
```

Then copy the printed IDs into `.env`. `GET /ready` reports which are bound and
which capabilities are off without them.

Five are required and the process refuses to start without them outside DEBUG:
`CLASSIFIER_AGENT_ID`, `VALIDATOR_AGENT_ID`, `REVIEWER_AGENT_ID`,
`SIGNATURE_VISION_AGENT_ID`, `SIGNATURE_JUDGE_AGENT_ID`. The rest are optional
and each one silently disables a capability — see `OPTIONAL_AGENT_BINDINGS` in
`config.py`.

---

## Deploy runbook — changing `workflow.py`

**This is the part that bites.** Mistral Studio is Temporal-backed: an
in-flight execution *replays its history* against whatever code the worker pool
is running. A document parked at a 24-hour review gate will still be replaying
tomorrow's code.

Changing an **activity body** is safe — activities are not replayed.

Changing the **step sequence** in `workflow.py` is not. Do this instead:

1. Bump `DEPLOYMENT_NAME` (`...-v2` → `...-v3`). It is a version, not a label.
2. Deploy the new workflow-worker pool alongside the old one.
3. Point `DEPLOYMENT_NAME` for the **api** and **dispatcher** at the new pool,
   so new runs land there.
4. Leave the old pool running until its in-flight executions drain, then stop
   it.

Never cut over in place while executions are parked at a gate.

---

## Operations

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness. Always 200 so a degraded provider never triggers a restart. Reports execution mode and circuit-breaker state. |
| `GET /ready` | Readiness. 503 when the database is unreachable, Redis is down under `queue`, or a required agent is unbound. |

**Schema** is owned by Alembic. `entrypoint.sh` runs `alembic upgrade head` in
the **api** container only (`RUN_MIGRATIONS=true`); the dispatcher and
workflow-worker skip it so three containers starting together do not race for
the same lock.

**HTTP surface** is `/api/v1/*`. The unprefixed paths an older frontend build
used (`/upload`, `/upload/batch`, `/status/{id}`) are re-registered onto the
same handler functions while `ENABLE_LEGACY_ROOT_ROUTES=true`. Turn it off once
no such build is deployed.
