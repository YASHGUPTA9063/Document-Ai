from typing import Literal
import os

from dotenv import load_dotenv
# Force .env values to override system environment variables.
# pydantic-settings reads os.environ, so we must inject .env values first.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError, field_validator

class Settings(BaseSettings):
    MISTRAL_API_KEY: str = Field(..., description="Mistral API Key")
    STORAGE_DIR: str = Field("./storage", description="Directory for file storage")
    DATABASE_URL: str = Field("sqlite+aiosqlite:///./doc_workflow.db", description="Database URL")
    APP_HOST: str = Field("0.0.0.0", description="FastAPI host")
    APP_PORT: int = Field(8000, description="FastAPI port")
    DEBUG: bool = Field(True, description="Enable debug mode")

    # ── Mistral Studio binding ───────────────────────────────────────────────
    # Every document and claim run executes on Mistral Studio's managed
    # orchestration plane. MISTRAL_WORKFLOW_ID identifies the workflow that
    # dispatch.py starts; DEPLOYMENT_NAME identifies the worker pool that
    # Studio dispatches the activities back to.
    #
    # DEPLOYMENT_NAME is a *version*, not a label. Studio replays an in-flight
    # execution's history against whatever code the pool is running, so a
    # document parked at a 24h wait_for_input will replay tomorrow's code.
    # Bump this on any change to workflow.py's step sequence and drain the old
    # pool rather than cutting over — see README's deploy runbook.
    MISTRAL_WORKFLOW_ID: str = Field(default="", description="Workflow ID from Mistral Studio — dispatch.py starts this")
    DEPLOYMENT_NAME: str = Field(default="document-processing-workflow", description="Mistral Studio worker-pool name. Treat as a version: bump on any workflow.py step change.")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis URL — used by the arq dispatcher and api/queue.py")

    # ── Process topology ─────────────────────────────────────────────────────
    # queue  — the API enqueues to Redis and returns; the arq dispatcher starts
    #          the Studio run, with retry/backoff. The production path.
    # inline — the API starts the Studio run in the request handler. No Redis
    #          required, which is what makes a bare `uvicorn main:app` work
    #          from a venv. Never use in production: a Mistral outage becomes
    #          a failed upload rather than a retried dispatch.
    EXECUTION_MODE: Literal["queue", "inline"] = Field(default="queue", description="How an upload reaches Mistral Studio: via the arq dispatcher (queue) or in-request (inline)")

    # Hosts the Mistral workflow worker inside the API process. A development
    # convenience so one `uvicorn` command is a complete stack; in Docker the
    # worker is its own container and this stays false.
    RUN_WORKFLOW_WORKER_IN_API: bool = Field(default=False, description="Run the Mistral workflow worker inside the API process (local dev only)")

    # ── HTTP surface ─────────────────────────────────────────────────────────
    # The canonical surface is /api/v1/*. The unprefixed paths (/upload,
    # /status/{id}) are the contract an older frontend build calls; they are
    # served by the same handlers and can be switched off once no such build
    # is deployed.
    ENABLE_LEGACY_ROOT_ROUTES: bool = Field(default=True, description="Also serve the v1 handlers at unprefixed root paths (legacy frontend contract)")
    CORS_ORIGINS: list[str] = Field(default=["*"], description="Allowed CORS origins. '*' is incompatible with credentialed requests — set real origins in production.")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, v):
        """Accept a comma-separated string from .env as well as a JSON list."""
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                return v  # let pydantic parse the JSON form
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return v

    # LLM sampling
    LLM_TEMPERATURE: float = Field(0.1, ge=0.0, le=1.0, description="Sampling temperature applied to every Mistral agent and chat completion call")
    LLM_MAX_TOKENS: int = Field(20480, gt=0, description="Max output tokens applied to every Mistral agent and chat completion call")

    # Agent IDs
    CLASSIFIER_AGENT_ID: str = Field(..., description="Classifier Agent ID from Mistral Studio")
    GENERAL_EXTRACTOR_AGENT_ID: str = Field(default="", description="General Extractor Agent ID from Mistral Studio")
    VALIDATOR_AGENT_ID: str = Field(..., description="Validator Agent ID from Mistral Studio")
    REVIEWER_AGENT_ID: str = Field(..., description="Reviewer Agent ID from Mistral Studio")
    OUTPUT_AGENT_ID: str = Field(default="", description="Output Agent ID from Mistral Studio")

    # Pre-Validation Agent
    PRE_VALIDATOR_AGENT_ID: str = Field(default="", description="Pre-Validation Vision Agent ID from Mistral Studio")

    # Intake Agent
    INTAKE_AGENT_ID: str = Field(default="", description="Intake Agent ID from Mistral Studio")

    # Fraud Examiner Agent
    FRAUD_AGENT_ID: str = Field(default="", description="Fraud Examiner Agent ID from Mistral Studio")

    # Preprocessing Step (Step 2.5)
    ENABLE_PREPROCESSING: bool = Field(default=False, description="Enable image preprocessing step (skew correction, brightness/CLAHE, noise removal, resolution normalization)")
    ENABLE_PREPROCESSING_PDF: bool = Field(default=False, description="Also apply preprocessing to PDF files (rasterizes each page). Only effective when ENABLE_PREPROCESSING=true")
    PREPROCESSING_AGENT_ID: str = Field(default="", description="Preprocessing Agent ID from Mistral Studio")

    # Auto-Verifier Agent
    AUTO_VERIFIER_AGENT_ID: str = Field(default="", description="Auto-Verifier Agent ID from Mistral Studio")

    # Document Splitting (Step 1.5)
    # Detects multi-document packets (one upload holding 2-N stitched documents),
    # splits them into per-document PDFs and fans out one child workflow each.
    # Off by default — with the flag false the pipeline behaves exactly as before.
    ENABLE_DOC_SPLITTING: bool = Field(default=False, description="Detect and split multi-document packets (Step 1.5)")
    SPLITTER_AGENT_ID: str = Field(default="", description="Page-Boundary Splitter Agent ID from Mistral Studio")
    SPLIT_CONFIDENCE_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0, description="Below this a page boundary is routed to human review, and the segment's type is not reused downstream")
    SPLIT_PAGE_BATCH_SIZE: int = Field(default=8, gt=0, description="Pages sent to the splitter agent per call")
    SPLIT_MAX_PAGES: int = Field(default=50, gt=0, description="Packets longer than this are processed whole instead of split")
    SPLIT_REQUIRE_REVIEW: bool = Field(default=True, description="Pause for human confirmation of boundaries when any page falls below the confidence threshold")
    SPLIT_MERGE_ORPHANS: bool = Field(default=True, description="Merge a low-confidence single-page outlier back into the surrounding document")

    # Document Checklist (Step 3.2)
    # After each document classifies, reconciles the doc types seen across the
    # whole upload batch against the configured classification types and pauses
    # the batch for a human when a required type was never uploaded.
    ENABLE_DOC_CHECKLIST: bool = Field(default=True, description="Reconcile an upload batch against the configured classification types (Step 3.2)")
    CHECKLIST_AGENT_ID: str = Field(default="", description="Document Checklist Agent ID from Mistral Studio — falls back to a deterministic set-difference when unset")
    CHECKLIST_REQUIRE_REVIEW: bool = Field(default=True, description="Pause the batch for human confirmation when required document types are missing")

    # Signature Verification Agent IDs
    SIGNATURE_VISION_AGENT_ID: str = Field(..., description="Signature Vision Agent ID from Mistral Studio")
    SIGNATURE_JUDGE_AGENT_ID: str = Field(..., description="Signature Judge Agent ID from Mistral Studio")

    # Face Verification Agent IDs (optional — run create_face_agents.py to generate)
    FACE_MORPHOLOGY1_AGENT_ID: str = Field(default="", description="Face Morphology Part 1 Agent ID (Geometry/Eyes/Nose)")
    FACE_MORPHOLOGY2_AGENT_ID: str = Field(default="", description="Face Morphology Part 2 Agent ID (Mouth/Ears/Secondary)")
    FACE_AGE_AGENT_ID: str = Field(default="", description="Face Age Variation Agent ID")
    FACE_JUDGE_AGENT_ID: str = Field(default="", description="Face Judge Agent ID")

    # Claim Processing Agent IDs (create each in Mistral Studio — see agents_config.py)
    CLAIM_INTEGRITY_AGENT_ID: str = Field(default="", description="Claim Integrity Agent ID — validates completeness, dates, policy, duplicates")
    CLAIM_MEDICAL_AGENT_ID: str = Field(default="", description="Medical Agent ID — validates diagnosis, ICD code, provider, documentation")
    CLAIM_TREATMENT_AGENT_ID: str = Field(default="", description="Treatment Agent ID — validates treatment-diagnosis alignment and billing")
    CLAIM_DISABILITY_AGENT_ID: str = Field(default="", description="Disability Agent ID — validates disability certificate and severity")
    CLAIM_LITIGATION_AGENT_ID: str = Field(default="", description="Litigation Agent ID — detects attorney involvement and fraud red flags")
    CLAIM_REPORT_AGENT_ID: str = Field(default="", description="Claim Report Agent ID — generates the final suggestion paragraph")

    # Google Document AI settings
    GOOGLE_APPLICATION_CREDENTIALS: str = Field(default="", description="Path to Google Cloud service account JSON key file")
    DOCUMENTAI_PROJECT_ID: str = Field(default="458272416814", description="Google Cloud Project ID")
    DOCUMENTAI_LOCATION: str = Field(default="us", description="Document AI processor location (us or eu)")
    DOCUMENTAI_PROCESSOR_ID: str = Field(default="ae6356d350bf69a6", description="Document AI Identity document proofing processor ID")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


try:
    settings = Settings()
except ValidationError as e:
    print("Startup Error: Missing required environment variables. Ensure all Agent IDs and MISTRAL_API_KEY are provided in .env.")
    print(e)
    import sys
    sys.exit(1)


# ─── Mistral Studio agent binding ────────────────────────────────────────────
# Each entry maps a settings field to the pipeline capability it powers. Every
# one of these defaults to "" and every call site degrades *silently* when it is
# unset — an unbound PRE_VALIDATOR_AGENT_ID skips quality gating entirely, an
# unbound CHECKLIST_AGENT_ID drops to a deterministic summary, an unbound
# SPLITTER_AGENT_ID disables packet splitting. In a container that reads as
# "working", so /ready reports the binding and startup can refuse to come up.
OPTIONAL_AGENT_BINDINGS: dict[str, str] = {
    "GENERAL_EXTRACTOR_AGENT_ID": "field extraction (Step 4)",
    "OUTPUT_AGENT_ID": "final output shaping (Step 7)",
    "PRE_VALIDATOR_AGENT_ID": "quality pre-validation (Step 2)",
    "INTAKE_AGENT_ID": "intake narration (Step 1)",
    "FRAUD_AGENT_ID": "fraud examination (Step 3.5)",
    "PREPROCESSING_AGENT_ID": "image preprocessing (Step 2.5)",
    "AUTO_VERIFIER_AGENT_ID": "automated KYC verification (Step 5.5)",
    "SPLITTER_AGENT_ID": "multi-document packet splitting (Step 1.5)",
    "CHECKLIST_AGENT_ID": "batch checklist narration (Step 3.2)",
    "FACE_MORPHOLOGY1_AGENT_ID": "face verification — morphology part 1",
    "FACE_MORPHOLOGY2_AGENT_ID": "face verification — morphology part 2",
    "FACE_AGE_AGENT_ID": "face verification — age variation",
    "FACE_JUDGE_AGENT_ID": "face verification — adjudication",
    "CLAIM_INTEGRITY_AGENT_ID": "claim integrity checks",
    "CLAIM_MEDICAL_AGENT_ID": "claim medical validation",
    "CLAIM_TREATMENT_AGENT_ID": "claim treatment validation",
    "CLAIM_DISABILITY_AGENT_ID": "claim disability validation",
    "CLAIM_LITIGATION_AGENT_ID": "claim litigation screening",
    "CLAIM_REPORT_AGENT_ID": "claim report generation",
}

# Bindings without which the deployment is not serviceable at all. Unlike the
# table above these are enforced: see bootstrap.assert_agent_bindings().
REQUIRED_AGENT_IDS: tuple[str, ...] = (
    "CLASSIFIER_AGENT_ID",
    "VALIDATOR_AGENT_ID",
    "REVIEWER_AGENT_ID",
    "SIGNATURE_VISION_AGENT_ID",
    "SIGNATURE_JUDGE_AGENT_ID",
)


def agent_binding_report() -> dict:
    """
    Which Studio agents this process is bound to, and what is lost where one is
    not. Surfaced by GET /ready so a degraded deployment is visible instead of
    quietly doing less work.
    """
    unbound = {
        field: capability
        for field, capability in OPTIONAL_AGENT_BINDINGS.items()
        if not getattr(settings, field, "")
    }
    missing_required = [f for f in REQUIRED_AGENT_IDS if not getattr(settings, f, "")]
    return {
        "workflow_id_bound": bool(settings.MISTRAL_WORKFLOW_ID),
        "deployment_name": settings.DEPLOYMENT_NAME,
        "required_missing": missing_required,
        "bound": len(OPTIONAL_AGENT_BINDINGS) - len(unbound),
        "total_optional": len(OPTIONAL_AGENT_BINDINGS),
        "degraded_capabilities": unbound,
    }

SUPPORTED_DOCUMENT_TYPES = [
    "invoice",
    "pan_card",
    "id_proof",
    "driving_licence",
    "driving_license",
    "claim_form",
    "tax_form",
    "medical_report",
    "lab_reports",
    "prescription_records",
    "bills_invoices",
    "disability_certificate",
    "legal_letter",
    "utility_bill",
    "Bank_Statement",
    "policy_adjustment_form"
]

