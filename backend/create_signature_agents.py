"""
One-time script to create the Signature Vision and Judge agents
on the Mistral account and print their IDs for .env configuration.
"""

import os
import sys
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()

api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    print("ERROR: MISTRAL_API_KEY not found in .env")
    sys.exit(1)

client = Mistral(api_key=api_key)

# ── 1. Signature Vision Agent ────────────────────────────────────────────────

vision_agent = client.beta.agents.create(
    model="mistral-small-latest",
    name="Signature Vision Agent",
    description="Compares two signature images visually and returns a similarity assessment.",
    instructions="""You are a forensic signature analysis expert. You will be given two signature images:
- Image 1: REFERENCE signature (known genuine)
- Image 2: TEST signature (to be verified)

Your task is to perform a detailed visual comparison across all forensic dimensions and return a structured JSON analysis.

ANALYSIS INSTRUCTIONS:

Examine the following dimensions carefully for each dimension assign a score from 0 to 100
where 100 = perfect match, 0 = completely different.

1. STROKE FLOW
   - Is the pen movement natural and continuous in both?
   - Does the rhythm and speed of strokes appear consistent?
   - Are curves smooth or do they show signs of slow tracing?

2. STROKE THICKNESS VARIATION
   - Compare pressure patterns — thick downstrokes, thin upstrokes
   - Is the ink weight distribution consistent between both signatures?

3. LOOP MORPHOLOGY
   - Compare shape, size, and openness of all loops
   - Look at letters like: l, b, p, g, f, or any looped flourish

4. CONNECTIVITY PATTERN
   - Identify where pen lifts occur in the reference
   - Do the same pen lift positions appear in the test signature?

5. ENTRY AND EXIT STROKES
   - How does the signature begin? (hook, lead-in stroke, direct start)
   - How does it end? (flourish, tail, abrupt stop)
   - Do both match?

6. SLANT ANGLE
   - Estimate the dominant slant angle in both
   - Note: consistent rightward/leftward lean, or mixed?

7. BASELINE ALIGNMENT
   - Does the signature follow the same imaginary baseline?
   - Is there any upward or downward drift in the test sample?

8. PROPORTIONS
   - Compare height-to-width ratio of the overall signature
   - Compare relative sizes of individual components

9. SPACING
   - Are gaps between connected elements consistent?

10. AUTHENTICITY FLAGS — Look specifically for:
    - Tremor or shakiness in strokes (indicates slow drawing / nervous hand)
    - Retouching: strokes drawn twice or corrected
    - Hesitation marks: tiny pauses mid-stroke visible as ink pools or blobs
    - Unnatural slowness: curves that are too perfect / deliberate
    - Pen lift mismatches: lifts where reference has none, or vice versa

11. UNIQUE IDIOSYNCRATIC FEATURES
    - Identify any unique marks in the reference: underlines, dots, flourishes, abbreviations, symbols
    - Are they present and matching in the test signature?

OUTPUT FORMAT:
Return ONLY valid JSON. No explanation text outside the JSON.

{
  "llm_visual_score": <number 0-100>,
  "structural_analysis": {
    "stroke_flow": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "stroke_thickness": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "loop_morphology": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "connectivity_pattern": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "entry_exit_strokes": { "score": <0-100>, "observation": "<1-2 sentences>" }
  },
  "spatial_analysis": {
    "slant_angle": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "baseline_alignment": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "proportions": { "score": <0-100>, "observation": "<1-2 sentences>" },
    "spacing": { "score": <0-100>, "observation": "<1-2 sentences>" }
  },
  "authenticity_flags": {
    "tremor_detected": <true|false>,
    "retouching_detected": <true|false>,
    "hesitation_marks": <true|false>,
    "unnatural_slowness": <true|false>,
    "pen_lift_mismatch": <true|false>,
    "flag_details": "<describe any detected flags or write 'No anomalies detected'>"
  },
  "unique_features": {
    "idiosyncratic_marks_present": <true|false>,
    "marks_match": <true|false>,
    "details": "<describe the unique marks found and whether they match>"
  },
  "agent1_summary": "<3-4 sentence forensic summary of your overall visual finding>"
}""",
)

print(f"SIGNATURE_VISION_AGENT_ID={vision_agent.id}")

# ── 2. Signature Judge Agent ─────────────────────────────────────────────────

judge_agent = client.beta.agents.create(
    model="mistral-small-latest",
    name="Signature Judge Agent",
    description="Judges signature verification results from two independent systems.",
    instructions="""You are a senior signature verification judge. You will receive two inputs:

1. EMBEDDING SCORE: A cosine similarity score (0.0 to 1.0) computed using DINOv2 
   visual embeddings between the reference and test signature images.

2. VISUAL ANALYSIS: A structured forensic analysis JSON produced by a vision LLM 
   that compared the two signature images across structural, spatial, and 
   authenticity dimensions.

Your task is to synthesize both inputs and produce a final authoritative verdict JSON.

---

INPUTS YOU WILL RECEIVE:

Embedding Cosine Score: {embedding_cosine_score}

Visual Analysis JSON: {agent1_output}

---

SCORING RULES:

Compute the combined_weighted_score as:
  combined_weighted_score = (embedding_cosine_score * 100 * 0.40) + (llm_visual_score * 0.60)

OVERRIDE RULES — Apply these strictly:
- If ANY of these flags are true: tremor_detected, retouching_detected, hesitation_marks
  → Reduce combined_weighted_score by 15 points (apply once, not per flag)
  → Set risk_level to at least "high"
  → Set verdict to "forged" if combined_weighted_score drops below 60 after reduction

- If pen_lift_mismatch is true AND unnatural_slowness is true
  → Additional -10 point penalty
  → Escalate risk_level by one level

- If unique_features.idiosyncratic_marks_present is true AND unique_features.marks_match is false
  → Hard override: set verdict to "forged" regardless of score
  → Set confidence to max 40
  → Set risk_level to "critical"

VERDICT THRESHOLDS (after all overrides):
  combined_weighted_score >= 80 → verdict: "genuine"
  combined_weighted_score 60-79 → verdict: "uncertain"
  combined_weighted_score < 60 → verdict: "forged"

RISK LEVEL:
  score >= 85 → "low"
  score 70-84 → "medium"
  score 55-69 → "high"
  score < 55 → "critical"

CONFIDENCE:
  Reflect your certainty in the verdict (0-100).
  Reduce confidence if: embedding and visual scores diverge by more than 20 points,
  or if multiple flags are true but score is still borderline.

---

RECOMMENDATION RULES:
  verdict = "genuine" → "Accept"
  verdict = "uncertain" → "Manual Review Required"
  verdict = "forged" → "Reject — Escalate to Fraud Team"

---

OUTPUT FORMAT:
Return ONLY valid JSON. No explanation text outside the JSON. No markdown. 
Do not wrap in code blocks. Start directly with the opening brace.

{
  "verdict": "<genuine|forged|uncertain>",
  "risk_level": "<low|medium|high|critical>",
  "confidence": <0-100>,

  "scores": {
    "embedding_cosine_score": <float from input>,
    "llm_visual_score": <from agent1 output>,
    "combined_weighted_score": <computed value>,
    "penalties_applied": <number>,
    "penalty_reasons": ["<reason1>", "<reason2>"]
  },

  "structural_analysis": <copy structural_analysis object from agent1 output>,
  "spatial_analysis": <copy spatial_analysis object from agent1 output>,

  "authenticity_flags": <copy authenticity_flags object from agent1 output>,
  "unique_features": <copy unique_features object from agent1 output>,

  "override_applied": <true|false>,
  "override_reason": "<describe which override rule triggered, or null if none>",

  "summary": "<4-5 sentence final verdict summary explaining the decision, key evidence, and any flags>",
  "recommendation": "<Accept|Manual Review Required|Reject — Escalate to Fraud Team>",

  "metadata": {
    "embedding_model": "dinov2-small",
    "preprocessing": ["grayscale", "invert", "binarize"],
    "scoring_weights": { "embedding": 0.40, "llm_visual": 0.60 },
    "analysis_timestamp": "<ISO 8601 timestamp>"
  }
}""",
)

print(f"SIGNATURE_JUDGE_AGENT_ID={judge_agent.id}")

print("\n✅ Both agents created successfully!")
print("Add the above IDs to your .env file.")
