import axios from 'axios';

// Relative by default — nginx (Docker) and the Vite dev server both proxy
// /api to the backend, so no hostname is baked into the bundle.
const BASE = import.meta.env.VITE_API_BASE_URL || '/api';

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
 * @returns {Promise<{document_id, filename, status, message, workflow_run_id}>}
 */
export async function uploadDocument(file, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/upload', form, {
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
 * @returns {Promise<{ total, succeeded, failed, results: Array }>}
 */
export async function uploadDocumentsBatch(files, onProgress) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const { data } = await api.post('/upload/batch', form, {
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
  const { data } = await api.get(`/status/${documentId}`);
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
 * Get OCR bounding box blocks for field citation highlighting.
 * Only available for image documents (PNG/JPEG/WEBP) processed after this feature was added.
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
  const { data } = await api.post('/upload', form, {
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

export default api;

