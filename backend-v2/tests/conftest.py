"""
Test environment bootstrap.

Imported by pytest before any test module, which matters because config.py
builds its Settings at import time and db/database.py builds the engine from
DATABASE_URL at import time. Setting these here means `pytest` works from a
clean checkout with no exported environment.

The database is a real SQLite file in a temp directory, not a mock: the
document and claim endpoints query through SQLAlchemy directly, so a mocked
session tests nothing. The file is created once per session and torn down
after.
"""

import os
import tempfile
import pathlib

_TMP_DIR = tempfile.mkdtemp(prefix="docai-tests-")
_DB_PATH = pathlib.Path(_TMP_DIR) / "test.db"

os.environ.setdefault("MISTRAL_API_KEY", "test-key")
os.environ.setdefault("CLASSIFIER_AGENT_ID", "test-classifier")
os.environ.setdefault("VALIDATOR_AGENT_ID", "test-validator")
os.environ.setdefault("REVIEWER_AGENT_ID", "test-reviewer")
os.environ.setdefault("SIGNATURE_VISION_AGENT_ID", "test-sig-vision")
os.environ.setdefault("SIGNATURE_JUDGE_AGENT_ID", "test-sig-judge")
os.environ.setdefault("MISTRAL_WORKFLOW_ID", "test-workflow")

# Forward slashes: SQLAlchemy's SQLite URL parser does not accept backslashes.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH.as_posix()}"
os.environ["STORAGE_DIR"] = str(pathlib.Path(_TMP_DIR) / "storage")

# Inline keeps Redis out of the test path; nothing here starts a real run.
os.environ["EXECUTION_MODE"] = "inline"
os.environ["RUN_WORKFLOW_WORKER_IN_API"] = "false"
os.environ["DEBUG"] = "true"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """
    Create the schema once for the whole session, and dispose the engine after.

    The dispose matters: aiosqlite runs each connection on its own thread, and
    a live connection pool at interpreter exit leaves those threads running, so
    pytest reports its results and then never exits.
    """
    import asyncio
    from db.database import engine, Base
    from db import models  # noqa: F401  — registers the tables on Base

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())

    yield

    async def _dispose():
        await engine.dispose()

    asyncio.run(_dispose())
