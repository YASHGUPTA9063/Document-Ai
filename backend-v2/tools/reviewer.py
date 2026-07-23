# ─── TOOL SCHEMAS ───
REVIEWER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_review_context",
            "description": "Fetches the current confidence score and clean validated data payload for human-in-the-loop review evaluation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The document ID to fetch review context for."
                    }
                },
                "required": ["document_id"]
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
def get_review_context(confidence_score: float, validated_data: dict) -> dict:
    """
    Returns the review context. The caller (reviewer_activity) is responsible
    for supplying the correct confidence_score and validated_data from the
    pipeline context.
    """
    return {
        "confidence_score": confidence_score,
        "validated_data": validated_data
    }
