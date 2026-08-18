Extract key fields from the document following this schema:
${fields_instruction}

Rules:
- Return the exact text as written in the document without normalization or cleaning.
- For every field, return a value even if not found — use empty string for required fields, null for optional fields.
- Never omit a field from the output.