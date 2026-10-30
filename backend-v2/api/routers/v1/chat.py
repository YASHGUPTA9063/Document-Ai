"""
Chat Router
===========
Question answering over every uploaded document (RAG).

Uploads are copied into a Mistral document library as they arrive (see
utils/rag_library.py and api.queue.submit_library_push). The chat endpoint
starts a Mistral conversation bound to that library, so retrieval, chunking and
embedding all happen on Mistral's side and this router only relays the turn.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import settings
from api.queue import submit_library_push
import utils.rag_library as rag

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(None, description="Continue an earlier conversation; omit to start a new one")


def _require_enabled() -> None:
    if not settings.ENABLE_RAG_CHAT:
        raise HTTPException(status_code=404, detail="Document chat is disabled on this deployment.")


@router.post("/chat")
async def chat(request: ChatRequest):
    """Answer one question from the document library, with the documents it cited."""
    _require_enabled()
    try:
        return await rag.ask(request.message.strip(), request.conversation_id)
    except Exception as e:
        logger.error("[Chat] Turn failed (conversation %s): %s", request.conversation_id, e)
        raise HTTPException(status_code=502, detail=f"The document assistant could not answer: {e}")


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a chat session's conversation on Mistral.

    The history holds the document excerpts the session retrieved, so deleting
    the session in the UI should not leave them behind on Mistral's side.
    """
    _require_enabled()
    try:
        await rag.delete_conversation(conversation_id)
    except Exception as e:
        logger.warning("[Chat] Could not delete conversation %s: %s", conversation_id, e)
        raise HTTPException(status_code=502, detail=f"Could not delete the conversation: {e}")
    return {"deleted": True, "conversation_id": conversation_id}


@router.get("/chat/library")
async def get_library():
    """Every document's library status — indexed documents are the ones chat can see."""
    _require_enabled()
    return await rag.list_library()


@router.post("/chat/library/sync")
async def sync_library():
    """
    Push every document that is not in the library yet, or whose push failed.

    Covers documents uploaded before the chat feature existed, and recovers
    pushes that ran out of retries.
    """
    _require_enabled()
    document_ids = await rag.documents_needing_push()
    for document_id in document_ids:
        await submit_library_push(document_id)
    return {"queued": len(document_ids), "document_ids": document_ids}
