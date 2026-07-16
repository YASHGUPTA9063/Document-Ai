"""
claim_disability.py
───────────────────
Activity for Agent 4 — Disability Agent.

Checks:
  - Disability certificate present (from licensed physician)
  - Severity level stated in certificate
  - Claimed limitations are consistent with the medical diagnosis

Tools called:
  get_claim_documents_data(claim_id, ["disability_certificate", "medical_report"])
"""
import json
import logging
import mistralai.workflows as workflows
from mistralai.client import Mistral
from config import settings
from tools.claim_tools import CLAIM_TOOLS, dispatch_claim_tool

logger = logging.getLogger(__name__)
client = Mistral(api_key=settings.MISTRAL_API_KEY)


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif hasattr(chunk, "text") and chunk.text:
                parts.append(chunk.text)
            elif isinstance(chunk, dict) and "text" in chunk:
                parts.append(chunk["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


@workflows.activity()
async def claim_disability_activity(claim_id: str) -> dict:
    """
    Runs the Disability Agent.
    Returns a structured dict with check results and overall status.
    """
    try:
        logger.info(f"[Claim {claim_id}] Starting Disability Agent activity.")

        if not settings.CLAIM_DISABILITY_AGENT_ID:
            raise ValueError("CLAIM_DISABILITY_AGENT_ID is not configured in settings/environment.")

        prompt = (
            f"You are running disability validation checks on claim_id='{claim_id}'.\n"
            f"Use your tools to fetch the required documents, then perform all checks as per your instructions.\n"
            f"Return ONLY the JSON result object."
        )

        messages = [{"role": "user", "content": prompt}]

        logger.info(f"[Claim {claim_id}] Calling Disability Agent ({settings.CLAIM_DISABILITY_AGENT_ID})")
        response = await client.agents.complete_async(
            agent_id=settings.CLAIM_DISABILITY_AGENT_ID,
            messages=messages,
            tools=CLAIM_TOOLS
        )
        message = response.choices[0].message

        # ── Tool-call loop ──────────────────────────────────────────────────
        while message.tool_calls:
            logger.info(f"[Claim {claim_id}] Disability Agent requested tool calls: {[tc.function.name for tc in message.tool_calls]}")

            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in message.tool_calls
                ]
            }
            messages.append(assistant_msg)

            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = await dispatch_claim_tool(tool_call.function.name, args)
                logger.info(f"[Claim {claim_id}] Executed tool '{tool_call.function.name}'")
                messages.append({
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                })

            response = await client.agents.complete_async(
                agent_id=settings.CLAIM_DISABILITY_AGENT_ID,
                messages=messages,
                tools=CLAIM_TOOLS
            )
            message = response.choices[0].message

        # ── Parse final JSON response ────────────────────────────────────────
        content = _extract_text(message.content).strip()
        try:
            parsed = json.loads(content)
        except Exception:
            logger.info(f"[Claim {claim_id}] Disability Agent response not JSON — requesting structured output.")
            messages.append({
                "role": "user",
                "content": "Please output only the JSON result object with no extra text."
            })
            response = await client.agents.complete_async(
                agent_id=settings.CLAIM_DISABILITY_AGENT_ID,
                messages=messages,
                response_format={"type": "json_object"}
            )
            parsed = json.loads(_extract_text(response.choices[0].message.content).strip())

        logger.info(f"[Claim {claim_id}] Disability Agent completed. Status: {parsed.get('status')}")
        return parsed

    except Exception as e:
        logger.error(f"[Claim {claim_id}] Disability activity failed: {e}")
        return {
            "agent": "Disability Agent",
            "status": "ERROR",
            "checks": [],
            "overall_reason": f"Agent activity failed with error: {str(e)}"
        }
