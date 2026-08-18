"""
utils/batch_client.py
──────────────────────
Helper utility for managing Mistral Batch API jobs (JSONL formatting,
file upload, job submission, status polling, and response parsing).
"""
import io
import json
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional
from mistralai.client import Mistral
from config import settings

logger = logging.getLogger(__name__)


class MistralBatchHelper:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.MISTRAL_API_KEY
        self.client = Mistral(api_key=self.api_key)

    async def upload_batch_jsonl(self, requests_data: List[Dict[str, Any]], filename: str = "batch_input.jsonl") -> str:
        """
        Takes a list of request dicts (each having 'custom_id' and 'body'),
        converts them to a JSONL byte buffer, and uploads it to Mistral with purpose='batch'.
        Returns the uploaded file_id.
        """
        lines = []
        for req in requests_data:
            lines.append(json.dumps(req, ensure_ascii=False))
        jsonl_content = "\n".join(lines).encode("utf-8")

        logger.info(f"Uploading batch JSONL file '{filename}' ({len(requests_data)} items, {len(jsonl_content)} bytes)")
        
        uploaded_file = await self.client.files.upload_async(
            file={
                "file_name": filename,
                "content": jsonl_content,
            },
            purpose="batch"
        )
        logger.info(f"Uploaded batch file successfully with file_id: {uploaded_file.id}")
        return uploaded_file.id

    async def create_batch_job(
        self,
        input_file_id: str,
        endpoint: str,
        model: Optional[str] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Submits a new batch job to Mistral.
        Returns the job_id.
        """
        kwargs = {
            "input_files": [input_file_id],
            "endpoint": endpoint,
        }
        if model:
            kwargs["model"] = model
        if agent_id:
            kwargs["agent_id"] = agent_id
        if metadata:
            kwargs["metadata"] = metadata

        logger.info(f"Creating batch job on endpoint='{endpoint}', model={model}, agent_id={agent_id}")
        job = await self.client.batch.jobs.create_async(**kwargs)
        logger.info(f"Batch job created with ID: {job.id}, status: {job.status}")
        return job.id

    async def poll_batch_job(
        self,
        job_id: str,
        poll_interval: float = 3.0,
        max_wait_seconds: float = 600.0
    ) -> Any:
        """
        Polls the batch job until it reaches a terminal status (SUCCESS, FAILED, TIMEOUT_EXCEEDED, CANCELLED).
        Returns the finished BatchJob object.
        """
        elapsed = 0.0
        while elapsed < max_wait_seconds:
            job = await self.client.batch.jobs.get_async(job_id=job_id)
            status = job.status
            total = job.total_requests or 0
            completed = job.completed_requests or 0
            succeeded = job.succeeded_requests or 0
            failed = job.failed_requests or 0

            logger.info(
                f"[Batch {job_id}] Status: {status} | Progress: {completed}/{total} "
                f"(Success: {succeeded}, Failed: {failed}) | Elapsed: {elapsed:.1f}s"
            )

            if status == "SUCCESS":
                return job
            elif status in ("FAILED", "TIMEOUT_EXCEEDED", "CANCELLED"):
                error_msg = f"Batch job {job_id} terminated with status: {status}. Errors: {job.errors}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Batch job {job_id} timed out after {max_wait_seconds}s")

    async def download_batch_results(self, output_file_id: str) -> Dict[str, Any]:
        """
        Downloads and parses the output JSONL file from Mistral.
        Returns a dict mapping custom_id -> parsed response body (or error).
        """
        logger.info(f"Downloading batch results from file_id: {output_file_id}")
        response = await self.client.files.download_async(file_id=output_file_id)
        
        if hasattr(response, "aread"):
            raw_bytes = await response.aread()
            content_text = raw_bytes.decode("utf-8")
        elif hasattr(response, "read"):
            raw_bytes = response.read()
            content_text = raw_bytes.decode("utf-8") if isinstance(raw_bytes, bytes) else str(raw_bytes)
        elif hasattr(response, "text") and isinstance(response.text, str):
            content_text = response.text
        elif isinstance(response, bytes):
            content_text = response.decode("utf-8")
        else:
            content_text = str(response)

        results = {}
        for line in content_text.strip().split("\n"):
            if not line.strip():
                continue
            item = json.loads(line)
            custom_id = item.get("custom_id")
            res_obj = item.get("response", {})
            status_code = res_obj.get("status_code", 200)
            body = res_obj.get("body", {})
            error = item.get("error")

            results[custom_id] = {
                "status_code": status_code,
                "body": body,
                "error": error
            }

        logger.info(f"Successfully parsed {len(results)} output items from file_id {output_file_id}")
        return results

    async def run_batch_pipeline(
        self,
        requests_data: List[Dict[str, Any]],
        endpoint: str,
        model: Optional[str] = None,
        agent_id: Optional[str] = None,
        filename: str = "batch_input.jsonl",
        metadata: Optional[Dict[str, str]] = None,
        poll_interval: float = 3.0,
        max_wait_seconds: float = 600.0
    ) -> Dict[str, Any]:
        """
        Convenience end-to-end runner:
        1. Uploads requests_data as JSONL.
        2. Creates the batch job.
        3. Polls until completion.
        4. Downloads and returns the parsed results keyed by custom_id.
        """
        if not model and requests_data:
            model = requests_data[0].get("body", {}).get("model")

        start_total = time.perf_counter()
        
        # 1. Upload
        start_upload = time.perf_counter()
        file_id = await self.upload_batch_jsonl(requests_data, filename=filename)
        upload_duration = time.perf_counter() - start_upload

        # 2. Create and Poll Batch Job
        start_job = time.perf_counter()
        job_id = await self.create_batch_job(
            input_file_id=file_id,
            endpoint=endpoint,
            model=model,
            agent_id=agent_id,
            metadata=metadata
        )
        job = await self.poll_batch_job(job_id, poll_interval=poll_interval, max_wait_seconds=max_wait_seconds)
        job_duration = time.perf_counter() - start_job
        
        if not job.output_file:
            raise RuntimeError(f"Batch job {job_id} succeeded but has no output_file ID.")

        # 3. Download Results
        start_dl = time.perf_counter()
        results = await self.download_batch_results(job.output_file)
        dl_duration = time.perf_counter() - start_dl

        total_duration = time.perf_counter() - start_total
        logger.info(
            f"⏱️ [BATCH_TIMING] Endpoint '{endpoint}' ({len(requests_data)} items): "
            f"Total: {total_duration:.2f}s | Upload: {upload_duration:.2f}s | "
            f"Mistral Queue/Inference: {job_duration:.2f}s | Download: {dl_duration:.2f}s"
        )

        return results
