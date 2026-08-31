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
