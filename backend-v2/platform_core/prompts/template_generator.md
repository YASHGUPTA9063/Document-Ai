You are a document extraction expert. Analyze the following document text extracted from a sample '${template_name}' document. Identify the key structured fields that would be useful to extract from this type of document (e.g. names, dates, amounts, item tables, identifiers).

Document Content:
${raw_text}

Generate a document extraction schema as a JSON list of field configurations. Each field in the list must be an object with the following fields:
- 'key': Unique field identifier in snake_case (e.g., 'invoice_date', 'total_amount'). Must only contain lowercase letters, numbers, and underscores.
- 'label': Human-readable label (e.g., 'Invoice Date', 'Total Amount').
- 'type': Data type. Must be exactly one of: 'Text', 'Number', 'Date', 'Boolean', 'Array of Text', 'Array of Objects'.
- 'required': Boolean indicating whether this field is essential and always expected in similar documents.
- 'description': Short description explaining what this field is and how it should be identified.

Output a valid JSON list of objects. Do not include any explanation or markdown formatting, just the raw JSON list.