import functools
import time
import logging
import asyncio

# Setup performance logger
logger = logging.getLogger("perf_logger")
logger.setLevel(logging.INFO)
logger.propagate = False  # Prevent performance logs from going to stdout/stderr (terminal)

# Configure file logging handler — write to STORAGE_DIR (writable in Docker)
# or fall back to /tmp if the default path is not writable.
import os
_storage = os.environ.get("STORAGE_DIR", ".")
log_file = os.path.join(_storage, "performance.log")
try:
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
except PermissionError:
    log_file = os.path.join("/tmp", "performance.log")
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def wrap_timing(func, category: str, name: str):
    """Wraps a function to measure and log its execution time."""
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            logger.info(f"[PERF] [{category.upper()}_START] {name} started")
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                logger.info(f"[PERF] [{category.upper()}_END] {name} took {duration:.3f}s")
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            logger.info(f"[PERF] [{category.upper()}_START] {name} started")
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                logger.info(f"[PERF] [{category.upper()}_END] {name} took {duration:.3f}s")
        return sync_wrapper

def install_performance_hooks():
    logger.info("Initializing performance timing hooks...")

    # 1. Wrap Mistral Agents Complete methods
    try:
        from mistralai.client.agents import Agents
        original_complete = Agents.complete

        def timed_complete(self, *args, **kwargs):
            agent_id = kwargs.get("agent_id") or (args[0] if len(args) > 0 else "unknown")
            start = time.perf_counter()
            logger.info(f"[PERF] [AGENT_START] Agent completion for agent_id='{agent_id}' started")
            try:
                return original_complete(self, *args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                logger.info(f"[PERF] [AGENT_END] Agent completion for agent_id='{agent_id}' took {duration:.3f}s")

        Agents.complete = timed_complete

        original_complete_async = Agents.complete_async

        async def timed_complete_async(self, *args, **kwargs):
            agent_id = kwargs.get("agent_id") or (args[0] if len(args) > 0 else "unknown")
            start = time.perf_counter()
            logger.info(f"[PERF] [AGENT_START] Agent async completion for agent_id='{agent_id}' started")
            try:
                return await original_complete_async(self, *args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                logger.info(f"[PERF] [AGENT_END] Agent async completion for agent_id='{agent_id}' took {duration:.3f}s")

        Agents.complete_async = timed_complete_async
        logger.info("Successfully patched Mistral Agents API client methods")
    except Exception as e:
        logger.warning(f"Could not patch Mistral Agents client: {e}")

    # 2. Wrap Workflows activity decorator
    try:
        import mistralai.workflows as workflows
        original_activity_decorator = workflows.activity

        def timing_activity_decorator(*args, **kwargs):
            def decorator(func):
                wrapped = wrap_timing(func, "activity", func.__name__)
                return original_activity_decorator(*args, **kwargs)(wrapped)

            if len(args) == 1 and callable(args[0]):
                func = args[0]
                args = ()
                return decorator(func)
            return decorator

        workflows.activity = timing_activity_decorator
        logger.info("Successfully patched mistralai.workflows activity decorator")
    except Exception as e:
        logger.warning(f"Could not patch mistralai.workflows activity decorator: {e}")

    # 3. Wrap Document validation tools
    try:
        import tools.preprocessor as tp
        tp.enhance_document_image = wrap_timing(tp.enhance_document_image, "tool", "enhance_document_image")

        import tools.output as to
        to.persist_final_extraction = wrap_timing(to.persist_final_extraction, "tool", "persist_final_extraction")

        import tools.intake as ti
        ti.check_document_duplicates = wrap_timing(ti.check_document_duplicates, "tool", "check_document_duplicates")

        import tools.fraud_checker as tfc
        tfc.run_identity_proofing = wrap_timing(tfc.run_identity_proofing, "tool", "run_identity_proofing")

        import tools.auto_verifier as tav
        tav.find_customer_reference = wrap_timing(tav.find_customer_reference, "tool", "find_customer_reference")
        tav.verify_signature = wrap_timing(tav.verify_signature, "tool", "verify_signature")
        tav.verify_face = wrap_timing(tav.verify_face, "tool", "verify_face")

        import tools.extractor as te
        te.extract_text_from_document = wrap_timing(te.extract_text_from_document, "tool", "extract_text_from_document")

        logger.info("Successfully patched document workflow tool functions")
    except Exception as e:
        logger.warning(f"Could not patch document workflow tool functions: {e}")

    # 4. Wrap Claim validation tools
    try:
        import tools.claim_tools as ct
        ct.dispatch_claim_tool = wrap_timing(ct.dispatch_claim_tool, "tool", "dispatch_claim_tool")
        logger.info("Successfully patched claim workflow tool functions")
    except Exception as e:
        logger.warning(f"Could not patch claim workflow tool functions: {e}")
