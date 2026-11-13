/**
 * The document status vocabulary the backend workflow emits, grouped by what
 * the UI should do about each group. Kept out of AppStore.jsx so both the store
 * and the pages can import it without tripping fast-refresh.
 */

// A document the pipeline still owns. `splitting` and `awaiting_split_review`
// belong here: while the splitter agent works, the packet is very much in
// flight, and leaving those out empties the processing queue mid-run — which
// tears down the live pipeline, stops the status pollers, and trips the
// "queue drained" redirect on the Processing page.
export const ACTIVE_STATUSES = [
  'pending',
  'processing',
  'splitting',
  'awaiting_split_review',
  'pre_validating',
  'preprocessing',
  'classifying',
  'checklist',
  'checklist_hold',
  'awaiting_checklist_review',
  'fraud_checking',
  'extracting',
  'validating',
  'auto_verifying',  // KYC documents: automatic reference check after validation
];

// Human review of extracted data. Deliberately excludes `awaiting_split_review`
// and `awaiting_checklist_review`, which are answered in their own modals on the
// Processing page rather than on the Validation page.
export const REVIEW_STATUSES = ['awaiting_review', 'duplicate'];

export const SPLIT_REVIEW_STATUS = 'awaiting_split_review';

// The Step 3.2 batch checklist barrier. Every document in an upload parks here
// and they are released together. `awaiting_checklist_review` marks the one
// document a reviewer acts on; `checklist_hold` is the rest of the batch waiting
// behind it. Both are answered by the same batch-scoped decision.
export const CHECKLIST_REVIEW_STATUS = 'awaiting_checklist_review';
export const CHECKLIST_HOLD_STATUS = 'checklist_hold';
export const CHECKLIST_GATE_STATUSES = [CHECKLIST_REVIEW_STATUS, CHECKLIST_HOLD_STATUS];

// Terminal states. The pipeline no longer owns these documents, so pollers stop
// and the processing queue drops them. `expired` is a human gate that ran out
// its 24h window with no decision — unlike `rejected` it reflects nobody having
// answered rather than a decision, which is why it is retryable.
export const TERMINAL_STATUSES = ['completed', 'rejected', 'failed', 'error', 'expired', 'deleted'];

// States the retry endpoint accepts. `completed` and in-flight documents are
// refused by the backend, so they are absent here too.
export const RETRYABLE_STATUSES = ['failed', 'error', 'expired'];

// ─── Pipeline position ──────────────────────────────────────────────
// Anything at or past this phase means the pipeline is finished — every visible
// step reads as done.
export const TERMINAL_PHASE = 11;

// Backend status -> pipeline phase. Statuses belonging to a switched-off step
// simply never arrive, so they cost nothing by staying in the table.
export const STATUS_PHASE = {
  pending: 0,
  processing: 1,               // intake
  splitting: 2,                // packet split detection
  awaiting_split_review: 2,
  split: TERMINAL_PHASE,       // packet done — its children carry on separately
  pre_validating: 3,
  preprocessing: 4,
  classifying: 5,
  checklist: 6,                    // batch checklist (Step 3.2)
  checklist_hold: 6,               // parked behind the batch barrier
  awaiting_checklist_review: 6,    // parked at the checklist gate
  fraud_checking: 6,      // runs after classification, alongside the checklist
  extracting: 7,
  validating: 8,
  auto_verifying: 8,               // KYC reference check, between validation and review
  awaiting_review: 9,
  completed: TERMINAL_PHASE,
  rejected: -1,
  error: -1,
};

/** How far through the pipeline a status is (higher = further along). */
export const statusPhase = (status) => STATUS_PHASE[status] ?? 0;
