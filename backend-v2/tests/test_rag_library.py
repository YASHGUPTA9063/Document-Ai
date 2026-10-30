"""
RAG document library: pushing uploads to Mistral and parsing chat answers.

The Mistral client is mocked; the database is the real SQLite test database,
because push idempotency is a property of the library_documents rows.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import utils.rag_library as rag
from db.database import AsyncSessionLocal
from db.models import Document, LibraryDocument


async def _make_document(tmp_path, **fields) -> str:
    path = tmp_path / f"{uuid.uuid4().hex}.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    async with AsyncSessionLocal() as session:
        doc = Document(filename=fields.pop("filename", "policy.pdf"), file_path=str(path), status="pending", **fields)
        session.add(doc)
        await session.commit()
        return doc.id


async def _library_row(document_id: str) -> LibraryDocument | None:
    from sqlalchemy.future import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LibraryDocument).where(LibraryDocument.document_id == document_id)
        )
        return result.scalar_one_or_none()


def _client(upload=None):
    client = MagicMock()
    client.beta.libraries.documents.upload_async = upload or AsyncMock(
        return_value=SimpleNamespace(id="mdoc-1", process_status="todo")
    )
    return client


class TestParseConversationOutputs:
    def test_text_and_references_become_answer_with_numbered_sources(self):
        outputs = [
            {"type": "tool.execution", "name": "document_library"},
            {
                "type": "message.output",
                "content": [
                    {"type": "text", "text": "The policy number is P-123."},
                    {"type": "tool_reference", "title": "policy.pdf", "tool": "document_library"},
                    {"type": "text", "text": " The insured is A. Rao."},
                    {"type": "tool_reference", "title": "kyc.pdf", "tool": "document_library"},
                    {"type": "tool_reference", "title": "policy.pdf", "tool": "document_library"},
                ],
            },
        ]

        answer, sources = rag.parse_conversation_outputs(outputs)

        assert answer == "The policy number is P-123.[1] The insured is A. Rao.[2][1]"
        assert [(s["index"], s["title"]) for s in sources] == [(1, "policy.pdf"), (2, "kyc.pdf")]

    def test_plain_string_content(self):
        answer, sources = rag.parse_conversation_outputs(
            [{"type": "message.output", "content": "Hello! Ask me about your documents."}]
        )
        assert answer == "Hello! Ask me about your documents."
        assert sources == []

    def test_repeated_reference_is_not_marked_twice_in_a_row(self):
        answer, _ = rag.parse_conversation_outputs([{
            "type": "message.output",
            "content": [
                {"type": "text", "text": "Fact."},
                {"type": "tool_reference", "title": "a.pdf"},
                {"type": "tool_reference", "title": "a.pdf"},
            ],
        }])
        assert answer == "Fact.[1]"


class TestPushDocument:
    @pytest.mark.asyncio
    async def test_push_records_library_id_and_is_idempotent(self, tmp_path):
        document_id = await _make_document(tmp_path)
        client = _client()

        with patch.object(rag.settings, "MISTRAL_LIBRARY_ID", "lib-1"), \
             patch.object(rag, "get_mistral_client", return_value=client):
            first = await rag.push_document(document_id)
            second = await rag.push_document(document_id)

        assert first["status"] == "processing"
        assert second["mistral_document_id"] == "mdoc-1"
        client.beta.libraries.documents.upload_async.assert_awaited_once()
        assert client.beta.libraries.documents.upload_async.await_args.kwargs["file"]["file_name"] == "policy.pdf"

        row = await _library_row(document_id)
        assert (row.library_id, row.mistral_document_id, row.status) == ("lib-1", "mdoc-1", "processing")

    @pytest.mark.asyncio
    async def test_failed_push_is_recorded_and_raised_then_retryable(self, tmp_path):
        document_id = await _make_document(tmp_path)
        failing = _client(upload=AsyncMock(side_effect=RuntimeError("library unavailable")))

        with patch.object(rag.settings, "MISTRAL_LIBRARY_ID", "lib-1"), \
             patch.object(rag, "get_mistral_client", return_value=failing):
            with pytest.raises(RuntimeError):
                await rag.push_document(document_id)

        row = await _library_row(document_id)
        assert row.status == "failed"
        assert "library unavailable" in row.error
        assert document_id in await rag.documents_needing_push()

        with patch.object(rag.settings, "MISTRAL_LIBRARY_ID", "lib-1"), \
             patch.object(rag, "get_mistral_client", return_value=_client()):
            result = await rag.push_document(document_id)

        assert result["status"] == "processing"
        assert document_id not in await rag.documents_needing_push()

    @pytest.mark.asyncio
    async def test_split_children_are_not_pushed_by_sync(self, tmp_path):
        parent_id = await _make_document(tmp_path, filename="packet.pdf")
        child_id = await _make_document(tmp_path, filename="packet_part1.pdf", parent_document_id=parent_id)

        pending = await rag.documents_needing_push()

        assert parent_id in pending
        assert child_id not in pending


class TestSubmitLibraryPush:
    @pytest.mark.asyncio
    async def test_disabled_is_a_no_op(self):
        from api import queue

        with patch.object(queue.settings, "ENABLE_RAG_CHAT", False), \
             patch.object(queue, "get_redis_pool", new=AsyncMock()) as pool:
            await queue.submit_library_push("doc1")

        pool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_queue_mode_enqueues_push_job(self):
        from api import queue

        pool = MagicMock()
        pool.enqueue_job = AsyncMock()

        with patch.object(queue.settings, "ENABLE_RAG_CHAT", True), \
             patch.object(queue.settings, "EXECUTION_MODE", "queue"), \
             patch.object(queue, "get_redis_pool", new=AsyncMock(return_value=pool)):
            await queue.submit_library_push("doc1")

        assert pool.enqueue_job.await_args.args == ("push_document_to_library", "doc1")

    @pytest.mark.asyncio
    async def test_scheduling_failure_never_fails_the_upload(self):
        from api import queue

        with patch.object(queue.settings, "ENABLE_RAG_CHAT", True), \
             patch.object(queue.settings, "EXECUTION_MODE", "queue"), \
             patch.object(queue, "get_redis_pool", new=AsyncMock(side_effect=ConnectionError("redis down"))):
            await queue.submit_library_push("doc1")  # must not raise
