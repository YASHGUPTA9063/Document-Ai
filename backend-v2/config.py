from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError

class Settings(BaseSettings):
    MISTRAL_API_KEY: str = Field(..., description="Mistral API Key")
    STORAGE_DIR: str = Field("./storage", description="Directory for file storage")
    DATABASE_URL: str = Field("sqlite+aiosqlite:///./doc_workflow.db", description="Database URL")
    APP_HOST: str = Field("0.0.0.0", description="FastAPI host")
    APP_PORT: int = Field(8000, description="FastAPI port")
    DEBUG: bool = Field(True, description="Enable debug mode")

    # Optional: platform_core queue path (worker.py + api/queue.py). Neither is
    # used by the default deployment, where document and claim processing run
    # on the Mistral Workflows SDK inside the app process. Declared with empty
    # defaults so worker.py can report a clear "not set" error instead of
    # dying with AttributeError.
    MISTRAL_WORKFLOW_ID: str = Field(default="", description="Workflow ID from Mistral Studio — only needed by the arq worker")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis URL — only needed by the arq worker / api.queue")

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

