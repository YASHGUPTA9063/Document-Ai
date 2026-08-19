# Implementation Plan — Multi-Document Packet Splitting

Split a single uploaded file that contains 2–N stitched-together documents into
per-document PDFs, then run the **existing** document pipeline independently on each
piece.

> **Status: implemented.** Everything below is built and merged on `yash-new`, behind
> `ENABLE_DOC_SPLITTING=false`. What is left before switching it on: create the splitter
> agent (`python create_or_update_agents.py`), set `SPLITTER_AGENT_ID`, and run the
> end-to-end check in §6. See §8 for what changed against the original plan.

Reference: the standalone `mistral_doc_splitter.py` PoC. This plan ports its *logic*
(OCR-once → per-page classify → confidence gate → boundary detection → pypdf split),
but replaces its hardcoded `DocType` enum and hardcoded `ID_MARKERS` with the
project's runtime-configurable classification types
(`utils/classification_config.py`) and templates (`utils/templates.py`).

---

## 1. What already exists (and what we reuse)

| Concern | Existing asset | Reuse decision |
|---|---|---|
| Doc-type catalogue | `utils/classification_config.py::load_classification_config()` → `storage/classification_config.json`, seeded from `config.SUPPORTED_DOCUMENT_TYPES`. Normalised to `{snake_key: Display Name}` by `tools/classifier.py::get_supported_doc_types()` | **Reuse as-is.** This is the replacement for the PoC's `DocType` enum. No new type registry. |
| Page-indexed OCR | `utils/ocr.py::extract_with_ocr()` already returns `pages: [{markdown, index}]` and accepts a `pages=[...]` subset | **Reuse.** One OCR pass over the whole packet replaces the PoC's `run_ocr()`. |
| Classification agent call | `activities/classifier.py` (vision-first, single agent call, `json_object` response) | **Keep untouched** — it classifies one already-split document. Splitting needs *per-page* classification, which is a new, separate agent. |
| Agent provisioning | `agents_config.py` + `create_or_update_agents.py` (writes IDs back into `.env`) | **Reuse.** The splitter agent is one more entry in `AGENT_CONFIGS`. |
| Workflow engine | `workflow.py::DocumentProcessingWorkflow` (Mistral Workflows SDK `InteractiveWorkflow`, already uses `wait_for_input` for the duplicate and reviewer pauses) | **Extend.** New step + a new pause type, same pattern. |
| Per-type field schema | `utils/templates.py::load_templates()` → `{key: {fields, is_kyc, use_vlm}}` | **Extend** with an optional `id_marker` regex — the dynamic replacement for the PoC's hardcoded `ID_MARKERS` dict. |
| Resilient Mistral client | `platform_core/adapters/resilient_mistral.py::get_mistral_client()` | **Reuse** — never instantiate a raw SDK client. |

---

## 2. Design decisions

### 2.1 Parent/child model (not in-place replacement)

The uploaded packet stays in the DB as a **parent** `Document` row with terminal
status `split`. Each detected segment becomes a **child** `Document` row with its own
file on disk and its own `document_processing_workflow` execution.

Why not mutate the parent into the first document and spawn the rest? Because
`/documents/{id}/file`, the OCR-block citation highlighting, and the audit trail all
assume `Document.file_path` holds the exact bytes that were classified and extracted.
Keeping the packet immutable preserves that invariant and gives a clean "show me the
original" affordance in the UI.

### 2.2 Where the split runs in the pipeline

Insert as **Step 1.5**, immediately after intake, before pre-validation:

```
1    Intake (duplicate check on the packet)
1.5  SPLIT DETECTION  ← new
       ├─ 1 segment  → fall through, pipeline continues unchanged
       └─ N segments → write children, fan out N workflows, parent returns {"status": "split"}
2    Pre-Validation      ─┐
2.5  Preprocessing        │ each CHILD runs these on its own isolated PDF
3    Classify             │ ← SKIPPED for children: doc_type comes from the split
3.5  Fraud check          │
4–7  Extract → Validate → Review → Output
```

Rationale for placing it *before* pre-validation: `activities/pre_validator.py` judges
blur / skew / orientation / blankness for **one** document. Running it on a 12-page
packet produces a single verdict that can reject a good invoice because page 9 is
skewed. Splitting first means every child gets its own quality gate and its own
`awaiting_review` pause.

The one check that must stay ahead of the split is PDF password protection —
`_is_password_protected()` is lifted out of `pre_validator.py` into the splitter as a
guard, since `pypdf` cannot read an encrypted PDF anyway.

### 2.3 Recursion guard

Child workflows are launched with `auto_split=False` in the workflow input. The
splitter activity is a no-op when that flag is false. A child can never re-split.

### 2.4 Children reuse the split classification — Step 3 is skipped

Detecting a boundary *is* classifying the page, so the work is already done. Each child
workflow is launched with the segment's `doc_type`, confidence and reasoning in its
input, and **Step 3 is skipped entirely** for split children: the classifier activity
is never called, `doc_type` comes straight from the splitter, and the pipeline
continues at Step 3.5 (fraud check) exactly as if the classifier had produced it. That
removes one Mistral call per child.

Two guarded fall-backs, so a weak split classification can never poison extraction —
in either case the child simply runs Step 3 the normal way:

1. The segment resolved to `others`, i.e. the splitter matched no configured type.
2. `min_confidence < SPLIT_CONFIDENCE_THRESHOLD` — the pages behind the segment were
   not confidently typed. (A segment a reviewer confirmed carries confidence 1.0: the
   review modal makes them pick the document type as well as the boundary, so their
   answer is reused rather than second-guessed.)

An unsplit document is untouched by any of this: `auto_split` off, splitter returns
`{"split": False}`, and the pipeline runs Steps 2 → 7 exactly as it does today.

### 2.5 Cost / latency envelope

Per packet: **1** OCR call (whole file) + `ceil(pages / SPLIT_PAGE_BATCH_SIZE)` agent
calls. The PoC made one agent call *per page*; batching 8 pages per call cuts a
24-page packet from 24 calls to 3. Then N × the normal per-document pipeline cost.
Packets over `SPLIT_MAX_PAGES` (default 50) are rejected rather than silently
truncated.

---

## 3. Work breakdown

### Phase 0 — Config & schema groundwork

**`config.py`** — add to `Settings`:

```python
ENABLE_DOC_SPLITTING: bool  = Field(default=False, description="Detect and split multi-document packets (Step 1.5)")
SPLITTER_AGENT_ID: str      = Field(default="",    description="Page-Boundary Splitter Agent ID from Mistral Studio")
SPLIT_CONFIDENCE_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0, description="Below this, a page boundary is routed to human review")
SPLIT_PAGE_BATCH_SIZE: int  = Field(default=8, gt=0, description="Pages sent to the splitter agent per call")
SPLIT_MAX_PAGES: int        = Field(default=50, gt=0, description="Reject packets longer than this")
SPLIT_REQUIRE_REVIEW: bool  = Field(default=True, description="Pause for human confirmation when any page is below threshold")
SPLIT_MERGE_ORPHANS: bool   = Field(default=True, description="Merge low-confidence single-page outliers into the preceding segment")
```

Ship `ENABLE_DOC_SPLITTING=false` so existing behaviour is byte-identical until the
flag is flipped.

**`db/models.py`** — `Document` gains:

```python
parent_document_id   = Column(String, ForeignKey("documents.id"), nullable=True, index=True)
page_range           = Column(String, nullable=True)   # "3-5" (1-based, inclusive) — child only
split_doc_type_hint  = Column(String, nullable=True)   # splitter's guess, pre-Step-3
split_confidence     = Column(Float,  nullable=True)   # min page confidence in the segment
is_split_parent      = Column(Boolean, nullable=False, default=False)
split_manifest       = Column(JSON,   nullable=True)   # parent only: segments + per-page audit trail

children = relationship("Document", backref=backref("parent", remote_side=[id]), cascade="all")
```

**Alembic migration** — new revision in `migrations/versions/` adding the six columns
plus the `parent_document_id` index. `init_db()` self-creates on fresh installs; the
migration covers existing deployments. All columns are nullable or defaulted, so it is
a purely additive change with no backfill.

**New status values** — `split` (parent, terminal) and `awaiting_split_review`
(parent, paused). Add both to `StatusBadge.jsx`'s colour map.

---

### Phase 1 — Core splitting engine (pure, no workflow, no I/O beyond pypdf)

**New file: `backend-v2/tools/splitter.py`**

This is the testable heart. Every function is sync and side-effect-light so it can be
unit-tested without touching the Mistral API.

```python
from pydantic import BaseModel, Field

class PageClassification(BaseModel):
    page_index: int                       # 0-based, aligns with pypdf + OCR page.index
    doc_type: str                         # snake_case key from get_supported_doc_types(), or "others"
    is_first_page: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""

class Segment(BaseModel):
    doc_type: str
    start: int                            # 0-based inclusive
    end: int                              # 0-based inclusive
    pages: list[int]
    min_confidence: float = 1.0
    verified: bool | None = None
    output_file: str | None = None
    child_document_id: str | None = None
```

Note the deliberate deviation from the PoC: `doc_type` is a plain `str` validated
against `get_supported_doc_types()` at parse time, **not** an `Enum`. Types are runtime
config — an enum would have to be regenerated every time someone edits
`storage/classification_config.json` from the Settings page.

Functions:

| Function | Responsibility |
|---|---|
| `is_splittable(file_path) -> tuple[bool, str]` | PDF? not encrypted? `2 <= page_count <= SPLIT_MAX_PAGES`? Returns the reason on false. Images and DOCX are single-document by definition. |
| `build_type_catalogue() -> list[dict]` | `get_supported_doc_types()` joined with per-type field labels from `load_templates()`, e.g. `{"key": "bank_statement", "display": "Bank Statement", "cues": ["account_number", "ifsc", "closing_balance"]}`. This is what makes the prompt type-aware **without hardcoding cues** — the cues are the template field labels the team already maintains. |
| `parse_page_classifications(raw, page_indexes, allowed_types)` | Coerces the agent's JSON array into `PageClassification`s. Unknown `doc_type` → `"others"` with confidence clamped to 0.0 so it trips the review gate; missing pages backfilled as low-confidence continuations. |
| `segment_pages(classifications) -> list[Segment]` | Deterministic boundary logic, ported from the PoC. |
| `merge_orphans(segments, classifications)` | Post-pass, see below. |
| `verify_segments(segments, pages_md, templates)` | Optional regex sanity check — see §3.1. |
| `split_pdf(input_path, segments, out_dir, base_name)` | pypdf write, one file per segment, into `storage/splits/{parent_id}/`. |
| `build_segments_from_overrides(overrides, total_pages)` | Rebuilds `Segment`s from human-confirmed boundaries; validates that they are contiguous and cover every page. |

**`segment_pages` — the ported logic, with two corrections to the PoC:**

```python
def segment_pages(classifications: list[PageClassification]) -> list[Segment]:
    segments: list[Segment] = []
    current: Segment | None = None

    for i, pc in enumerate(classifications):
        prev_type = classifications[i - 1].doc_type if i > 0 else None

        # New doc when: first page overall, agent flagged a fresh header,
        # or the type changed from the previous page.
        start_new = (i == 0) or pc.is_first_page or (pc.doc_type != prev_type)

        # Same type + no fresh header => continuation, never split.
        # (Handles p2/p3 of a bank statement the agent typed correctly.)
        if pc.doc_type == prev_type and not pc.is_first_page:
            start_new = False

        if start_new or current is None:      # `or current is None` — PoC could NPE here
            if current:
                segments.append(current)
            current = Segment(doc_type=pc.doc_type, start=i, end=i,
                              pages=[i], min_confidence=pc.confidence)
        else:
            current.end = i
            current.pages.append(i)
            current.min_confidence = min(current.min_confidence, pc.confidence)

    if current:
        segments.append(current)
    return segments
```

Corrections vs. the PoC:

1. **`current is None` guard.** In the PoC, if the first element ever evaluated
   `start_new` as false — possible once a review override edits page 0 — `current.end`
   raises `AttributeError`.
2. **`merge_orphans()` post-pass.** A single page whose type differs from *both*
   neighbours and whose confidence is below threshold is merged into the preceding
   segment rather than becoming a 1-page document. This is the single biggest source of
   over-splitting on real packets (a mid-statement page carrying a stray letterhead).
   Gated by `SPLIT_MERGE_ORPHANS` so it can be turned off if it ever masks a real
   boundary.

#### 3.1 ID-marker verification without hardcoded regexes

The PoC hardcodes `ID_MARKERS = {"aadhaar_card": ..., "pan_card": ...}`. Replace it
with an **optional per-template field**:

```jsonc
// storage/templates.json
"pan_card": {
  "fields": [ ... ],
  "is_kyc": true,
  "id_marker": "\\b[A-Z]{5}\\d{4}[A-Z]\\b"   // new, optional
}
```

`verify_segments()` compiles `id_marker` when present and searches the segment's
concatenated OCR markdown; types without a marker get `verified: None` (the PoC's "no
rule for this type" case). `utils/templates.py::load_templates()` normalises
`id_marker` to `None` when absent — same place it already defaults `is_kyc`, `use_vlm`
and field `weight` — and the Templates UI gets one optional text input for it. A bad
regex is caught at save time and rejected with a 400 rather than exploding inside the
workflow.

Verification is **advisory**: a `verified: False` segment still processes, but the flag
lands in the manifest and forces the review gate open.

---

### Phase 2 — The splitter agent

**`agents_config.py`** — new entry:

```python
{
    "env_var": "SPLITTER_AGENT_ID",
    "name": "Document Boundary Splitter",
    "description": "Classifies each page of a multi-document packet and flags which pages start a new document.",
    "instructions": """<see below>""",
    "model": "mistral-large-latest",
    "completion_args": {"temperature": LLM_TEMPERATURE, "top_p": 1.0, "max_tokens": LLM_MAX_TOKENS},
}
```

Instruction skeleton — note it carries **no document-type list and no per-type cues**;
both are injected per call from the runtime config, exactly as
`activities/classifier.py` already does with `types_list_str`:

```
You are the Boundary Splitter Agent in an IDP pipeline. You receive the OCR markdown
of several CONSECUTIVE pages from one packet that contains multiple stitched-together
documents, plus the list of supported document types with their expected fields.

For EACH page you receive, decide:
  - doc_type      : exactly one key from the supplied list, or "others"
  - is_first_page : true ONLY if the page opens a NEW document
  - confidence    : 0.0-1.0
  - reasoning     : one short sentence for the audit trail

FIRST-PAGE RULES
- true  : header/title block, "Page 1 of N", a fresh identity (new account / consumer /
          policy number), a new statement or billing period, or a type change.
- false : continuation — no fresh header, a table continuing mid-row, "continued",
          page number > 1, same identity as the previous page.
- Two documents of the SAME type back-to-back: the page opening the second one is
  still is_first_page = true.

Be conservative: when a page could be a continuation, LOWER the confidence rather than
guessing a boundary. A missed boundary is recoverable by a human; a wrong one splits a
document in half.

Return ONLY a JSON object: {"pages": [{"page_index": int, "doc_type": str,
"is_first_page": bool, "confidence": float, "reasoning": str}, ...]} with one entry per
page supplied, echoing back the page_index you were given.
```

Run `python create_or_update_agents.py` → writes `SPLITTER_AGENT_ID` into `.env`.

**`api/routers/v1/settings.py`** — add `"splitter"` to `AGENT_PIPELINE_META` at
`"step": 1.5` and to the `agent_configs` list in `list_agents()`, so it appears on the
Agents page like every other agent.

---

### Phase 3 — The activity and the fan-out

**New file: `backend-v2/activities/splitter.py`**

```python
@workflows.activity()
async def splitter_activity(document_id: str, file_path: str) -> dict:
    """
    Step 1.5 — Packet split detection.

    Returns:
      {"split": False, "reason": "..."}                                   # single document
      {"split": True, "segments": [...], "pages": [...],
       "needs_review": bool}                                              # packet detected
    """
```

Flow:

1. `is_splittable()` → early return `{"split": False, "reason": ...}` for images, DOCX,
   1-page PDFs, encrypted PDFs, and over-length packets.
2. `extract_with_ocr(file_path, "unknown")` — one call, all pages. Build
   `pages_md[index] = markdown` keyed on `page.index` so it aligns 1:1 with
   `PdfReader.pages` ordering. If OCR returns fewer pages than pypdf reports, abort the
   split (`{"split": False, "reason": "ocr_page_mismatch"}`) — a misaligned index would
   cut the PDF in the wrong place, which is worse than not splitting at all.
3. Batch pages into groups of `SPLIT_PAGE_BATCH_SIZE`, each batch carrying a one-page
   look-back for continuity context. Call
   `client.agents.complete_async(agent_id=settings.SPLITTER_AGENT_ID,
   response_format={"type": "json_object"})` per batch, concurrently via
   `asyncio.gather`. Reuse `_extract_text()` for content coercion — lift it into
   `utils/` and import from both call sites, since it is currently duplicated verbatim
   in `activities/classifier.py` and `activities/pre_validator.py`.
4. `parse_page_classifications()` → `segment_pages()` → `merge_orphans()` →
   `verify_segments()`.
5. `needs_review = SPLIT_REQUIRE_REVIEW and (any page below threshold or any segment
   with `verified is False`)`.
6. Errors follow the house pattern: `db.update_error(document_id, {...,
   "stage": "splitter"})`. **Exception:** a splitter failure should *degrade*, not kill
   the upload — the workflow catches it and continues as a single document with a
   warning on the parent, because the packet is still processable whole.

**New file: `backend-v2/activities/split_fanout.py`** — separate activity, because it
does DB writes and workflow launches and must be individually retryable:

```python
@workflows.activity()
async def split_fanout_activity(document_id: str, file_path: str,
                                segments: list[dict], claim_id: str | None) -> dict:
```

1. `split_pdf()` → `storage/splits/{parent_id}/{nn}_{doc_type}.pdf`. Writing into a
   per-parent subdirectory sidesteps `utils/file_handler.py::save_file()`'s
   filename-collision problem (it writes `storage/{filename}` verbatim, so two packets
   named `scan.pdf` already overwrite each other today).
2. For each segment, insert a child `Document`: `filename` =
   `"{parent_stem} — {Display Type} (p{start}-{end}).pdf"`, `file_hash` = sha256 of the
   child bytes, plus `parent_document_id`, `page_range`, `split_doc_type_hint`,
   `split_confidence`, and the inherited `customer_id`.
3. Launch each child with
   `workflows.execute_workflow_async("document_processing_workflow",
   input={document_id, filename, file_path, "auto_split": False,
   "preclassified_doc_type": ..., "preclassified_confidence": ...,
   "preclassified_reasoning": ...})`; store the returned `execution_id` as the child's
   `workflow_run_id`. The pre-classification fields are sent empty when the segment
   resolved to `others` or fell below the confidence threshold (§2.4), which makes the
   child run Step 3 normally.
4. If the parent was uploaded with a `claim_id`, call
   `claim_db.link_document_to_claim()` for each child and **unlink the parent** — a
   claim wants the constituent documents, not the packet.
5. Write `split_manifest` onto the parent (segments + every `PageClassification`, for
   audit), set `status="split"` and `is_split_parent=True`.

**`workflow.py`** — wire it in. The signature gains a defaulted parameter so existing
callers and in-flight executions are unaffected:

```python
async def run(self, document_id: str, filename: str, file_path: str,
              auto_split: bool = True,
              preclassified_doc_type: str = "",
              preclassified_confidence: float = 0.0,
              preclassified_reasoning: str = "") -> dict:
    ...
    # Step 1.5 — Split detection
    if auto_split and settings.ENABLE_DOC_SPLITTING:
        await _update_status(document_id, "splitting")
        try:
            split_result = await splitter_activity(document_id, file_path)
        except Exception as e:
            logger.warning(f"[Document {document_id}] Splitter failed, processing as single document: {e}")
            split_result = {"split": False}

        if split_result.get("split"):
            segments = split_result["segments"]

            if split_result.get("needs_review"):
                await _update_status_and_message(
                    document_id, "awaiting_split_review",
                    f"{len(segments)} documents detected — confirm boundaries.")
                decision = await self.wait_for_input(SplitDecisionRequest, timeout=timedelta(hours=24))
                if not decision.approved:
                    split_result["split"] = False          # user says it's one document
                elif decision.segments:
                    segments = [s.model_dump() for s in decision.segments]

            if split_result.get("split"):
                fanout = await split_fanout_activity(document_id, file_path, segments, claim_id)
                logger.info(f"[Document {document_id}] Split into {len(fanout['children'])} documents")
                return {"status": "split", **fanout}       # parent workflow ends here

    # Step 2 — Pre-Validation (unchanged) …
    # Step 3 — Classify, or reuse the split classification
    if preclassified_doc_type:
        doc_type = preclassified_doc_type            # no classifier call
        classifier_result = {"doc_type": doc_type, "confidence": preclassified_confidence,
                             "reasoning": preclassified_reasoning, "source": "splitter"}
    else:
        classifier_result = await classifier_activity(document_id, clean_file_path)
        doc_type = classifier_result["doc_type"]
```

All four new parameters are defaulted, so in-flight executions and any caller that
does not know about splitting keep working unchanged.

**`schemas/documents.py`**:

```python
class SegmentOverride(BaseModel):
    doc_type: str
    start: int
    end: int

class SplitDecisionRequest(BaseModel):
    approved: bool                                    # False = "it's one document, don't split"
    segments: Optional[list[SegmentOverride]] = None  # None = accept boundaries as detected
```

Add the import to the `imports_passed_through()` block at the top of `workflow.py`.

---

### Phase 4 — API surface

**`api/routers/v1/documents.py`**

| Endpoint | Change |
|---|---|
| `POST /upload` | New `auto_split: bool = Query(True)`, passed into the workflow input. |
| `POST /upload/batch` | Same flag, applied to every file in the batch. |
| `GET /documents` | New `include_children: bool = Query(True)`. When false, filter `parent_document_id IS NULL`. Every row gains `parent_document_id`, `is_split_parent`, `page_range`, `child_count` so the UI can nest without an N+1. |
| `GET /documents/{id}/split` | **New.** Returns the parent's `split_manifest` plus live child rows (id, filename, doc_type, status, page_range, confidence). 404 when the document is not a split parent. |
| `POST /documents/{id}/split-decision` | **New.** Body = `SplitDecisionRequest`; resumes the paused parent via the SDK's send-input call on `workflow_run_id`, mirroring however the existing duplicate/reviewer resume endpoint in `api/routers/v1/workflow.py` does it. |
| `DELETE /documents/{id}` | Cascade: deleting a parent soft-deletes every child, cancels each child's `workflow_run_id`, and removes `storage/splits/{parent_id}/`. Deleting a lone child leaves the parent intact. |
| `GET /status/{id}` | Include `parent_document_id` / `is_split_parent` so `useDocumentPoller` can redirect the UI from a parent that just turned `split` to its children. |

**`api/routers/v1/settings.py`** — `GET/PUT /settings/splitting` over a
`storage/splitting_config.json`, following the exact shape of the existing
normalization/classification settings pair:
`{enabled, confidence_threshold, require_review, merge_orphans, max_pages}`. Env vars
remain the defaults; the JSON file overrides them at read time — same precedence
`utils/classification_config.py` already uses.

---

### Phase 5 — Frontend (`frontend-v2`)

| File | Change |
|---|---|
| `src/api/client.js` | `uploadDocument(file, onProgress, {autoSplit})`; new `getSplitManifest(id)` and `submitSplitDecision(id, payload)`. |
| `src/pages/Upload.jsx` | "Auto-split multi-document packets" toggle in the batch strip. `DocPoller` recognises `status === 'split'` and swaps the row for a "Split into N documents" summary linking to the children. |
| `src/pages/Documents.jsx` | Nest children under their parent (indent + a "pages 3–5" chip). Parent row is collapsible and shows aggregate child status. |
| `src/components/ui/StatusBadge.jsx` | `split` (neutral/indigo) and `awaiting_split_review` (amber, same family as `awaiting_review`). |
| `src/components/ui/SplitReviewModal.jsx` | **New.** Page thumbnails in a strip (rendered from `/documents/{id}/file`); each boundary is a toggle ("starts a new document"), each segment gets a doc-type dropdown fed by `GET /settings/classification`. Submits `SplitDecisionRequest`. |
| `src/components/ui/PipelineSteps.jsx` | Insert the splitter at step 1.5. |
| `src/pages/Settings.jsx` | Splitting section bound to `GET/PUT /settings/splitting`. |

---

### Phase 6 — Tests

**`backend-v2/tests/test_splitter.py`** (new, no network — this is where the PoC's
`_self_test()` lands, promoted to real cases):

1. Multi-page + back-to-back same-type — the PoC's exact fixture: 3-page bank statement
   → utility bill → aadhaar → pan → **two** salary slips, asserting the two slips land
   in separate segments.
2. Single-document packet → exactly one segment (must NOT trigger a split).
3. Orphan merge: `[stmt, stmt, invoice(conf 0.4), stmt]` merges the low-confidence
   invoice page back into the statement.
4. Orphan merge disabled → 3 segments.
5. Unknown `doc_type` from the agent → coerced to `others`, confidence 0.0, trips review.
6. Missing page in the agent response → backfilled as a low-confidence continuation.
7. `build_segments_from_overrides` accepts human-confirmed boundaries and rejects
   overlapping, gapped, or out-of-range ones.
8. `is_splittable` matrix: png, docx, 1-page pdf, encrypted pdf, 60-page pdf.
9. `split_pdf` page fidelity: child page counts sum to the parent's, and page N of child
   K matches the source page (compare extracted text).
10. `verify_segments` with and without a template `id_marker`; an invalid regex is
    rejected at template-save time, not at split time.

**`backend-v2/tests/test_api.py`** — `auto_split=false` skips the splitter;
`GET /documents/{id}/split` 404s on a normal document; parent delete cascades to
children.

**Manual E2E** — build a fixture packet from `test_docs/` (concatenate a PAN card, a
2-page bank statement, and a utility bill), upload with splitting on, confirm three
children complete independently and `GET /cross-validate/latest` still resolves.

---

## 4. File-change summary

**New (8)**

```
backend-v2/tools/splitter.py                       core engine (pure, 23 unit tests)
backend-v2/activities/splitter.py                  Step 1.5 — OCR + batched page classification
backend-v2/activities/split_fanout.py              pypdf write + child rows + workflow fan-out
backend-v2/utils/split_config.py                   storage/splitting_config.json load/save
backend-v2/tests/test_splitter.py
backend-v2/migrations/versions/a1b2c3d4e5f6_document_split_columns.py
frontend-v2/src/components/ui/SplitReviewModal.jsx
storage/splitting_config.json                      (runtime, created on first save)
storage/splits/{parent_id}/                        (runtime, one dir per split packet)
```

**Modified (12)**

```
backend-v2/config.py                    7 settings
backend-v2/db/models.py                 6 Document columns + self-relationship
backend-v2/db/database.py               defensive ALTERs in init_db()
backend-v2/db/operations.py             get_or_create_split_child, mark_split_parent, …
backend-v2/db/claim_operations.py       get/remove claim links for a document
backend-v2/schemas/documents.py         SplitDecisionRequest, SegmentOverride, status lineage
backend-v2/workflow.py                  auto_split + preclassified_* params, Step 1.5, Step 3 skip
backend-v2/agents_config.py             SPLITTER_AGENT_ID entry
backend-v2/utils/templates.py           optional id_marker + validate_id_markers()
backend-v2/api/routers/v1/documents.py  upload flag, 2 new endpoints, list/status/delete cascade
backend-v2/api/routers/v1/settings.py   /settings/splitting, 400 on bad id_marker, agent meta
backend-v2/.env.example                 SPLITTER_AGENT_ID + the 6 SPLIT_* vars
frontend-v2/src/api/client.js
frontend-v2/src/pages/{Upload,Documents,Settings}.jsx
frontend-v2/src/components/ui/{StatusBadge,PipelineSteps}.jsx
frontend-v2/src/hooks/useDocumentPoller.js
```

No new dependencies — `pypdf==6.14.2` and `pymupdf==1.28.0` are already pinned in
`requirements.txt`.

---

## 5. Sequencing

| # | Milestone | Depends on | Independently shippable? |
|---|---|---|---|
| 1 | Phase 0: settings + migration + statuses | — | Yes (dormant, flag off) |
| 2 | Phase 1: `tools/splitter.py` + `tests/test_splitter.py` | 1 | Yes — boundary logic is verifiable with zero API calls |
| 3 | Phase 2: splitter agent provisioned | — | Yes (parallel with 2) |
| 4 | Phase 3: activities + workflow wiring | 1, 2, 3 | Yes — backend-complete, drivable via curl |
| 5 | Phase 4: API surface | 4 | Yes |
| 6 | Phase 5: frontend | 5 | Yes |
| 7 | Phase 6: E2E, then flip `ENABLE_DOC_SPLITTING=true` | all | — |

Milestone 2 is the one worth front-loading: the boundary logic is where the accuracy
lives, and it is fully testable before a single API call is made.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| **Over-splitting** cuts a real document in half — the worst failure mode, because downstream extraction then produces two half-populated records | Conservative agent instructions, orphan merge, confidence gate defaulting to `require_review=true`, and a review modal that can re-merge before any child is created |
| **OCR/pypdf page misalignment** would split at the wrong offset | Hard-assert `len(ocr_pages) == PdfReader.page_count` and key on `page.index`; abort the split on mismatch rather than guessing |
| **Cost blow-up** on long packets | `SPLIT_MAX_PAGES` cap, batched classification, single OCR pass |
| **Duplicate-detection noise** — children of two uploads of the same packet collide on hash | Correct behaviour: the second packet's children are flagged duplicates and pause for override, exactly as a re-uploaded standalone document does today |
| **Classification config drift** — a type is deleted from Settings while a split sits paused mid-review | `parse_page_classifications` and the review endpoint both re-validate against the *current* catalogue; unknown types degrade to `others` |
| **Fan-out failure halfway through** (3 of 5 children launched) | `split_fanout_activity` is idempotent on `(parent_id, segment_index)` — it skips children that already exist, so an activity retry completes the fan-out instead of duplicating it |

---

## 7. What changed during implementation

Six things came out differently from the plan above. All are already in the code.

1. **Children skip Step 3 entirely** (§2.4) — the original plan re-classified every
   child with the vision classifier and kept the split type as a hint. Now the split
   type is authoritative and the classifier call is skipped, with two guarded
   fall-backs.
2. **Two-level enable switch.** `ENABLE_DOC_SPLITTING` (env) is the deploy-level kill
   switch checked by the workflow; `enabled` in `storage/splitting_config.json` is the
   runtime toggle checked inside the activity. With the env flag off, the Settings
   toggle does nothing — that is deliberate, so a deployment can hard-disable the
   feature regardless of what is in the UI.
3. **`merge_orphans` is stricter than planned.** It only fires when the pages either
   side of the outlier are the *same* type, and it merges all three into one segment.
   The looser "merge any low-confidence single page into the preceding segment" rule
   would have swallowed genuine one-page documents (a PAN card between two statements).
4. **`build_segments_from_overrides` replaced `apply_review_overrides`.** The review
   modal submits final boundaries rather than per-page corrections, so segments are
   rebuilt directly and validated for contiguity and full coverage.
5. **Boundary rebuilding runs as an activity** (`rebuild_segments_activity`), not
   inline in workflow code — it reads the classification config off disk, which is I/O
   and does not belong in a deterministic workflow body.
6. **A splitter failure never fails the upload.** `splitter_activity` deliberately does
   not call `db.update_error`; the workflow catches, logs, and processes the packet
   whole. Marking the document failed would contradict the run that then completes.

### Verification performed

- 23 unit tests in `tests/test_splitter.py` — all pass (boundary logic, orphan merging,
  malformed agent responses, reviewer overrides, `id_marker` checks, PDF fidelity).
  pytest is not installed in this checkout, so they were executed through a shim
  runner; they are ordinary pytest tests and need no changes to run under `pytest`.
- Offline simulation of `splitter_activity` over a real 6-page PDF with a stubbed OCR
  and agent: correct 3-way split, 2 agent calls at batch size 4, look-back page present
  in the second prompt, and the OCR/pypdf misalignment guard aborting the split.
- Schema migration applied to a scratch SQLite database; parent and child rows persist.
- `vite build` clean; `eslint` reports no new findings (the two it does report are
  pre-existing on `main`).

---

## 8. Open questions for the team

1. **Should a split parent stay visible in the Documents list?** Plan assumes yes
   (collapsible, with children nested). The alternative — hide parents entirely — is a
   one-line change to `GET /documents`.
2. **Default for `SPLIT_REQUIRE_REVIEW`.** Plan defaults it to `true` (safer, but every
   ambiguous packet blocks on a human). Flipping to `false` makes splitting fully
   automatic and relies on the per-child `awaiting_review` gate to catch damage.
3. **Claim linkage.** Plan unlinks the parent and links each child. If the claim UI
   expects one row per uploaded file, that needs revisiting before Phase 3.
