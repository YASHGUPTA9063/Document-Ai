import functools
import time
import logging
import asyncio

# Setup performance logger
logger = logging.getLogger("perf_logger")
logger.setLevel(logging.INFO)
logger.propagate = False  # Prevent performance logs from going to stdout/stderr (terminal)

# Configure file logging handler
log_file = "performance.log"
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
