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
  'fraud_checking',
  'extracting',
  'validating',
];

// Human review of extracted data. Deliberately excludes `awaiting_split_review`,
// which is reviewed in the split modal, not on the Validation page.
export const REVIEW_STATUSES = ['awaiting_review', 'duplicate'];

export const SPLIT_REVIEW_STATUS = 'awaiting_split_review';
