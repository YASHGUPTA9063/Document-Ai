# ─── TOOL SCHEMAS ───
REVIEWER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_review_context",
            "description": "Fetches the current confidence score and clean validated data payload for human-in-the-loop review evaluation.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# ─── TOOL FUNCTIONS ───
def get_review_context(confidence_score: float, validated_data: dict) -> dict:
    return {
        "confidence_score": confidence_score,
        "validated_data": validated_data
    }
