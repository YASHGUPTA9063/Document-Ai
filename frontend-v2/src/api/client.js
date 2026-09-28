import axios from 'axios';

// Relative by default — nginx (Docker) and the Vite dev server both proxy
// /api/v1 straight through to the backend, so no hostname is baked into the
// bundle and the browser never makes a cross-origin request.
const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const api = axios.create({ baseURL: BASE, timeout: 30000 });

// ─── Response interceptor: normalize errors ──────
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err?.response?.data?.detail ||
      err?.response?.data?.message ||
      err?.message ||
      'Unknown error';
    return Promise.reject(new Error(msg));
  }
);

// ─── Document APIs ───────────────────────────────

/**
 * Upload a document.
 * @param {File} file
 * @param {(pct: number) => void} onProgress
 * @param {{autoSplit?: boolean, batchId?: string}} options - autoSplit: detect multi-document
 *   packets and split them. batchId: join an existing upload batch instead of starting a new
 *   one — how the documents a checklist reported missing get added to the batch waiting on them.
 * @returns {Promise<{document_id, filename, status, message, workflow_run_id, batch_id}>}
 */
export async function uploadDocument(file, onProgress, { autoSplit = true, batchId = null } = {}) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/documents/upload', form, {
    params: { auto_split: autoSplit, ...(batchId ? { batch_id: batchId } : {}) },
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/**
 * Batch upload — sends all files in a single multipart request to /upload/batch.
 * Server processes them concurrently and returns per-file results.
 * @param {File[]} files
 * @param {(pct: number) => void} onProgress  — overall upload progress 0-100
 * @param {{autoSplit?: boolean, batchId?: string}} options
 * @returns {Promise<{ total, succeeded, failed, batch_id, results: Array }>}
 */
export async function uploadDocumentsBatch(files, onProgress, { autoSplit = true, batchId = null } = {}) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const { data } = await api.post('/documents/upload/batch', form, {
    params: { auto_split: autoSplit, ...(batchId ? { batch_id: batchId } : {}) },
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000, // 5 min — large batches can take a while
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/**
 * Get workflow status for a document.
 * @param {string} documentId
 * @returns {Promise<WorkflowStatusResponse>}
 */
export async function getStatus(documentId) {
  const { data } = await api.get(`/documents/${documentId}/status`);
  return data;
}

/**
 * List documents (paginated).
 * @param {number} page
 * @param {number} limit
 */
export async function listDocuments(page = 1, limit = 50) {
  const pageNum = typeof page === 'number' ? page : 1;
  const limitNum = typeof limit === 'number' ? limit : 50;
  const { data } = await api.get('/documents', { params: { page: pageNum, limit: limitNum } });
  return data; // array
}

/**
 * Get full extracted data for a document.
 * @param {string} documentId
 */
export async function getExtractedData(documentId) {
  const { data } = await api.get(`/documents/${documentId}/extracted`);
  return data;
}

/**
 * Update extracted data for a document.
 * @param {string} documentId
 * @param {object} validatedData
 */
export async function updateExtractedData(documentId, rawFields) {
  const { data } = await api.put(`/documents/${documentId}/extracted`, { raw_fields: rawFields });
  return data;
}

/**
 * Signal duplicate decision.
 * @param {string} workflowRunId
 * @param {boolean} override
 */
export async function resumeDuplicate(workflowRunId, override) {
  const { data } = await api.post(`/workflow/${workflowRunId}/resume/duplicate`, { override });
  return data;
}

/**
 * Signal human review decision.
 * @param {string} workflowRunId
 * @param {boolean} approved
 * @param {object|null} corrections
 * @param {string|null} rejectionReason
 */
export async function resumeReview(workflowRunId, approved, corrections = null, rejectionReason = null) {
  const { data } = await api.post(`/workflow/${workflowRunId}/resume/review`, {
    approved,
    corrections,
    rejection_reason: rejectionReason,
  });
  return data;
}

/**
 * Fetch all pipeline agents (live from Mistral API + static workflow agents).
 * @returns {Promise<Array>}
 */
export async function getAgents() {
  const { data } = await api.get('/agents');
  return data;
}

/**
 * Start a fresh processing run for a document that failed, errored, or whose
 * review window expired. Starts a NEW workflow execution rather than resuming
 * the old one — a terminated run has no pending input to submit to.
 * @param {string} documentId
 * @returns {Promise<{document_id, status, workflow_run_id, message}>}
 */
export async function retryDocument(documentId) {
  const { data } = await api.post(`/documents/${documentId}/retry`);
  return data;
}

/**
 * Delete (soft) a document.
 * @param {string} documentId
 */
export async function deleteDocument(documentId) {
  const { data } = await api.delete(`/documents/${documentId}`);
  return data;
}

/**
 * Get the preview URL for a document.
 * @param {string} documentId
 * @returns {string}
 */
export function getDocumentFileUrl(documentId) {
  return `${BASE}/documents/${documentId}/file`;
}

/**
 * Get the URL for one page of a document rendered as a PNG.
 * The browser's PDF embed cannot be drawn on, so citation highlighting shows
 * the page as an image and overlays the OCR boxes on that instead.
 * @param {string} documentId
 * @param {number} pageIndex 0-based
 * @returns {string}
 */
export function getDocumentPageUrl(documentId, pageIndex) {
  return `${BASE}/documents/${documentId}/page/${pageIndex}`;
}

/**
 * Number of pages the document can be rendered as images. Non-PDFs report 1.
 * @param {string} documentId
 * @returns {Promise<{ page_count: number, renderable: boolean }>}
 */
export async function getDocumentPageCount(documentId) {
  const { data } = await api.get(`/documents/${documentId}/page-count`);
  return data;
}

/**
 * Get OCR bounding box blocks for field citation highlighting.
 * Available for any document OCR produced spatial blocks for — images and
 * PDFs alike. DOCX and documents processed before the feature existed report
 * available: false.
 * @param {string} documentId
 * @returns {Promise<{ blocks: Array, available: boolean }>}
 */
export async function getOcrBlocks(documentId) {
  const { data } = await api.get(`/documents/${documentId}/ocr-blocks`);
  return data;
}

/**
 * Get templates from backend
 * @returns {Promise<object>}
 */
export async function getTemplates() {
  const { data } = await api.get('/templates');
  return data;
}

/**
 * Save templates to backend
 * @param {object} templatesData
 * @returns {Promise<object>}
 */
export async function saveTemplates(templatesData) {
  const { data } = await api.put('/templates', templatesData);
  return data;
}

/**
 * Generate a template from a sample document.
 * @param {string} templateName
 * @param {File} file
 * @param {boolean} isKyc
 * @param {object|null} kycBoxes - Optional {signature: {x1,y1,x2,y2}, photo: {x1,y1,x2,y2}}
 * @returns {Promise<{success: boolean, template_name: string, fields: Array, is_kyc: boolean}>}
 */
export async function generateTemplateFromSample(templateName, file, isKyc = false, kycBoxes = null, useVlm = false) {
  const form = new FormData();
  form.append('file', file);
  const params = { template_name: templateName, is_kyc: isKyc, use_vlm: useVlm };
  if (kycBoxes) {
    params.kyc_boxes = JSON.stringify(kycBoxes);
  }
  const { data } = await api.post('/templates/generate', form, {
    params,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return data;
}

/**
 * Delete a template.
 * @param {string} templateName
 * @returns {Promise<object>}
 */
export async function deleteTemplate(templateName) {
  const { data } = await api.delete(`/templates/${templateName}`);
  return data;
}

/**
 * Get the URL for a cropped signature/photo image.
 * @param {string} documentId
 * @param {string} filename - e.g. "signature.png" or "photo.png"
 * @returns {string}
 */
export function getCropUrl(documentId, filename) {
  return `${BASE}/documents/${documentId}/crops/${filename}`;
}

/**
 * Verify a signature or photo against a reference image.
 * Runs the DINO + Mistral Vision + Judge pipeline.
 * @param {string} documentId
 * @param {File} referenceFile - The reference signature/photo to compare against
 * @param {'signature'|'photo'} verificationType
 * @returns {Promise<object>} Full verification result with verdict, scores, analysis
 */
export async function verifySignature(documentId, referenceFile, verificationType = 'signature') {
  const form = new FormData();
  form.append('file', referenceFile);
  const { data } = await api.post(
    `/documents/${documentId}/verify-signature`,
    form,
    {
      params: { verification_type: verificationType },
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000, // 2 min — ML inference + Mistral API calls
    }
  );
  return data;
}

/**
 * Which optional pipeline stages this deployment has switched on. Both come
 * from the backend environment (ENABLE_DOC_SPLITTING / ENABLE_DOC_CHECKLIST)
 * and have no runtime override, so the answer is fixed for the session.
 * @returns {Promise<{doc_splitting: boolean, doc_checklist: boolean}>}
 */
export async function getFeatureFlags() {
  const { data } = await api.get('/settings/features');
  return data;
}

/**
 * Get normalization settings.
 * @returns {Promise<object>}
 */
export async function getNormConfig() {
  const { data } = await api.get('/settings/normalization');
  return data;
}

/**
 * Save normalization settings.
 * @param {object} config
 * @returns {Promise<object>}
 */
export async function saveNormConfig(config) {
  const { data } = await api.put('/settings/normalization', config);
  return data;
}

/**
 * Get classification document types.
 * @returns {Promise<string[]>}
 */
export async function getClassificationConfig() {
  const { data } = await api.get('/settings/classification');
  return data;
}

/**
 * Save classification document types.
 * @param {string[]} docTypes
 * @returns {Promise<object>}
 */
export async function saveClassificationConfig(docTypes) {
  const { data } = await api.put('/settings/classification', docTypes);
  return data;
}

// ─── Batch checklist (Step 3.2) ──────────────────────

/**
 * The checklist for one upload batch: which of the configured classification
 * types are present, which are missing, and which document supplied each.
 * Computed live when the workflow has not evaluated the batch yet.
 * @param {string} batchId
 */
export async function getBatchChecklist(batchId) {
  const { data } = await api.get(`/batches/${batchId}/checklist`);
  return data;
}

/**
 * Answer for a whole batch held at the checklist gate. Every document in the
 * batch is parked behind the one gate, so the decision releases all of them.
 * Idempotent: re-calling on a released batch is a no-op.
 * @param {string} batchId
 * @param {boolean} proceed  true continues despite the missing types
 * @param {string} [note]    reviewer's reason, stored on the checklist
 */
export async function submitChecklistDecision(batchId, proceed, note = null) {
  const { data } = await api.post(`/batches/${batchId}/checklist-decision`, {
    proceed,
    note,
    rejection_reason: proceed ? null : note,
  });
  return data;
}

/**
 * Re-run the checklist for a batch. Releases every document behind the gate if
 * the batch now holds everything, so this is how newly uploaded documents
 * actually unblock the batch rather than just refreshing the display.
 * @param {string} batchId
 */
export async function evaluateBatchChecklist(batchId) {
  const { data } = await api.post(`/batches/${batchId}/checklist/evaluate`);
  return data;
}

// ─── Document splitting ──────────────────────────────

/**
 * Get the split manifest for a packet: detected segments, the per-page audit
 * trail, and the live state of each child document.
 * 404s when the document was never split.
 * @param {string} documentId
 * @returns {Promise<{document_id, filename, status, segments: Array, pages: Array, children: Array}>}
 */
export async function getSplitManifest(documentId) {
  const { data } = await api.get(`/documents/${documentId}/split`);
  return data;
}

/**
 * Answer a packet paused at the split review gate.
 * @param {string} documentId
 * @param {boolean} approved - false processes the file as one document
 * @param {Array<{doc_type: string, start: number, end: number}>|null} segments
 *        null accepts the detected boundaries; otherwise these replace them
 *        (0-based page indexes, inclusive, contiguous, covering every page)
 */
export async function submitSplitDecision(documentId, approved, segments = null) {
  const { data } = await api.post(`/documents/${documentId}/split-decision`, { approved, segments });
  return data;
}

/**
 * Get document splitting settings. `enabled` is reported for reference only —
 * it mirrors ENABLE_DOC_SPLITTING and cannot be changed through the API.
 * @returns {Promise<{enabled, confidence_threshold, page_batch_size, max_pages, require_review, merge_orphans}>}
 */
export async function getSplitSettings() {
  const { data } = await api.get('/settings/splitting');
  return data;
}

/**
 * Save document splitting settings. Only the tuning knobs are persisted; an
 * `enabled` key is ignored by the backend.
 * @param {object} config
 */
export async function saveSplitSettings(config) {
  const { data } = await api.put('/settings/splitting', config);
  return data;
}

/**
 * Get vLLM fallback settings.
 * @returns {Promise<{enabled: boolean, confidence_threshold: number}>}
 */
export async function getVllmSettings() {
  const { data } = await api.get('/settings/vllm');
  return data;
}

/**
 * Save vLLM fallback settings.
 * @param {{enabled: boolean, confidence_threshold: number}} config
 * @returns {Promise<object>}
 */
export async function saveVllmSettings(config) {
  const { data } = await api.put('/settings/vllm', config);
  return data;
}

// ─── Claim Processing APIs ────────────────────────────────────────────────────

/**
 * Create a new claim record.
 * @param {{ claimant_name, claim_type, policy_number, description, priority, amount }} payload
 */
export async function createClaim(payload) {
  const { data } = await api.post('/claims', payload);
  return data;
}

/**
 * List all claims.
 * @returns {Promise<Array>}
 */
export async function listClaims() {
  const { data } = await api.get('/claims');
  return data;
}

/**
 * Get extraction status for all docs linked to a claim.
 * @param {string} claimId
 * @returns {Promise<{ claim_status, total_docs, completed_docs, failed_docs, ready_to_process, doc_statuses }>}
 */
export async function getClaimStatus(claimId) {
  const { data } = await api.get(`/claims/${claimId}/status`);
  return data;
}

/**
 * Trigger the claim processing workflow.
 * @param {string} claimId
 * @returns {Promise<{ claim_id, workflow_run_id, status }>}
 */
export async function runClaimWorkflow(claimId) {
  const { data } = await api.post(`/claims/${claimId}/run`);
  return data;
}

export async function rerunClaimWorkflow(claimId) {
  const { data } = await api.post(`/claims/${claimId}/rerun`);
  return data;
}

/**
 * Get the final claim report (after workflow completes).
 * @param {string} claimId
 * @returns {Promise<{ claim_id, claimant_name, overall_status, suggestion, agent_results, processed_at }>}
 */
export async function getClaimReport(claimId) {
  const { data } = await api.get(`/claims/${claimId}/report`);
  return data;
}

/**
 * Submit adjuster's accept/reject decision.
 * @param {string} claimId
 * @param {'approve'|'reject'} decision
 * @param {string} [notes]
 */
export async function submitClaimDecision(claimId, decision, notes = '') {
  const { data } = await api.post(`/claims/${claimId}/decision`, { decision, notes });
  return data;
}

/**
 * Permanently delete a claim and its document links.
 * @param {string} claimId
 */
export async function deleteClaim(claimId) {
  const { data } = await api.delete(`/claims/${claimId}`);
  return data;
}

/**
 * Upload a document as part of a claim — passes claim_id and doc_type as query params.
 * @param {string} claimId
 * @param {File} file
 * @param {string} docType  e.g. "medical_report"
 * @param {(pct: number) => void} onProgress
 */
export async function uploadClaimDocument(claimId, file, docType, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/documents/upload', form, {
    params: { claim_id: claimId, doc_type: docType },
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/**
 * Cross-validate Name and DOB between the most recently completed
 * PAN Card and Aadhaar Card documents in the system.
 * @returns {Promise<object>}
 */
export async function crossValidate() {
  const { data } = await api.get('/cross-validate/latest');
  return data;
}

/**
 * Cross-validate Name and DOB between the most recently completed
 * Passport and Driving License documents in the system.
 * @returns {Promise<object>}
 */
export async function crossValidatePassportDL() {
  const { data } = await api.get('/cross-validate/passport-dl');
  return data;
}

/**
 * Cross-validate Address between the most recently completed
 * Utility Bill and Bank Statement documents in the system.
 * @returns {Promise<object>}
 */
export async function crossValidateAddress() {
  const { data } = await api.get('/cross-validate/address');
  return data;
}

/**
 * Get the aggregated KYC verdict — calls the backend which runs
 * cross-validations + checks biometric verification + LLM verdict.
 * @returns {Promise<{verdict, confidence, summary, reasoning, risk_flags, checks}>}
 */
export async function getKycVerdict() {
  const { data } = await api.get('/kyc-verdict', { timeout: 60000 });
  return data;
}

// ─── KYC Process APIs ─────────────────────────────────────────────────────────

/**
 * Create a new KYC application with form data.
 * @param {{ applicant_name, fathers_name, date_of_birth, address, form_source, form_document_id }} payload
 */
export async function createKycApplication(payload) {
  const { data } = await api.post('/kyc', payload);
  return data;
}

/**
 * List all KYC applications.
 * @returns {Promise<Array>}
 */
export async function listKycApplications() {
  const { data } = await api.get('/kyc');
  return data;
}

/**
 * Get a single KYC application.
 * @param {string} kycId
 */
export async function getKycApplication(kycId) {
  const { data } = await api.get(`/kyc/${kycId}`);
  return data;
}

/**
 * Update KYC form data.
 * @param {string} kycId
 * @param {{ applicant_name, fathers_name, date_of_birth, address }} payload
 */
export async function updateKycForm(kycId, payload) {
  const { data } = await api.put(`/kyc/${kycId}`, payload);
  return data;
}

/**
 * Get extraction status of KYC linked documents.
 * @param {string} kycId
 */
export async function getKycStatus(kycId) {
  const { data } = await api.get(`/kyc/${kycId}/status`);
  return data;
}

/**
 * Upload an identity document for KYC verification.
 * @param {string} kycId
 * @param {File} file
 * @param {string|null} uploadBatch - batch id from an earlier upload, to group files added together
 * @param {(pct: number) => void} onProgress
 */
export async function uploadKycDocument(kycId, file, uploadBatch, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post(`/kyc/${kycId}/upload-doc`, form, {
    params: uploadBatch ? { upload_batch: uploadBatch } : {},
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/**
 * Trigger KYC verification (cross-validates form data vs document data).
 * @param {string} kycId
 * @param {string[]} [documentIds] - ID documents to verify against; omit for all extracted docs
 */
export async function runKycVerification(kycId, documentIds) {
  const body = documentIds?.length ? { document_ids: documentIds } : null;
  // Face + signature comparison each run several model calls — allow for it.
  const { data } = await api.post(`/kyc/${kycId}/verify`, body, { timeout: 300_000 });
  return data;
}

/**
 * Get the final KYC verification result.
 * @param {string} kycId
 */
export async function getKycResult(kycId) {
  const { data } = await api.get(`/kyc/${kycId}/result`);
  return data;
}

/**
 * Submit reviewer's KYC decision (approve/reject).
 * @param {string} kycId
 * @param {'approve'|'reject'} decision
 * @param {string} [notes]
 */
export async function submitKycDecision(kycId, decision, notes = '') {
  const { data } = await api.post(`/kyc/${kycId}/decision`, { decision, notes });
  return data;
}

/**
 * Delete a KYC application.
 * @param {string} kycId
 */
export async function deleteKycApplication(kycId) {
  const { data } = await api.delete(`/kyc/${kycId}`);
  return data;
}

/**
 * Upload a pre-filled application form for OCR extraction.
 * @param {string} kycId
 * @param {File} file
 * @param {(pct: number) => void} [onProgress]
 */
export async function uploadKycForm(kycId, file, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post(`/kyc/${kycId}/upload-form`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return data;
}

/**
 * Poll the OCR extraction status of the uploaded form.
 * @param {string} kycId
 */
export async function getKycFormStatus(kycId) {
  const { data } = await api.get(`/kyc/${kycId}/form-status`);
  return data;
}

/**
 * Upload a photo or signature image for the KYC application.
 * @param {string} kycId
 * @param {File} file
 * @param {'photo'|'signature'} attachmentType
 */
export async function uploadKycAttachment(kycId, file, attachmentType) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post(`/kyc/${kycId}/upload-attachment`, form, {
    params: { attachment_type: attachmentType },
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  });
  return data;
}

export default api;
