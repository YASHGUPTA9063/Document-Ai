# Generic Cross-Validation System

Currently, the cross-validation feature is hardcoded to compare **PAN ↔ Aadhaar** only. This plan makes it **flexible** — users pick any two document types to compare (Name + DOB), with the PAN ↔ Aadhaar comparison kept as the default.

## Proposed Changes

### Backend

#### [MODIFY] [documents.py](file:///c:/Users/MrYashGupta/Desktop/Document-AI/backend-v2/api/routers/v1/documents.py)

1. **New endpoint** `GET /cross-validate/compare?doc_type_a=<type>&doc_type_b=<type>`
   - Takes two query parameters: the doc_type strings to compare
   - Fetches the latest completed document of each type (same pattern as existing)
   - Extracts `full_name` / `name` and `date_of_birth` using flexible field lookup
   - Uses existing `_fuzzy_name()` and `_exact_dob()` helpers
   - Returns a **generic** response shape with `doc_a` / `doc_b` keys instead of `pan` / `aadhaar`

2. **New endpoint** `GET /cross-validate/doc-types`
   - Returns the list of distinct `doc_type` values that have at least one completed document
   - This powers the dropdown selectors on the frontend

3. **Keep existing** `GET /cross-validate/latest` endpoint unchanged for backward compatibility

---

### Frontend

#### [MODIFY] [client.js](file:///c:/Users/MrYashGupta/Desktop/Document-AI/frontend-v2/src/api/client.js)

- Add `crossValidateCompare(docTypeA, docTypeB)` → calls `GET /cross-validate/compare?doc_type_a=...&doc_type_b=...`
- Add `getCrossValidateDocTypes()` → calls `GET /cross-validate/doc-types`

#### [MODIFY] [Validation.jsx](file:///c:/Users/MrYashGupta/Desktop/Document-AI/frontend-v2/src/pages/Validation.jsx)

Redesign the `CrossValidation` component:

1. **Two dropdown selectors** at the top — one for "Document A" and one for "Document B"
   - Populated from the `/cross-validate/doc-types` endpoint
   - Default to `pan_card` and `aadhar_card` if they exist
   - Labels are prettified (e.g., `aadhar_card` → "Aadhaar Card", `driving_license` → "Driving License")
2. **Compare button** triggers the comparison
3. **Results table** is now generic — column headers show the selected doc type names dynamically
4. The `FieldRow` component is updated to accept generic labels (`docAVal` / `docBVal` instead of `panVal` / `aadhaarVal`)
5. Overall PASS/FAIL/INCOMPLETE badge works the same way

## Open Questions

> [!IMPORTANT]
> Currently your DB has no `driving_license` or `passport` documents. When those documents are uploaded, what `doc_type` value will the classifier assign to them? The system will work with whatever string gets stored — the dropdowns are populated dynamically from the DB. But if driving license documents get classified as `id_proof` or `others`, the cross-validation won't know they're driving licenses.

## Verification Plan

### Manual Verification
- Start the dev server, navigate to the Validation page
- Confirm the two dropdowns appear and are populated with available doc types
- Select `pan_card` and `aadhar_card`, verify the existing comparison still works
- Try selecting other doc type combinations
- Test the INCOMPLETE state when one of the selected types has no completed documents
