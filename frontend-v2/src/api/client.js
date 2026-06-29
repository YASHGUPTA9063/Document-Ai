import axios from 'axios';

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
  const { data } = await api.get('/documents', { params: { page, limit } });
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
export async function updateExtractedData(documentId, validatedData) {
  const { data } = await api.put(`/documents/${documentId}/extracted`, { validated_data: validatedData });
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
 */
export async function resumeReview(workflowRunId, approved, corrections = null) {
  const { data } = await api.post(`/workflow/${workflowRunId}/resume/review`, {
    approved,
    corrections,
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
export async function generateTemplateFromSample(templateName, file, isKyc = false, kycBoxes = null) {
  const form = new FormData();
  form.append('file', file);
  const params = { template_name: templateName, is_kyc: isKyc };
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

export default api;

