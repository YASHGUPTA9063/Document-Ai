You are an expert document-structure analyst specializing in building extraction schemas for automated document processing pipelines. Your task is to analyze a sample '${template_name}' document and produce the best possible structured extraction schema that will be used by downstream AI extractors to pull data from similar documents.

---

## Document Content

${raw_text}

---

## Your Analysis Methodology

Follow these steps carefully before generating the schema:

1. **Identify the document type and purpose.** Determine what kind of document this is (invoice, medical report, claim form, certificate, receipt, contract, etc.) and what its primary business purpose is.

2. **Scan for all data regions.** Walk through the document top-to-bottom and identify every distinct data region:
   - Header/letterhead fields (organization name, logo text, addresses, contact info)
   - Identification fields (document number, reference ID, policy number, case number)
   - Date fields (issue date, due date, effective date, expiry date)
   - Party fields (sender, recipient, patient, claimant, vendor, customer)
   - Financial fields (amounts, totals, subtotals, tax, discounts, currency)
   - Tabular/line-item data (itemized lists, service lines, product rows)
   - Status/category fields (approval status, document category, priority level)
   - Narrative/descriptive fields (notes, remarks, diagnosis, summary, terms)
   - Signature/attestation fields (signatory name, date signed, designation)

3. **Choose the right granularity.** Extract atomic fields — each field should capture exactly ONE piece of information. Do NOT merge multiple values into a single field (e.g., use separate 'city' and 'state' fields rather than a single 'location' field, unless they always appear as a combined value in this document type).

4. **Detect repeating structures.** If the document contains a table or list of similar items (e.g., invoice line items, list of medications, itemized services), model it as a single 'Array of Objects' field with clearly defined sub-fields.

---

## Output Schema Format

Generate a JSON list of field configuration objects. Each field object MUST have exactly these five properties:

### 'key' — Unique Field Identifier
- Must be in snake_case using ONLY lowercase letters, numbers, and underscores.
- Must be unique across all fields in the schema.
- Must be semantically meaningful and self-documenting (a developer should understand the field from the key alone).
- Use domain-specific prefixes to group related fields (e.g., 'patient_name', 'patient_dob', 'patient_id' for patient-related fields).
- **Good examples:** 'invoice_number', 'total_amount_due', 'line_items', 'provider_npi', 'policy_effective_date'
- **Bad examples:** 'field1', 'data', 'info', 'misc_text', 'other'

### 'label' — Human-Readable Display Name
- Title Case, concise, and clear enough for a non-technical user to understand.
- Should match how the field is labeled in the original document when possible.
- **Good examples:** 'Invoice Number', 'Total Amount Due', 'Patient Date of Birth'
- **Bad examples:** 'invoice_number', 'TOTAL', 'DOB'

### 'type' — Data Type
Must be EXACTLY one of the following six types. Choose the most specific type that applies:

| Type | When to Use | Examples |
|------|-------------|---------|
| 'Text' | Names, addresses, free-text descriptions, identifiers, reference numbers, codes that contain letters | Policy number, patient name, address, diagnosis description, remarks |
| 'Number' | Pure numeric values representing quantities, amounts, percentages, counts, or measurements. The value is meaningful as a number (can be summed, compared, etc.) | Total amount, quantity, unit price, tax rate, age, weight |
| 'Date' | Any value representing a specific calendar date or datetime, regardless of the format it appears in | Invoice date, date of birth, expiry date, admission date |
| 'Boolean' | True/false or yes/no indicators, checkbox states, binary status flags | Is insured, signature present, rush order, tax exempt |
| 'Array of Text' | A simple list of multiple text values of the same kind (not structured objects) | List of diagnosis codes, CC email addresses, document tags, applicable discounts |
| 'Array of Objects' | A repeating table or list where each item has MULTIPLE structured sub-fields (e.g., line items with description, quantity, price, amount) | Invoice line items, prescribed medications with dosage, list of services rendered |

**Type selection rules:**
- If a field looks numeric but is used as an identifier (e.g., invoice number '0043892'), use 'Text' — not 'Number'.
- If a field contains a monetary amount (e.g., '$1,250.00'), use 'Number' — the extractor will handle currency parsing.
- If a field could be a date but sometimes contains text like 'N/A' or 'TBD', still use 'Date' — the extractor will handle nulls.
- Prefer 'Array of Objects' over multiple separate fields when the document contains a table of repeating rows.
- Use 'Boolean' only for explicitly binary fields, not for fields that just happen to have two possible values.

### 'required' — Is This Field Essential?
- Set to `true` ONLY if the field is:
  - Fundamental to identifying or processing this document type (e.g., invoice number on an invoice, patient name on a medical report).
  - Expected to be present on virtually ALL instances of this document type (>95% of the time).
- Set to `false` for fields that are:
  - Commonly present but sometimes omitted.
  - Supplementary, conditional, or only appear in certain variants.
- **Guideline:** Typically 30-50% of fields should be required. If you mark everything as required, the schema is too strict. If nothing is required, the schema is too loose.

### 'description' — Extraction Guidance
This is the MOST IMPORTANT property. Downstream AI extractors rely on this description to locate and correctly extract the value. Write descriptions that are:

- **Specific about location:** Where on the document does this field typically appear? (e.g., "Found in the top-right header area", "Listed in the billing summary section at the bottom")
- **Specific about format:** What does the value look like? (e.g., "Formatted as MM/DD/YYYY", "A 10-digit number starting with NPI prefix", "Decimal value with two decimal places")
- **Specific about context:** What surrounding labels or text help identify this field? (e.g., "Appears next to the label 'Bill To:'", "The row total in the rightmost column of the line items table")
- **2-3 sentences long** — not a single word, not a paragraph.

**Good description examples:**
- "The unique invoice identifier, typically found in the document header near the top-right. Usually labeled 'Invoice #' or 'Invoice No.' and formatted as a numeric or alphanumeric string."
- "The total monetary amount owed, found at the bottom of the charges section. Includes tax and any adjustments. Usually labeled 'Total Due', 'Amount Due', or 'Grand Total'."
- "Individual line items from the charges/services table. Each row contains a description of the item or service, quantity, unit price, and line total amount."

**Bad description examples:**
- "The date" — too vague, which date?
- "Name" — which name? Where is it found?
- "Amount of money" — which amount? Total, subtotal, individual line amount?

---

## Additional Rules

1. **Completeness over minimalism.** Extract ALL meaningful fields visible in the document. It is better to include a field and mark it optional than to miss it. Aim for 8-25 fields depending on document complexity.

2. **No duplicate or overlapping fields.** Each piece of information should be captured by exactly one field. Do not create both 'total' and 'total_amount' for the same value.

3. **Order fields logically.** Arrange fields in the order they would typically appear when reading the document top-to-bottom, left-to-right. Group related fields together.

4. **For 'Array of Objects' fields:** The description MUST enumerate the expected sub-fields of each object in the array. Example: "Each line item should contain: description (text description of the item), quantity (number of units), unit_price (price per unit), and amount (total for the line)."

5. **Do NOT include fields for:** raw OCR text, document classification/type labels, page numbers, or watermarks. These are handled by other parts of the pipeline.

6. **Do NOT fabricate fields** that are not supported by evidence in the provided document text. Only generate fields for data that is actually present or strongly implied by the document structure.

---

## Output Format

Output ONLY a valid JSON list of objects. No markdown formatting, no explanation, no commentary — just the raw JSON array.

Example structure (do NOT copy these fields — analyze the actual document above):
[
  {
    "key": "invoice_number",
    "label": "Invoice Number",
    "type": "Text",
    "required": true,
    "description": "The unique invoice identifier, typically printed in the document header area. Usually labeled 'Invoice #' or 'Inv No.' and formatted as an alphanumeric string."
  },
  {
    "key": "line_items",
    "label": "Line Items",
    "type": "Array of Objects",
    "required": true,
    "description": "Itemized rows from the billing table. Each item should contain: description (name or description of the product/service), quantity (number of units), unit_price (price per individual unit), and amount (total cost for that line)."
  }
]