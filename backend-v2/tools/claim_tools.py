"""
claim_tools.py
──────────────
The 3 shared fetch tools used by all 5 claim processing agents.
Each tool is a pure data fetcher — the LLM does all reasoning.

Tool schemas are passed to client.agents.complete(tools=CLAIM_TOOLS).
The actual implementations call claim_operations async functions via asyncio.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


# ─── TOOL SCHEMAS (passed to Mistral agent calls) ─────────────────────────────

CLAIM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_claim_documents_data",
            "description": (
                "Fetches the OCR-extracted field-value pairs for specified document types "
                "belonging to a claim. Returns structured JSON per document type. "
                "Use this to read the actual claim documents (form fields, medical data, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {
                        "type": "string",
                        "description": "The unique claim identifier (e.g. CLM-001)."
                    },
                    "doc_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of document types to fetch. Valid values include: "
                            "claim_form, policy_document, id_proof, medical_report, "
                            "lab_reports, prescription_records, bills_invoices, "
                            "disability_certificate, legal_letter."
                        )
                    }
                },
                "required": ["claim_id", "doc_types"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_claimant_history",
            "description": (
                "Fetches the prior claims history for a claimant from the database. "
                "Returns total prior claims count, how many were submitted in the last 12 months, "
                "and a list of individual prior claim records with dates and statuses. "
                "Use this to check for duplicate claims or suspicious claim frequency."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claimant_id": {
                        "type": "string",
                        "description": "The unique claimant identifier (e.g. CLT-001)."
                    }
                },
                "required": ["claimant_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy_details",
            "description": (
                "Fetches the insurance policy coverage details for a given policy ID. "
                "Returns start date, end date, coverage type, and holder name. "
                "Use this to verify whether the policy was active on the incident date "
                "and what coverage it provides."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_id": {
                        "type": "string",
                        "description": "The unique policy identifier (e.g. POL-123)."
                    }
                },
                "required": ["policy_id"]
            }
        }
    }
]


# ─── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────────

async def get_claim_documents_data(claim_id: str, doc_types: list) -> dict:
    from db.claim_operations import get_claim_documents_data as _async_fn
    try:
        return await _async_fn(claim_id, doc_types)
    except Exception as e:
        logger.error(f"[Tool] get_claim_documents_data failed for claim {claim_id}: {e}")
        return {"error": str(e)}


async def get_claimant_history(claimant_id: str) -> dict:
    from db.claim_operations import get_claimant_history as _async_fn
    try:
        return await _async_fn(claimant_id)
    except Exception as e:
        logger.error(f"[Tool] get_claimant_history failed for claimant {claimant_id}: {e}")
        return {"error": str(e)}


async def get_policy_details(policy_id: str) -> dict:
    from db.claim_operations import get_policy_details as _async_fn
    try:
        return await _async_fn(policy_id)
    except Exception as e:
        logger.error(f"[Tool] get_policy_details failed for policy {policy_id}: {e}")
        return {"error": str(e)}


# ─── DISPATCH HELPER ──────────────────────────────────────────────────────────

async def dispatch_claim_tool(tool_name: str, args: dict) -> dict:
    """
    Central dispatcher called from agent activity tool-call loops.
    Maps tool name strings to their implementations.

    Args:
        tool_name: The function name from the tool_call (e.g. 'get_claim_documents_data')
        args: Parsed dict of arguments from tool_call.function.arguments

    Returns:
        dict result from the tool function, ready to be JSON-serialized as a tool message.
    """
    if tool_name == "get_claim_documents_data":
        return await get_claim_documents_data(
            claim_id=args["claim_id"],
            doc_types=args["doc_types"]
        )
    elif tool_name == "get_claimant_history":
        return await get_claimant_history(claimant_id=args["claimant_id"])
    elif tool_name == "get_policy_details":
        return await get_policy_details(policy_id=args["policy_id"])
    else:
        logger.error(f"[Tool Dispatcher] Unknown tool name: {tool_name}")
        return {"error": f"Unknown tool: {tool_name}"}
