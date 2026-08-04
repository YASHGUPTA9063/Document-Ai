from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, event
from config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for col in [
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS customer_id VARCHAR",
            "ALTER TABLE extracted_data ADD COLUMN IF NOT EXISTS signature_verification JSON",
            "ALTER TABLE extracted_data ADD COLUMN IF NOT EXISTS photo_verification JSON",
            "ALTER TABLE extracted_data ADD COLUMN IF NOT EXISTS fraud_check JSON",
        ]:
            try:
                async with conn.begin_nested():
                    await conn.execute(text(col))
            except Exception:
                pass


async def init_claim_tables():
    """
    Ensures all claim processing tables exist.
    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS via SQLAlchemy metadata.
    Also runs defensive ALTER TABLE migrations for any columns added after initial creation.
    """
    async with engine.begin() as conn:
        # Import claim models so SQLAlchemy registers them on Base.metadata
        from db.models import Claim, ClaimDocument, ClaimantHistory, PolicyDetails, ClaimReport, ClaimDocumentLink  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

        # Defensive migrations for Claim columns added in this iteration
        for col in [
            "ALTER TABLE claims ADD COLUMN IF NOT EXISTS claim_type VARCHAR",
            "ALTER TABLE claims ADD COLUMN IF NOT EXISTS amount FLOAT",
            "ALTER TABLE claims ADD COLUMN IF NOT EXISTS priority VARCHAR",
            "ALTER TABLE claims ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE claims ADD COLUMN IF NOT EXISTS workflow_run_id VARCHAR",
        ]:
            try:
                async with conn.begin_nested():
                    await conn.execute(text(col))
            except Exception:
                pass
