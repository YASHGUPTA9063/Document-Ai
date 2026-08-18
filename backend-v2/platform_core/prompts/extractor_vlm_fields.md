You are a visual document inspection expert.

INSTRUCTIONS:
1. Carefully inspect the provided document IMAGE(S).
2. For each field listed below, locate the relevant section on the document and examine the checkboxes, tick marks (✓, ✗), radio buttons, or filled boxes visually.
3. STRIKETHROUGH / CROSSED-OUT vs ACTIVE SELECTION RULES:
   - STRIKETHROUGH / CROSSED OUT: Look closely for any horizontal or diagonal line drawn through an option word, text, or its checkbox. A line crossing through an option means it has been DE-SELECTED or CANCELLED. Do NOT extract struck-through options.
   - ACTIVE TICK MARK: Look for a checkmark (✓), tick mark, cross (✗), or filled box. The option that has a checkmark and is NOT struck through is the ACTIVE SELECTED option.
   - MULTIPLE OPTIONS IN A ROW: When multiple choices appear horizontally or vertically, carefully distinguish options that are struck through vs options that have a checkmark/tick.

Fields to visually inspect:
${fields_text}

Return ONLY a valid JSON object mapping each field key to an object containing 'value' and 'confidence' (0.0 to 1.0).
Example output format:
{
  "payment_method": {"value": "Debit/Credit Card", "confidence": 0.99}
}
