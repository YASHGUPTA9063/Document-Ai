from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError

class Settings(BaseSettings):
    MISTRAL_API_KEY: str = Field(..., description="Mistral API Key")
    STORAGE_DIR: str = Field("./storage", description="Directory for file storage")
    DATABASE_URL: str = Field("sqlite+aiosqlite:///./doc_workflow.db", description="Database URL")
    APP_HOST: str = Field("0.0.0.0", description="FastAPI host")
    APP_PORT: int = Field(8000, description="FastAPI port")
    DEBUG: bool = Field(True, description="Enable debug mode")

    # Agent IDs
    CLASSIFIER_AGENT_ID: str = Field(..., description="Classifier Agent ID from Mistral Studio")
    EXTRACTOR_AGENT_ID: str = Field(..., description="Extractor Agent ID from Mistral Studio")
    VALIDATOR_AGENT_ID: str = Field(..., description="Validator Agent ID from Mistral Studio")
    REVIEWER_AGENT_ID: str = Field(..., description="Reviewer Agent ID from Mistral Studio")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

try:
    settings = Settings()
except ValidationError as e:
    print("Startup Error: Missing required environment variables. Ensure all Agent IDs and MISTRAL_API_KEY are provided in .env.")
    print(e)
    import sys
    sys.exit(1)
