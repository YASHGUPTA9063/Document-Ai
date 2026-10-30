"""
RAG Document Library
====================
Every uploaded document is copied into one Mistral document library, and the
chat endpoint answers questions over that library with Mistral's
`document_library` tool. Mistral owns chunking, embedding and retrieval; this
module owns three things:

  * which library — MISTRAL_LIBRARY_ID, or one found or created by
    MISTRAL_LIBRARY_NAME on first use;
  * the push — upload a document's file and track its indexing status in the
    `library_documents` table;
  * the conversation — start or continue a Mistral conversation bound to the
    library, and turn its output into an answer plus the documents it cited.

Pushes are dispatched by api.queue.submit_library_push, so under
EXECUTION_MODE=queue they run in the arq dispatcher with retries and never hold
up an upload request.
"""

import asyncio
import logging
import os
from contextlib import suppress

from sqlalchemy import desc
from sqlalchemy.future import select

from config import settings
from db.database import AsyncSessionLocal
from db.models import Document, LibraryDocument
from platform_core.adapters.resilient_mistral import get_mistral_client
from platform_core.prompts.manager import PromptManager

logger = logging.getLogger(__name__)

PROMPTS = PromptManager()

# Library-side process_status -> our status. Anything not listed is still
# being worked on by Mistral ("todo", "in_progress", "waiting_for_capacity").
_STATUS_MAP = {
    "done": "indexed",
    "noop": "indexed",
    "self_managed": "indexed",
    "error": "failed",
    "missing_content": "failed",
}

_library_id: str | None = None
_library_lock = asyncio.Lock()


def _local_status(process_status) -> str:
    return _STATUS_MAP.get(str(process_status), "processing")


def _field(obj, name):
    """Read a field from an SDK model or a plain dict; SDK UNSET reads as None."""
    value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
    return value if isinstance(value, (str, list, int, float)) else None


def _row_dict(row: LibraryDocument) -> dict:
    return {
        "document_id": row.document_id,
        "filename": row.filename,
        "status": row.status,
        "error": row.error,
        "mistral_document_id": row.mistral_document_id,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ─── Library resolution ──────────────────────────────────────────────────────

async def _oldest_named_library(client) -> str | None:
    name = settings.MISTRAL_LIBRARY_NAME
    resp = await client.beta.libraries.list_async(search=name, page_size=100)
    matches = [lib for lib in resp.data if lib.name == name]
    if not matches:
        return None
    return min(matches, key=lambda lib: lib.created_at).id


async def get_library_id() -> str:
    """
    The library every push and every chat goes to.

    Without MISTRAL_LIBRARY_ID, the API workers and the dispatcher may all reach
    here at once on a fresh deployment and each create a library. They converge
    by always using the oldest library with the configured name, and a process
    whose own creation lost that race deletes it again.
    """
    global _library_id
    if settings.MISTRAL_LIBRARY_ID:
        return settings.MISTRAL_LIBRARY_ID
    if _library_id:
        return _library_id

    async with _library_lock:
        if _library_id:
            return _library_id

        client = get_mistral_client()
        found = await _oldest_named_library(client)
        if found is None:
            created = await client.beta.libraries.create_async(
                name=settings.MISTRAL_LIBRARY_NAME,
                description="Documents uploaded to the Document AI platform, searched by the document chat.",
            )
            found = await _oldest_named_library(client) or created.id
            if found != created.id:
                with suppress(Exception):
                    await client.beta.libraries.delete_async(library_id=created.id)
            logger.info("[RAG] Created document library %s (%s)", found, settings.MISTRAL_LIBRARY_NAME)

        _library_id = found
        return _library_id


# ─── Push ────────────────────────────────────────────────────────────────────

async def _update_row(document_id: str, **fields) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LibraryDocument).where(LibraryDocument.document_id == document_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        await session.commit()


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


async def push_document(document_id: str) -> dict:
    """
    Upload one document's file to the library.

    Idempotent: a document already uploaded (anything but `failed`) is left
    alone, so a double-submitted job or a re-sync never creates a duplicate in
    the library. Raises on failure after recording it, so the caller can retry.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None or doc.status == "deleted":
            return {"document_id": document_id, "status": "skipped"}

        result = await session.execute(
            select(LibraryDocument).where(LibraryDocument.document_id == document_id)
        )
        row = result.scalar_one_or_none()
        if row is not None and row.mistral_document_id and row.status != "failed":
            return _row_dict(row)

        if row is None:
            row = LibraryDocument(document_id=document_id, filename=doc.filename)
            session.add(row)
        row.status = "queued"
        row.error = None
        await session.commit()
        filename, file_path = doc.filename, doc.file_path

    # The upload is a network call of unbounded length, so no session is held
    # open across it.
    try:
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"File for document {document_id} is missing on disk")
        content = await asyncio.to_thread(_read_bytes, file_path)
        library_id = await get_library_id()
        uploaded = await get_mistral_client().beta.libraries.documents.upload_async(
            library_id=library_id,
            file={"file_name": filename, "content": content},
        )
    except Exception as e:
        await _update_row(document_id, status="failed", error=str(e)[:2000])
        raise

    status = _local_status(uploaded.process_status)
    await _update_row(
        document_id,
        library_id=library_id,
        mistral_document_id=uploaded.id,
        status=status,
        error=None,
    )
    logger.info("[RAG] Pushed document %s to library as %s (%s)", document_id, uploaded.id, status)
    return {"document_id": document_id, "status": status, "mistral_document_id": uploaded.id}


async def detach_document(session, document_id: str) -> None:
    """
    Remove a deleted document from the library, inside the caller's session.

    Best-effort: a library that cannot be reached must not block a deletion,
    so a failed remote delete is logged and the row is marked deleted anyway.
    """
    result = await session.execute(
        select(LibraryDocument).where(LibraryDocument.document_id == document_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return
    if row.library_id and row.mistral_document_id:
        try:
            await get_mistral_client().beta.libraries.documents.delete_async(
                library_id=row.library_id, document_id=row.mistral_document_id,
            )
        except Exception as e:
            logger.warning("[RAG] Could not remove document %s from the library: %s", document_id, e)
    row.status = "deleted"


async def documents_needing_push() -> list[str]:
    """
    Live documents with no library copy, or whose push failed.

    Split children are skipped: their parent packet holds the same pages, and
    pushing both would put every page in the library twice.
    """
    async with AsyncSessionLocal() as session:
        pushed = select(LibraryDocument.document_id).where(LibraryDocument.status != "failed")
        result = await session.execute(
            select(Document.id)
            .where(Document.status != "deleted")
            .where(Document.parent_document_id.is_(None))
            .where(Document.id.not_in(pushed))
        )
        return list(result.scalars().all())


# ─── Status ──────────────────────────────────────────────────────────────────

async def _refresh_one(client, row: LibraryDocument) -> None:
    try:
        status = await client.beta.libraries.documents.status_async(
            library_id=row.library_id, document_id=row.mistral_document_id,
        )
    except Exception as e:
        logger.debug("[RAG] Status check failed for %s: %s", row.document_id, e)
        return
    row.status = _local_status(status.process_status)


async def list_library() -> dict:
    """
    Every document's library status, refreshing the ones still being indexed.

    Mistral indexes asynchronously after an upload, so a document's status only
    moves from `processing` to `indexed` when someone asks — this is that ask.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LibraryDocument)
            .where(LibraryDocument.status != "deleted")
            .order_by(desc(LibraryDocument.created_at))
        )
        rows = list(result.scalars().all())

        pending = [r for r in rows if r.status == "processing" and r.mistral_document_id and r.library_id]
        if pending:
            client = get_mistral_client()
            await asyncio.gather(*[_refresh_one(client, r) for r in pending[:50]])
            await session.commit()

        items = [_row_dict(r) for r in rows]

    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"total": len(items), "counts": counts, "documents": items}


# ─── Chat ────────────────────────────────────────────────────────────────────

def parse_conversation_outputs(outputs) -> tuple[str, list[dict]]:
    """
    Flatten a conversation response into answer text and its sources.

    The assistant's message arrives as a list of chunks in which `text` chunks
    carry the answer and `tool_reference` chunks follow the sentence they
    support. Each distinct reference becomes a numbered source, and a `[n]`
    marker is left where it appeared so the answer keeps its citations.
    """
    parts: list[str] = []
    sources: list[dict] = []
    index_by_title: dict[str, int] = {}

    for entry in outputs or []:
        if _field(entry, "type") != "message.output":
            continue
        content = _field(entry, "content")
        if isinstance(content, str):
            parts.append(content)
            continue
        for chunk in content or []:
            kind = _field(chunk, "type")
            if kind == "text":
                parts.append(_field(chunk, "text") or "")
            elif kind == "tool_reference":
                title = _field(chunk, "title") or "Untitled document"
                if title not in index_by_title:
                    index_by_title[title] = len(sources) + 1
                    sources.append({
                        "index": index_by_title[title],
                        "title": title,
                        "description": _field(chunk, "description"),
                        "url": _field(chunk, "url"),
                    })
                marker = f"[{index_by_title[title]}]"
                if not (parts and parts[-1].endswith(marker)):
                    parts.append(marker)

    return "".join(parts).strip(), sources


async def _link_sources(sources: list[dict]) -> list[dict]:
    """Attach our document id to each source, matched by the uploaded filename."""
    titles = [s["title"] for s in sources]
    if not titles:
        return sources
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LibraryDocument)
            .where(LibraryDocument.filename.in_(titles))
            .where(LibraryDocument.status != "deleted")
            .order_by(desc(LibraryDocument.created_at))
        )
        by_name: dict[str, str] = {}
        for row in result.scalars().all():
            by_name.setdefault(row.filename, row.document_id)
    for source in sources:
        source["document_id"] = by_name.get(source["title"])
    return sources


async def delete_conversation(conversation_id: str) -> None:
    """Delete a stored conversation, and with it every document excerpt it retrieved."""
    await get_mistral_client().beta.conversations.delete_async(conversation_id=conversation_id)


async def ask(message: str, conversation_id: str | None = None) -> dict:
    """
    Answer one chat turn.

    The first turn starts a stored Mistral conversation bound to the library;
    later turns append to it by id, so the history lives with Mistral and the
    client only has to remember `conversation_id`.
    """
    client = get_mistral_client()
    if conversation_id:
        resp = await client.beta.conversations.append_async(
            conversation_id=conversation_id,
            inputs=message,
        )
    else:
        library_id = await get_library_id()
        resp = await client.beta.conversations.start_async(
            model=settings.RAG_CHAT_MODEL,
            instructions=PROMPTS.get("rag_chat"),
            tools=[{"type": "document_library", "library_ids": [library_id]}],
            completion_args={"temperature": settings.LLM_TEMPERATURE},
            inputs=message,
            store=True,
        )

    answer, sources = parse_conversation_outputs(resp.outputs)
    return {
        "conversation_id": resp.conversation_id,
        "answer": answer or "I could not produce an answer to that.",
        "sources": await _link_sources(sources),
    }
