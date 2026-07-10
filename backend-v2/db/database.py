from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

from sqlalchemy import text

Base = declarative_base()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN file_hash VARCHAR"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN customer_id VARCHAR"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE extracted_data ADD COLUMN signature_verification JSON"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE extracted_data ADD COLUMN photo_verification JSON"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE extracted_data ADD COLUMN fraud_check JSON"))
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
        from db.models import Claim, ClaimDocument, ClaimantHistory, PolicyDetails, ClaimReport  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
