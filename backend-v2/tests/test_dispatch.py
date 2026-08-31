"""
Dispatch and queue-mode tests
=============================
Covers the layer that replaced three ad-hoc `execute_workflow_async` call sites
(the upload endpoint, the arq worker, the split fan-out), each of which passed a
different combination of execution_id and deployment_name — leaving Studio
executions impossible to correlate back to a document.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from platform_core import dispatch


def _fake_client(execution_id="exec-123"):
    client = MagicMock()
    response = MagicMock()
    response.execution_id = execution_id
    client.workflows.execute_workflow_async = AsyncMock(return_value=response)
    return client


class TestExecutionIds:
    def test_execution_id_is_correlatable_and_unique(self):
        """
        The id has to name the document, so a Studio execution can be traced
        back to a row, and still differ per attempt: Studio rejects a reused
        id, and a document is legitimately re-run on retry or duplicate
        override.
        """
        first = dispatch._execution_id("doc", "abc123")
        second = dispatch._execution_id("doc", "abc123")

        assert first.startswith("doc-abc123-")
        assert second.startswith("doc-abc123-")
        assert first != second


class TestStartDocumentRun:
    @pytest.mark.asyncio
    async def test_passes_deployment_name_and_execution_id(self):
        """
        Both were omitted by the upload endpoint before this module existed,
        which left the run unattributable and pinned to no worker-pool version.
        """
        client = _fake_client()
        with patch.object(dispatch, "get_mistral_client", return_value=client), \
             patch.object(dispatch.settings, "MISTRAL_WORKFLOW_ID", "wf-1"), \
             patch.object(dispatch.settings, "DEPLOYMENT_NAME", "pool-v2"):
            run_id = await dispatch.start_document_run("doc1", "a.pdf", "/tmp/a.pdf")

        assert run_id == "exec-123"
        kwargs = client.workflows.execute_workflow_async.await_args.kwargs
        assert kwargs["workflow_identifier"] == "wf-1"
        assert kwargs["deployment_name"] == "pool-v2"
        assert kwargs["execution_id"].startswith("doc-doc1-")

    @pytest.mark.asyncio
    async def test_falls_back_to_workflow_name_without_an_id(self):
        client = _fake_client()
        with patch.object(dispatch, "get_mistral_client", return_value=client), \
             patch.object(dispatch.settings, "MISTRAL_WORKFLOW_ID", ""):
            await dispatch.start_document_run("doc1", "a.pdf", "/tmp/a.pdf")

        kwargs = client.workflows.execute_workflow_async.await_args.kwargs
        assert kwargs["workflow_identifier"] == dispatch.DOCUMENT_WORKFLOW

    @pytest.mark.asyncio
    async def test_split_child_arguments_reach_the_workflow(self):
        """
        A child of a split packet must carry auto_split=False (the recursion
        guard) and its pre-classification, so it skips Step 3 rather than
        paying for a classification the splitter already did.
        """
        client = _fake_client()
        with patch.object(dispatch, "get_mistral_client", return_value=client):
            await dispatch.start_document_run(
                "child1", "child.pdf", "/tmp/child.pdf",
                auto_split=False,
                preclassified_doc_type="pan_card",
                preclassified_confidence=0.91,
            )

        payload = client.workflows.execute_workflow_async.await_args.kwargs["input"]
        assert payload["auto_split"] is False
        assert payload["preclassified_doc_type"] == "pan_card"
        assert payload["preclassified_confidence"] == 0.91

    @pytest.mark.asyncio
    async def test_wraps_sdk_errors_in_dispatch_error(self):
        """arq retries on DispatchError, so the SDK exception must not leak."""
        client = MagicMock()
        client.workflows.execute_workflow_async = AsyncMock(side_effect=RuntimeError("network"))

        with patch.object(dispatch, "get_mistral_client", return_value=client):
            with pytest.raises(dispatch.DispatchError):
                await dispatch.start_document_run("doc1", "a.pdf", "/tmp/a.pdf")


class TestStartDocumentRunAndRecord:
    @pytest.mark.asyncio
    async def test_records_the_run_id(self):
        client = _fake_client("exec-999")
        with patch.object(dispatch, "get_mistral_client", return_value=client), \
             patch("db.operations.update_workflow_run_id", new=AsyncMock()) as update:
            run_id = await dispatch.start_document_run_and_record("doc1", "a.pdf", "/tmp/a.pdf")

        assert run_id == "exec-999"
        update.assert_awaited_once_with("doc1", "exec-999")

    @pytest.mark.asyncio
    async def test_marks_the_document_failed_when_dispatch_fails(self):
        """
        A document whose run never started must not sit at `pending` forever
        with nothing to explain why.
        """
        client = MagicMock()
        client.workflows.execute_workflow_async = AsyncMock(side_effect=RuntimeError("boom"))

        with patch.object(dispatch, "get_mistral_client", return_value=client), \
             patch("db.operations.update_error", new=AsyncMock()) as err, \
             patch("db.operations.update_status_and_message", new=AsyncMock()) as status:
            with pytest.raises(dispatch.DispatchError):
                await dispatch.start_document_run_and_record("doc1", "a.pdf", "/tmp/a.pdf")

        err.assert_awaited_once()
        assert status.await_args.args[1] == "failed"


class TestSubmitDocumentRun:
    @pytest.mark.asyncio
    async def test_inline_mode_dispatches_directly(self):
        from api import queue

        with patch.object(queue.settings, "EXECUTION_MODE", "inline"), \
             patch("platform_core.dispatch.start_document_run_and_record",
                   new=AsyncMock(return_value="exec-1")) as start:
            run_id = await queue.submit_document_run("doc1", "a.pdf", "/tmp/a.pdf")

        assert run_id == "exec-1"
        start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_queue_mode_enqueues_and_returns_none(self):
        """
        Under `queue` the execution id is not known yet — the dispatcher
        assigns it. Callers must treat None as "started", not as a failure.
        """
        from api import queue

        pool = MagicMock()
        pool.enqueue_job = AsyncMock()

        with patch.object(queue.settings, "EXECUTION_MODE", "queue"), \
             patch.object(queue, "get_redis_pool", new=AsyncMock(return_value=pool)):
            run_id = await queue.submit_document_run("doc1", "a.pdf", "/tmp/a.pdf")

        assert run_id is None
        assert pool.enqueue_job.await_args.kwargs["_job_id"] == "doc-doc1"

    @pytest.mark.asyncio
    async def test_retry_uses_a_distinct_job_key(self):
        """
        arq refuses to enqueue a job id it still holds a result for. Reusing
        the default key would make a retry a silent no-op for as long as
        WorkerSettings.keep_result.
        """
        from api import queue

        pool = MagicMock()
        pool.enqueue_job = AsyncMock()

        with patch.object(queue.settings, "EXECUTION_MODE", "queue"), \
             patch.object(queue, "get_redis_pool", new=AsyncMock(return_value=pool)):
            await queue.submit_document_run(
                "doc1", "a.pdf", "/tmp/a.pdf", job_key="doc-doc1-retry-abcd1234"
            )

        assert pool.enqueue_job.await_args.kwargs["_job_id"] == "doc-doc1-retry-abcd1234"

    @pytest.mark.asyncio
    async def test_claim_reruns_are_never_deduplicated(self):
        """`/claims/{id}/rerun` is an explicit user action; dedup would eat it."""
        from api import queue

        pool = MagicMock()
        pool.enqueue_job = AsyncMock()

        with patch.object(queue.settings, "EXECUTION_MODE", "queue"), \
             patch.object(queue, "get_redis_pool", new=AsyncMock(return_value=pool)):
            await queue.submit_claim_run("CLM-1", "CLA-1", "POL-1")
            first = pool.enqueue_job.await_args.kwargs["_job_id"]
            await queue.submit_claim_run("CLM-1", "CLA-1", "POL-1")
            second = pool.enqueue_job.await_args.kwargs["_job_id"]

        assert first != second
        assert first.startswith("claim-CLM-1-")
