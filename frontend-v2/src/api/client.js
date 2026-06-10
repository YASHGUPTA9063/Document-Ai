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

export default api;

