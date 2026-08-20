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

// The Step 3.2 batch checklist gate. Only ever set on one document per batch —
// the last one to classify — which holds the gate for all of its siblings.
export const CHECKLIST_REVIEW_STATUS = 'awaiting_checklist_review';
