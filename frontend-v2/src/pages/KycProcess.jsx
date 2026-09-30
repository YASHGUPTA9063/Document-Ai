import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Shield, Plus, Sparkles, User, FileText, Upload as UploadIcon, UploadCloud,
  CheckCircle, XCircle, AlertTriangle, Loader2, Trash2, Eye,
  ChevronRight, ChevronLeft, Edit3, ArrowRight, X, RefreshCw,
  Calendar, Camera, PenTool, Users, MapPin, Check,
} from 'lucide-react';
import { createPortal } from 'react-dom';
import { Modal } from '../components/ui/Modal';
import {
  createKycApplication, listKycApplications, getKycStatus,
  uploadKycDocument, runKycVerification, getKycResult,
  deleteKycApplication, updateKycForm,
  uploadKycForm, getKycFormStatus, uploadKycAttachment,
} from '../api/client';

/* ─── Helpers ─── */
function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return dateStr; }
}

function formatFileSize(bytes) {
  if (!bytes) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/* ─── Status config ─── */
const statusConfig = {
  form_submitted:  { label: 'Form Submitted',  icon: <FileText size={13} />,                cls: 'pending',    color: 'var(--muted)' },
  doc_uploaded:    { label: 'Doc Uploaded',     icon: <UploadIcon size={13} />,              cls: 'pending',    color: 'var(--info)' },
  extracting:      { label: 'Extracting…',      icon: <Loader2 size={13} className="spin" />, cls: 'processing', color: 'var(--info)' },
  ready:           { label: 'Ready to Verify',  icon: <CheckCircle size={13} />,             cls: 'approved',   color: 'var(--success)' },
  verifying:       { label: 'Verifying…',       icon: <Loader2 size={13} className="spin" />, cls: 'processing', color: 'var(--info)' },
  completed:       { label: 'Result Ready',     icon: <Eye size={13} />,                     cls: 'pending',    color: 'var(--accent)' },
  verified:        { label: 'Verified ✓',       icon: <CheckCircle size={13} />,             cls: 'approved',   color: 'var(--success)' },
  failed:          { label: 'Failed ✗',         icon: <XCircle size={13} />,                 cls: 'rejected',   color: 'var(--danger)' },
};

/* ─── Stepper ─── */
function Stepper({ steps, current }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 28 }}>
      {steps.map((step, i) => {
        const isActive = i === current;
        const isDone = i < current;
        const isLast = i === steps.length - 1;
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', flex: isLast ? 0 : 1 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              opacity: isActive ? 1 : isDone ? 0.85 : 0.4,
              transition: 'all 0.3s ease',
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 700,
                background: isDone ? 'var(--success)' : isActive ? 'var(--accent)' : 'var(--surface)',
                color: isDone || isActive ? '#fff' : 'var(--muted)',
                border: `2px solid ${isDone ? 'var(--success)' : isActive ? 'var(--accent)' : 'var(--border)'}`,
                transition: 'all 0.3s ease',
                boxShadow: isActive ? '0 0 12px rgba(79,110,247,0.3)' : 'none',
              }}>
                {isDone ? <CheckCircle size={15} /> : i + 1}
              </div>
              <div style={{ whiteSpace: 'nowrap' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: isActive ? 'var(--text)' : 'var(--muted)' }}>
                  {step.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>{step.desc}</div>
              </div>
            </div>
            {!isLast && (
              <div style={{
                flex: 1, height: 2, minWidth: 20, margin: '0 12px',
                background: isDone ? 'var(--success)' : 'var(--border)',
                borderRadius: 1, transition: 'background 0.3s ease',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Result Chip ─── */
function ResultChip({ result, score }) {
  const cfg = {
    MATCH:     { color: 'var(--success)', bg: 'var(--success-dim)', border: 'var(--success-border)', icon: '✓' },
    PARTIAL:   { color: 'var(--warn)',    bg: 'var(--warn-dim)',    border: 'var(--warn-border)',    icon: '~' },
    MISMATCH:  { color: 'var(--danger)',  bg: 'var(--danger-dim)',  border: 'var(--danger-border)',  icon: '✗' },
    NOT_FOUND: { color: 'var(--muted)',   bg: 'var(--surface)',     border: 'var(--border)',          icon: '?' },
    REVIEW:    { color: 'var(--warn)',    bg: 'var(--warn-dim)',    border: 'var(--warn-border)',    icon: '!' },
  }[result] || { color: 'var(--muted)', bg: 'var(--surface)', border: 'var(--border)', icon: '?' };

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700,
      color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`,
    }}>
      {cfg.icon} {result}
      {score != null && (
        <span style={{ fontWeight: 400, opacity: 0.85, marginLeft: 3 }}>
          {Math.round(score * 100)}%
        </span>
      )}
    </span>
  );
}


/* An ID document can be verified against once OCR and its photo/signature crop are done */
const isUsableIdDoc = (d) => d.status === 'completed' && d.images_status !== 'running';

/* Status line for a processed ID document */
function idDocStatus(d) {
  if (isUsableIdDoc(d)) return { label: 'Ready', color: 'var(--success)' };
  if (d.status === 'failed' || d.status === 'rejected') return { label: d.status === 'rejected' ? 'Rejected' : 'Failed', color: 'var(--danger)' };
  if (d.status === 'awaiting_review') return { label: 'Awaiting manual review', color: 'var(--warn)' };
  return { label: 'Processing…', color: 'var(--info)' };
}

/* The documents from the most recent upload — the ones the user picks from */
// Extra applicant details read off the form, shown and editable on the review step.
const DETAIL_FIELDS = [
  { key: 'gender', label: 'Gender' },
  { key: 'nationality', label: 'Nationality' },
  { key: 'passport_number', label: 'Passport Number' },
  { key: 'driving_license_number', label: 'Driving License Number' },
  { key: 'email', label: 'Email' },
  { key: 'contact_number', label: 'Contact Number' },
];
const EMPTY_DETAILS = Object.fromEntries(DETAIL_FIELDS.map(f => [f.key, '']));

const latestBatchDocs = (status) =>
  (status?.doc_statuses || []).filter(d => d.upload_batch === (status.latest_batch ?? null));

function ExtractedImage({ label, url, kind, size = 80 }) {
  return (
    <div style={{ textAlign: 'center' }}>
      {url ? (
        <img src={url} alt={label} style={kind === 'photo'
          ? { width: size, height: size, objectFit: 'cover', borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)' }
          : { maxHeight: size, maxWidth: size * 2, objectFit: 'contain', background: '#fff', borderRadius: 6, padding: 4, border: '1px solid rgba(0,0,0,0.1)' }} />
      ) : (
        <div style={{ fontSize: 11, color: 'var(--muted)', fontStyle: 'italic' }}>Not found</div>
      )}
      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>{label}</div>
    </div>
  );
}

/* ─── Main component ─── */
export function KycProcess() {
  const navigate = useNavigate();
  const location = useLocation();

  /* ── List state ── */
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  /* ── Wizard state ── */
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [activeKycId, setActiveKycId] = useState(null);

  /* ── Form state (Step 1) ── */
  const [formMode, setFormMode] = useState('manual'); // 'manual' | 'upload'
  const [fName, setFName] = useState('');
  const [fDob, setFDob] = useState('');
  const [fFather, setFFather] = useState('');
  const [fAddress, setFAddress] = useState('');
  const [fDetails, setFDetails] = useState(EMPTY_DETAILS);
  const [fFile, setFFile] = useState(null);
  const [fFormDragActive, setFFormDragActive] = useState(false);
  const [fPhoto, setFPhoto] = useState(null);
  const [fPhotoPreview, setFPhotoPreview] = useState(null);
  const [fSignature, setFSignature] = useState(null);
  const [fSignaturePreview, setFSignaturePreview] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  /* ── ID documents state (Step 3) ── */
  const [idQueue, setIdQueue] = useState([]);         // files added but not uploaded: { key, file }
  const [uploading, setUploading] = useState(false);
  const [uploadIndex, setUploadIndex] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [extractionStatus, setExtractionStatus] = useState(null);
  const [verifyDocId, setVerifyDocId] = useState(null); // the processed document chosen for the KYC check
  const [dragActive, setDragActive] = useState(false);

  /* ── Result state (Step 4) ── */
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [decision, setDecision] = useState(null); // 'approve' | 'disapprove' pending confirmation
  const [decisionDone, setDecisionDone] = useState(null); // confirmed decision, shown as a brief tick popup

  // Show the tick popup briefly, then close the wizard
  useEffect(() => {
    if (!decisionDone) return;
    const t = setTimeout(() => {
      setDecisionDone(null);
      resetWizard();
      setWizardOpen(false);
    }, 1800);
    return () => clearTimeout(t);
  }, [decisionDone]); // eslint-disable-line react-hooks/exhaustive-deps

  const fileInputRef = useRef(null);
  const photoInputRef = useRef(null);
  const signatureInputRef = useRef(null);
  const idFileInputRef = useRef(null);
  const pollRef = useRef(null);      // application list refresh

  /* ── Load applications ── */
  const loadApps = useCallback(async () => {
    try {
      setLoadError('');
      const data = await listKycApplications();
      const apps = Array.isArray(data) ? data : [];
      setApplications(apps);
      return apps;
    } catch (e) {
      setLoadError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  /* ── Poll for active applications ── */
  useEffect(() => {
    const ACTIVE = ['extracting', 'verifying'];
    const hasActive = applications.some(a => ACTIVE.includes(a.status));
    if (hasActive) {
      pollRef.current = setInterval(loadApps, 5000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [applications, loadApps]);

  /* ── Reset form ── */
  const resetWizard = useCallback(() => {
    setWizardStep(0);
    setActiveKycId(null);
    setFormMode('manual');
    setFName(''); setFDob(''); setFFather(''); setFAddress('');
    setFDetails(EMPTY_DETAILS);
    setFFile(null); setFFormDragActive(false);
    setFPhoto(null); setFPhotoPreview(null);
    setFSignature(null); setFSignaturePreview(null);
    setSubmitting(false); setSubmitError('');
    setIdQueue([]);
    setUploading(false); setUploadIndex(0); setUploadProgress(0);
    setExtractionStatus(null); setVerifyDocId(null);
    setVerifying(false); setVerifyResult(null);
    setDragActive(false);
  }, []);

  /* ── Hand uploads off to the Processing page; it returns here when they finish ── */
  const goToProcessing = useCallback((kycId, kind, documentIds) => {
    navigate('/processing', { state: { kyc: { kycId, kind, documentIds } } });
  }, [navigate]);

  /* ── Load processed ID documents and preselect one to verify against ── */
  const loadIdStatus = useCallback(async (kycId, preselect) => {
    try {
      const status = await getKycStatus(kycId);
      setExtractionStatus(status);
      const usable = latestBatchDocs(status).filter(isUsableIdDoc).map(d => d.document_id);
      // Prefer one of the documents just processed, else the most recent usable one.
      const fresh = usable.find(id => preselect?.includes(id));
      setVerifyDocId(fresh || usable.at(-1) || null);
    } catch { /* ignore */ }
  }, []);

  /* ── Handle photo/signature preview ── */
  const handlePhotoSelect = useCallback((file) => {
    if (!file) return;
    setFPhoto(file);
    const url = URL.createObjectURL(file);
    setFPhotoPreview(url);
  }, []);

  const handleSignatureSelect = useCallback((file) => {
    if (!file) return;
    setFSignature(file);
    const url = URL.createObjectURL(file);
    setFSignaturePreview(url);
  }, []);

  /* ── Step 1: Create KYC application ── */
  const handleCreateApplication = useCallback(async () => {
    if (formMode === 'manual' && !fName.trim()) return;
    if (formMode === 'upload' && !fFile) return;
    setSubmitting(true);
    setSubmitError('');
    try {
      // 1. Create the application record
      const data = await createKycApplication({
        applicant_name: fName.trim() || undefined,
        date_of_birth: fDob.trim() || undefined,
        fathers_name: fFather.trim() || undefined,
        address: fAddress.trim() || undefined,
        form_source: formMode,
      });
      const kycId = data.kyc_id;
      setActiveKycId(kycId);

      // 2. Upload photo & signature (if provided)
      if (fPhoto) {
        try { await uploadKycAttachment(kycId, fPhoto, 'photo'); } catch (e) { console.error('Photo upload failed:', e); }
      }
      if (fSignature) {
        try { await uploadKycAttachment(kycId, fSignature, 'signature'); } catch (e) { console.error('Signature upload failed:', e); }
      }

      // 3. If upload mode, send the form through the OCR pipeline and follow it
      //    on the Processing page — it brings the user back to review.
      if (formMode === 'upload' && fFile) {
        const res = await uploadKycForm(kycId, fFile);
        goToProcessing(kycId, 'form', [res.document_id]);
        return;
      }

      // Manual mode — go to review
      await loadApps();
      setWizardStep(1);
    } catch (e) {
      setSubmitError(e.message || 'Failed to create application');
    } finally {
      setSubmitting(false);
    }
  }, [formMode, fName, fDob, fFather, fAddress, fFile, fPhoto, fSignature, loadApps, goToProcessing]);

  /* ── Step 2: Save reviewed details — verification compares against these ── */
  const handleConfirmReview = useCallback(async () => {
    if (!activeKycId) return;
    setSubmitting(true);
    setSubmitError('');
    try {
      await updateKycForm(activeKycId, {
        applicant_name: fName.trim(),
        date_of_birth: fDob.trim(),
        fathers_name: fFather.trim(),
        address: fAddress.trim(),
        ...Object.fromEntries(DETAIL_FIELDS.map(({ key }) => [key, fDetails[key].trim()])),
      });
      await Promise.all([loadApps(), loadIdStatus(activeKycId)]);
      setWizardStep(2);
    } catch (e) {
      setSubmitError(e.message || 'Failed to save application details');
    } finally {
      setSubmitting(false);
    }
  }, [activeKycId, fName, fDob, fFather, fAddress, fDetails, loadApps, loadIdStatus]);

  /* ── Step 3: Queue ID documents ── */
  const addIdFiles = useCallback((files) => {
    const added = Array.from(files || []).map(file => ({
      key: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`,
      file,
    }));
    if (added.length) setIdQueue(q => [...q, ...added]);
  }, []);

  /* ── Step 3: Upload the added documents, then follow them on the Processing page ── */
  const handleUploadIdDocs = useCallback(async () => {
    const toUpload = idQueue;
    if (!toUpload.length || !activeKycId) return;
    setUploading(true);
    setSubmitError('');
    const documentIds = [];
    const uploadedKeys = [];
    let batch = null; // every file in this upload shares the batch the first one gets
    try {
      for (let i = 0; i < toUpload.length; i++) {
        setUploadIndex(i);
        setUploadProgress(0);
        const res = await uploadKycDocument(activeKycId, toUpload[i].file, batch, setUploadProgress);
        batch = res.upload_batch;
        documentIds.push(res.document_id);
        uploadedKeys.push(toUpload[i].key);
      }
      goToProcessing(activeKycId, 'id', documentIds);
    } catch (e) {
      // Drop what already went up so a retry doesn't upload it twice.
      setIdQueue(q => q.filter(item => !uploadedKeys.includes(item.key)));
      if (uploadedKeys.length) await loadIdStatus(activeKycId);
      setSubmitError(`${e.message || 'Upload failed'}${uploadedKeys.length ? ` — ${uploadedKeys.length} of ${toUpload.length} uploaded before the error.` : ''}`);
      setUploading(false);
    }
  }, [idQueue, activeKycId, goToProcessing, loadIdStatus]);

  /* ── Step 4: Run verification ── */
  const handleVerify = useCallback(async () => {
    if (!activeKycId) return;
    setVerifying(true);
    try {
      const result = await runKycVerification(activeKycId, verifyDocId ? [verifyDocId] : undefined);
      setVerifyResult(result);
      await loadApps();
    } catch (e) {
      setSubmitError(e.message || 'Verification failed');
    } finally {
      setVerifying(false);
    }
  }, [activeKycId, verifyDocId, loadApps]);

  /* ── View existing result ── */
  const handleViewResult = useCallback(async (kycId) => {
    setActiveKycId(kycId);
    setWizardOpen(true);
    setWizardStep(3);
    try {
      const result = await getKycResult(kycId);
      setVerifyResult(result);
    } catch {
      // No result yet
      setVerifyResult(null);
    }
  }, []);

  /* ── Resume wizard for existing application ── */
  const handleResume = useCallback(async (app, { documentIds, error } = {}) => {
    // Still being read by the pipeline → follow it on the Processing page.
    if (app.status === 'form_submitted' && app.form_source === 'uploaded') {
      try {
        const s = await getKycFormStatus(app.kyc_id);
        if (!['completed', 'failed', 'no_form', 'not_found'].includes(s.status)) {
          goToProcessing(app.kyc_id, 'form', app.form_document_id ? [app.form_document_id] : []);
          return;
        }
        // The list row may predate the extraction — prefer the freshly populated fields.
        if (s.status === 'completed' && s.populated) {
          app = {
            ...app,
            applicant_name: s.populated.applicant_name || app.applicant_name,
            date_of_birth: s.populated.date_of_birth || app.date_of_birth,
            fathers_name: s.populated.fathers_name || app.fathers_name,
            address: s.populated.address || app.address,
            ...Object.fromEntries(DETAIL_FIELDS.map(({ key }) => [key, s.populated[key] || app[key]])),
            photo_url: s.populated.photo_url || app.photo_url,
            signature_url: s.populated.signature_url || app.signature_url,
          };
        }
      } catch { /* fall through to review */ }
    }
    if (app.status === 'extracting') {
      try {
        const s = await getKycStatus(app.kyc_id);
        const pending = (s.doc_statuses || [])
          .filter(d => !['completed', 'failed', 'rejected'].includes(d.status) || d.images_status === 'running')
          .map(d => d.document_id);
        if (pending.length) {
          goToProcessing(app.kyc_id, 'id', pending);
          return;
        }
      } catch { /* fall through to the documents step */ }
    }

    resetWizard();
    setActiveKycId(app.kyc_id);
    setFName(app.applicant_name || '');
    setFDob(app.date_of_birth || '');
    setFFather(app.fathers_name || '');
    setFAddress(app.address || '');
    setFDetails(Object.fromEntries(DETAIL_FIELDS.map(({ key }) => [key, app[key] || ''])));
    setFPhotoPreview(app.photo_url || null);
    setFSignaturePreview(app.signature_url || null);
    setWizardOpen(true);
    if (error) setSubmitError(error);

    if (app.status === 'form_submitted') {
      setWizardStep(1); // Go to review
    } else if (['ready', 'doc_uploaded', 'extracting'].includes(app.status)) {
      setWizardStep(2); // ID documents step
      loadIdStatus(app.kyc_id, documentIds);
    } else if (['completed', 'verified', 'failed'].includes(app.status)) {
      handleViewResult(app.kyc_id);
    }
  }, [resetWizard, goToProcessing, loadIdStatus, handleViewResult]);

  /* ── Initial load; when returning from the Processing page (/kyc-process?kyc_id=…) resume that application ── */
  useEffect(() => {
    const kycId = new URLSearchParams(location.search).get('kyc_id');
    const { documentIds, formFailed } = location.state || {};
    if (kycId) navigate('/kyc-process', { replace: true });
    loadApps().then((apps) => {
      const app = kycId && apps?.find(a => a.kyc_id === kycId);
      if (!app) return;
      handleResume(app, {
        documentIds,
        error: formFailed ? 'Form extraction failed — enter the details manually below, or start over with a clearer copy.' : undefined,
      });
    });
    // Mount only — the query string is consumed (and cleared) on the first run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Delete ── */
  const handleDelete = useCallback(async (kycId) => {
    if (!window.confirm('Delete this customer? This cannot be undone.')) return;
    try {
      await deleteKycApplication(kycId);
      setApplications(prev => prev.filter(a => a.kyc_id !== kycId));
    } catch (e) {
      alert(`Failed to delete: ${e.message}`);
    }
  }, []);

  /* ── Drag & drop helpers ── */
  const handleDrag = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  }, []);
  const handleDrop = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    addIdFiles(e.dataTransfer.files);
  }, [addIdFiles]);

  /* ── ID documents ── */
  const processedIdDocs = latestBatchDocs(extractionStatus);
  const verifyDoc = processedIdDocs.find(d => d.document_id === verifyDocId);

  /* ── Stats ── */
  const totalCount = applications.length;
  const verifiedCount = applications.filter(a => a.status === 'verified').length;
  const pendingCount = applications.filter(a => !['verified', 'failed'].includes(a.status)).length;
  const failedCount = applications.filter(a => a.status === 'failed').length;

  const STEPS = [
    { label: 'Application', desc: 'Fill details' },
    { label: 'Review', desc: 'Confirm data' },
    { label: 'Upload ID', desc: 'Identity doc' },
    { label: 'Result', desc: 'Verification' },
  ];

  return (
    <div className="claim-page">
      {/* Header */}
      <div className="claim-page-header" style={{ marginBottom: 20 }}>
        <div>
          <div className="chip" style={{ marginBottom: 6 }}>
            <Shield size={12} /> Customer Verification
          </div>
          <div className="claim-page-title">
            Customer <span className="grad">Onboarding</span>
          </div>
          <div className="claim-page-sub">
            Submit applicant details, upload identity documents, and run AI-powered verification.
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => { resetWizard(); setWizardOpen(true); }}>
          <Plus size={14} /> New Customer
        </button>
      </div>

      {/* Stats */}
      <div className="claim-stats-grid anim-slide-in" style={{ marginBottom: 20 }}>
        <div className="claim-stat">
          <div className="claim-stat-icon accent"><Shield size={16} /></div>
          <div>
            <div className="claim-stat-value">{totalCount}</div>
            <div className="claim-stat-label">Total Applications</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon success"><CheckCircle size={16} /></div>
          <div>
            <div className="claim-stat-value">{verifiedCount}</div>
            <div className="claim-stat-label">Verified</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon info"><Loader2 size={16} /></div>
          <div>
            <div className="claim-stat-value">{pendingCount}</div>
            <div className="claim-stat-label">In Progress</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon warn"><AlertTriangle size={16} /></div>
          <div>
            <div className="claim-stat-value">{failedCount}</div>
            <div className="claim-stat-label">Failed</div>
          </div>
        </div>
      </div>

      {/* Wizard */}
      {wizardOpen && (
        <div className="card" style={{ marginBottom: 24, position: 'relative', overflow: 'visible' }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => { resetWizard(); setWizardOpen(false); }}
            style={{ position: 'absolute', top: 12, right: 12, padding: 4 }}
            title="Close"
          >
            <X size={14} />
          </button>

          <Stepper steps={STEPS} current={wizardStep} />

          {/* ─── STEP 1: Application Form ─── */}
          {wizardStep === 0 && (
            <div style={{ animation: 'fadeIn 0.3s ease' }}>
              <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>
                Applicant Details
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-dim)', marginBottom: 20 }}>
                Fill in the customer's details manually, or upload a pre-filled application form for automatic extraction.
              </div>

              {/* Mode toggle — styled like claim priority selector */}
              <div style={{ marginBottom: 18 }}>
                <label className="claim-form-label">Input Method</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[
                    { key: 'manual', icon: <Edit3 size={14} />, label: 'Fill Manually', sub: 'Enter details by hand' },
                    { key: 'upload', icon: <UploadIcon size={14} />, label: 'Upload Form', sub: 'Extract from document' },
                  ].map(({ key, icon, label, sub }) => (
                    <button
                      key={key}
                      className={`btn ${formMode === key ? 'btn-primary' : 'btn-outline'}`}
                      onClick={() => setFormMode(key)}
                      style={{
                        flex: 1, padding: '12px 16px', fontSize: 13, gap: 8,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexDirection: 'column', minHeight: 60,
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>{icon} {label}</span>
                      <span style={{ fontSize: 10, opacity: 0.7, fontWeight: 400 }}>{sub}</span>
                    </button>
                  ))}
                </div>
              </div>

              {formMode === 'manual' ? (
                <>
                  {/* Row 1: Name + DOB */}
                  <div className="claim-form-grid">
                    <div>
                      <label className="claim-form-label">
                        <User size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                        Full Name <span className="required">*</span>
                      </label>
                      <input
                        className="styled-input"
                        value={fName}
                        onChange={e => setFName(e.target.value)}
                        placeholder="e.g. Rahul Sharma"
                      />
                    </div>
                    <div>
                      <label className="claim-form-label">
                        <Calendar size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                        Date of Birth
                      </label>
                      <input
                        className="styled-input"
                        value={fDob}
                        onChange={e => setFDob(e.target.value)}
                        placeholder="DD-MM-YYYY (e.g. 15-03-1995)"
                      />
                    </div>
                    <div>
                      <label className="claim-form-label">
                        <Users size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                        Father's Name
                      </label>
                      <input
                        className="styled-input"
                        value={fFather}
                        onChange={e => setFFather(e.target.value)}
                        placeholder="e.g. Suresh Sharma"
                      />
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <label className="claim-form-label">
                        <MapPin size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                        Address
                      </label>
                      <textarea
                        className="styled-input"
                        value={fAddress}
                        onChange={e => setFAddress(e.target.value)}
                        placeholder="House / street, locality, city, state, PIN"
                        rows={2}
                        style={{ resize: 'vertical', fontFamily: 'inherit' }}
                      />
                    </div>
                  </div>
                  <div className="claim-form-note" style={{ marginTop: 10, padding: '8px 12px' }}>
                    <strong>Tip:</strong> Dates in any format (DD/MM/YYYY, YYYY-MM-DD, etc.) are normalised during verification.
                  </div>

                  {/* Row 2: Photo + Signature uploads */}
                  <div className="claim-form-grid" style={{ marginTop: 18 }}>
                    {/* Photo */}
                    <div>
                      <label className="claim-form-label">
                        <Camera size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                        Applicant Photo
                      </label>
                      <div
                        onClick={() => photoInputRef.current?.click()}
                        style={{
                          border: '2px dashed var(--border)', borderRadius: 'var(--radius-sm)',
                          padding: fPhotoPreview ? 8 : '24px 16px',
                          textAlign: 'center', cursor: 'pointer',
                          background: 'var(--card-alt)', transition: 'all 0.2s ease',
                          minHeight: 120, display: 'flex', flexDirection: 'column',
                          alignItems: 'center', justifyContent: 'center', gap: 8,
                          position: 'relative', overflow: 'hidden',
                        }}
                      >
                        {fPhotoPreview ? (
                          <>
                            <img src={fPhotoPreview} alt="Photo" style={{
                              maxWidth: '100%', maxHeight: 120, borderRadius: 6, objectFit: 'cover',
                            }} />
                            <div style={{ fontSize: 11, color: 'var(--muted)' }}>{fPhoto?.name}</div>
                            <button
                              className="btn btn-ghost btn-icon btn-sm"
                              onClick={(e) => { e.stopPropagation(); setFPhoto(null); setFPhotoPreview(null); }}
                              style={{ position: 'absolute', top: 4, right: 4 }}
                            >
                              <X size={12} />
                            </button>
                          </>
                        ) : (
                          <>
                            <Camera size={24} style={{ color: 'var(--muted)', opacity: 0.6 }} />
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Upload Photo</div>
                            <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>JPG, PNG, WEBP</div>
                          </>
                        )}
                        <input
                          ref={photoInputRef}
                          type="file"
                          style={{ display: 'none' }}
                          accept="image/*"
                          onChange={e => handlePhotoSelect(e.target.files?.[0])}
                        />
                      </div>
                    </div>

                    {/* Signature */}
                    <div>
                      <label className="claim-form-label">
                        <PenTool size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                        Applicant Signature
                      </label>
                      <div
                        onClick={() => signatureInputRef.current?.click()}
                        style={{
                          border: '2px dashed var(--border)', borderRadius: 'var(--radius-sm)',
                          padding: fSignaturePreview ? 8 : '24px 16px',
                          textAlign: 'center', cursor: 'pointer',
                          background: 'var(--card-alt)', transition: 'all 0.2s ease',
                          minHeight: 120, display: 'flex', flexDirection: 'column',
                          alignItems: 'center', justifyContent: 'center', gap: 8,
                          position: 'relative', overflow: 'hidden',
                        }}
                      >
                        {fSignaturePreview ? (
                          <>
                            <img src={fSignaturePreview} alt="Signature" style={{
                              maxWidth: '100%', maxHeight: 120, borderRadius: 6, objectFit: 'contain',
                              background: '#fff', padding: 4,
                            }} />
                            <div style={{ fontSize: 11, color: 'var(--muted)' }}>{fSignature?.name}</div>
                            <button
                              className="btn btn-ghost btn-icon btn-sm"
                              onClick={(e) => { e.stopPropagation(); setFSignature(null); setFSignaturePreview(null); }}
                              style={{ position: 'absolute', top: 4, right: 4 }}
                            >
                              <X size={12} />
                            </button>
                          </>
                        ) : (
                          <>
                            <PenTool size={24} style={{ color: 'var(--muted)', opacity: 0.6 }} />
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Upload Signature</div>
                            <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>JPG, PNG, WEBP</div>
                          </>
                        )}
                        <input
                          ref={signatureInputRef}
                          type="file"
                          style={{ display: 'none' }}
                          accept="image/*"
                          onChange={e => handleSignatureSelect(e.target.files?.[0])}
                        />
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                /* Upload form — uses the same bulk-upload-zone from claims */
                <div style={{ marginTop: 4 }}>
                  <label className="claim-form-label" style={{ marginBottom: 10, display: 'block' }}>
                    Application Form
                    <span style={{ fontWeight: 400, color: 'var(--muted)', marginLeft: 6 }}>(upload pre-filled form)</span>
                  </label>

                  <div
                    className={`bulk-upload-zone ${fFormDragActive ? 'drag-active' : ''}`}
                    onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); setFFormDragActive(true); }}
                    onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setFFormDragActive(true); }}
                    onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setFFormDragActive(false); }}
                    onDrop={(e) => {
                      e.preventDefault(); e.stopPropagation(); setFFormDragActive(false);
                      if (e.dataTransfer.files?.[0]) setFFile(e.dataTransfer.files[0]);
                    }}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <UploadCloud className="bulk-upload-icon" size={28} />
                    <div className="bulk-upload-title">
                      Drag & drop your form here or <span style={{ color: 'var(--accent)', textDecoration: 'underline' }}>browse</span>
                    </div>
                    <div className="bulk-upload-sub">Supports PDF, JPG, PNG up to 10MB</div>
                    <input
                      type="file"
                      ref={fileInputRef}
                      style={{ display: 'none' }}
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={e => setFFile(e.target.files?.[0] || null)}
                    />
                  </div>

                  {fFile && (
                    <div className="bulk-file-list">
                      <div className="bulk-file-item">
                        <div className="bulk-file-info">
                          <FileText size={14} color="var(--accent)" />
                          <span className="bulk-file-name" title={fFile.name}>{fFile.name}</span>
                          <span className="bulk-file-size">({formatFileSize(fFile.size)})</span>
                        </div>
                        <button
                          className="btn btn-ghost btn-icon btn-sm"
                          onClick={(e) => { e.stopPropagation(); setFFile(null); }}
                          title="Remove file"
                          type="button"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="claim-form-note" style={{ marginTop: 12 }}>
                    <strong>Note:</strong> After upload you'll be taken to the Processing page while the form runs through the OCR pipeline. When it's done you'll come back here to review the extracted name, date of birth, father's name, address, photo and signature.
                  </div>
                </div>
              )}

              {submitError && (
                <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--error-dim, rgba(220,38,38,0.1))', border: '1px solid var(--error, #dc2626)', borderRadius: 8, color: 'var(--error, #dc2626)', fontSize: 'var(--text-sm)' }}>
                  {submitError}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20, gap: 10 }}>
                <button
                  className="btn btn-ghost"
                  onClick={() => { resetWizard(); setWizardOpen(false); }}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleCreateApplication}
                  disabled={submitting || (formMode === 'manual' && !fName.trim()) || (formMode === 'upload' && !fFile)}
                >
                  {submitting ? <Loader2 size={14} className="spin" /> : <ArrowRight size={14} />}
                  {submitting
                    ? (formMode === 'upload' ? 'Uploading…' : 'Creating…')
                    : (formMode === 'upload' ? 'Upload & Process' : 'Create & Continue')
                  }
                </button>
              </div>
            </div>
          )}

          {/* ─── STEP 2: Review ─── */}
          {wizardStep === 1 && (
            <div style={{ animation: 'fadeIn 0.3s ease' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>
                Review Application Data
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 20 }}>
                Confirm the applicant's details before proceeding to document upload. These are the values the ID document is verified against — correct anything the extraction got wrong.
              </div>

              {/* Customer Card */}
              <div style={{
                background: 'linear-gradient(135deg, rgba(79,110,247,0.06) 0%, rgba(168,85,247,0.04) 100%)',
                border: '1px solid rgba(79,110,247,0.2)',
                borderRadius: 14, padding: 24, marginBottom: 20,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: '50%',
                    background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <User size={20} style={{ color: '#fff' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{fName || '—'}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>Customer · {activeKycId}</div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  {[
                    { label: 'Full Name', value: fName, set: setFName },
                    { label: 'Date of Birth', value: fDob, set: setFDob },
                    { label: "Father's Name", value: fFather, set: setFFather },
                    ...DETAIL_FIELDS.map(({ key, label }) => ({
                      label,
                      value: fDetails[key],
                      set: v => setFDetails(d => ({ ...d, [key]: v })),
                    })),
                    { label: 'Address', value: fAddress, set: setFAddress, wide: true },
                  ].map(({ label, value, set, wide }) => (
                    <div key={label} style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.06)', gridColumn: wide ? '1 / -1' : undefined }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                        {label}
                      </div>
                      {wide ? (
                        <textarea
                          className="styled-input"
                          value={value}
                          onChange={e => set(e.target.value)}
                          placeholder="Not provided"
                          rows={2}
                          style={{ fontSize: 14, fontWeight: 600, width: '100%', resize: 'vertical', fontFamily: 'inherit' }}
                        />
                      ) : (
                        <input
                          className="styled-input"
                          value={value}
                          onChange={e => set(e.target.value)}
                          placeholder="Not provided"
                          style={{ fontSize: 14, fontWeight: 600, width: '100%' }}
                        />
                      )}
                    </div>
                  ))}
                </div>

                {(fPhotoPreview || fSignaturePreview) && (
                  <div style={{ display: 'flex', gap: 16, marginTop: 16 }}>
                    {fPhotoPreview && (
                      <div style={{ padding: '10px', borderRadius: 8, background: 'rgba(0,0,0,0.06)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Applicant Photo</div>
                        <img src={fPhotoPreview} alt="Applicant" style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 6, border: '1px solid rgba(0,0,0,0.1)' }} />
                      </div>
                    )}
                    {fSignaturePreview && (
                      <div style={{ padding: '10px', borderRadius: 8, background: 'rgba(0,0,0,0.06)', display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Applicant Signature</div>
                        <img src={fSignaturePreview} alt="Signature" style={{ maxHeight: 80, maxWidth: '100%', objectFit: 'contain', background: '#fff', borderRadius: 6, padding: 4, border: '1px solid rgba(0,0,0,0.1)' }} />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {submitError && (
                <div style={{ marginBottom: 12, fontSize: 12, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={13} /> {submitError}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <button className="btn btn-ghost" onClick={() => setWizardStep(0)} style={{ gap: 6, display: 'flex', alignItems: 'center' }}>
                  <ChevronLeft size={14} /> Back
                </button>
                <button className="btn btn-primary" onClick={handleConfirmReview} disabled={submitting || !fName.trim()} style={{ padding: '10px 28px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}>
                  {submitting ? <Loader2 size={14} className="spin" /> : <ArrowRight size={14} />} Upload ID Document
                </button>
              </div>
            </div>
          )}

          {/* ─── STEP 3: Identity Documents ─── */}
          {wizardStep === 2 && (
            <div style={{ animation: 'fadeIn 0.3s ease' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>
                Identity Documents
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 20 }}>
                Upload one or more identity documents, then choose the one to use for customer verification.
              </div>

              {/* Documents already processed for this application */}
              {processedIdDocs.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <label className="claim-form-label" style={{ marginBottom: 8, display: 'block' }}>
                    Uploaded documents
                    <span style={{ fontWeight: 400, color: 'var(--muted)', marginLeft: 6 }}>(select the one to use for customer verification)</span>
                  </label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {processedIdDocs.map(ds => {
                      const usable = isUsableIdDoc(ds);
                      const checked = verifyDocId === ds.document_id;
                      const st = idDocStatus(ds);
                      return (
                        <label key={ds.document_id} style={{
                          display: 'flex', gap: 12, alignItems: 'flex-start',
                          padding: '12px 16px', borderRadius: 10,
                          background: 'var(--surface)',
                          border: `1px solid ${checked ? 'var(--accent)' : 'var(--border)'}`,
                          cursor: usable ? 'pointer' : 'default', opacity: usable ? 1 : 0.75,
                        }}>
                          <input
                            type="radio"
                            name="kyc-verify-doc"
                            checked={checked}
                            disabled={!usable}
                            onChange={() => setVerifyDocId(ds.document_id)}
                            style={{ marginTop: 3 }}
                          />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{ds.filename}</span>
                              <span style={{ fontSize: 11, fontWeight: 600, color: st.color }}>· {st.label}</span>
                            </div>
                            {usable && (
                              <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', marginTop: 10 }}>
                                <ExtractedImage label="Photo" url={ds.photo_url} kind="photo" size={64} />
                                <ExtractedImage label="Signature" url={ds.signature_url} kind="signature" size={64} />
                              </div>
                            )}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Add new documents */}
              <label className="claim-form-label" style={{ marginBottom: 8, display: 'block' }}>
                {processedIdDocs.length > 0 ? 'Upload a new set of documents' : 'Upload documents'}
              </label>
              <div
                className={`bulk-upload-zone ${dragActive ? 'drag-active' : ''}`}
                onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={() => !uploading && idFileInputRef.current?.click()}
              >
                <UploadCloud className="bulk-upload-icon" size={28} />
                <div className="bulk-upload-title">
                  Drag & drop documents here or <span style={{ color: 'var(--accent)', textDecoration: 'underline' }}>browse</span>
                </div>
                <div className="bulk-upload-sub">PDF, PNG, JPG accepted · add as many as you need</div>
                <input
                  ref={idFileInputRef}
                  type="file"
                  hidden
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp"
                  onChange={e => { addIdFiles(e.target.files); e.target.value = ''; }}
                />
              </div>

              {idQueue.length > 0 && (
                <div className="bulk-file-list">
                  {idQueue.map(item => (
                    <div key={item.key} className="bulk-file-item" style={{ gap: 10 }}>
                      <div className="bulk-file-info" style={{ flex: 1, minWidth: 0 }}>
                        <FileText size={14} color="var(--accent)" />
                        <span className="bulk-file-name" title={item.file.name}>{item.file.name}</span>
                        <span className="bulk-file-size">({formatFileSize(item.file.size)})</span>
                      </div>
                      <button
                        className="btn btn-ghost btn-icon btn-sm"
                        onClick={() => setIdQueue(q => q.filter(x => x.key !== item.key))}
                        disabled={uploading}
                        title="Remove file"
                        type="button"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {uploading && (
                <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Loader2 size={13} className="spin" />
                  Uploading {uploadIndex + 1} of {idQueue.length} · {uploadProgress}%
                </div>
              )}

              {submitError && (
                <div style={{ marginTop: 12, fontSize: 12, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={13} /> {submitError}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 20 }}>
                <button className="btn btn-ghost" onClick={() => setWizardStep(1)} disabled={uploading} style={{ gap: 6, display: 'flex', alignItems: 'center' }}>
                  <ChevronLeft size={14} /> Back
                </button>
                <div style={{ display: 'flex', gap: 10 }}>
                  {idQueue.length > 0 && (
                    <button className="btn btn-primary" onClick={handleUploadIdDocs} disabled={uploading} style={{ padding: '10px 24px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}>
                      {uploading ? <Loader2 size={14} className="spin" /> : <UploadIcon size={14} />}
                      Upload & Process {idQueue.length} {idQueue.length === 1 ? 'document' : 'documents'}
                    </button>
                  )}
                  {idQueue.length === 0 && verifyDoc && (
                    <button className="btn btn-primary" onClick={() => setWizardStep(3)} style={{ padding: '10px 28px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}>
                      <ArrowRight size={14} /> Verify with {verifyDoc.filename}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ─── STEP 4: Result ─── */}
          {wizardStep === 3 && (
            <div style={{ animation: 'fadeIn 0.3s ease' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>
                Customer Verification Result
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 20 }}>
                Cross-validation of form data against the selected identity document.
              </div>

              {!verifyResult && !verifying && (
                <div style={{ textAlign: 'center', padding: '30px 20px' }}>
                  <Shield size={40} style={{ color: 'var(--accent)', marginBottom: 12 }} />
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>Ready to Verify</div>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 20 }}>
                    Click below to cross-validate the applicant's form data against the extracted document data.
                  </div>
                  <button className="btn btn-primary" onClick={handleVerify} style={{
                    padding: '12px 36px', fontSize: 14, fontWeight: 700, gap: 8,
                    display: 'inline-flex', alignItems: 'center',
                    background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%)',
                    boxShadow: '0 4px 20px rgba(79,110,247,0.35)',
                    borderRadius: 10,
                  }}>
                    <Shield size={16} /> Run Customer Verification
                  </button>
                </div>
              )}

              {verifying && (
                <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                  <Loader2 size={36} className="spin" style={{ color: 'var(--accent)', marginBottom: 12 }} />
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>Verifying…</div>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>
                    Cross-validating form fields, photo and signature against the ID — this can take a minute or two
                  </div>
                </div>
              )}

              {verifyResult && (
                <div>
                  {/* Overall verdict */}
                  {(() => {
                    const ov = verifyResult.overall_status;
                    const cfg = {
                      VERIFIED: { color: '#10b981', bg: 'linear-gradient(135deg, rgba(16,185,129,0.12) 0%, rgba(16,185,129,0.04) 100%)', border: 'rgba(16,185,129,0.35)', icon: CheckCircle, label: 'VERIFIED', glow: 'rgba(16,185,129,0.25)' },
                      FAILED:   { color: '#ef4444', bg: 'linear-gradient(135deg, rgba(239,68,68,0.12) 0%, rgba(239,68,68,0.04) 100%)', border: 'rgba(239,68,68,0.35)', icon: XCircle, label: 'FAILED', glow: 'rgba(239,68,68,0.25)' },
                      REVIEW:   { color: '#f59e0b', bg: 'linear-gradient(135deg, rgba(245,158,11,0.12) 0%, rgba(245,158,11,0.04) 100%)', border: 'rgba(245,158,11,0.35)', icon: AlertTriangle, label: 'NEEDS REVIEW', glow: 'rgba(245,158,11,0.25)' },
                    }[ov] || { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.35)', icon: AlertTriangle, label: ov, glow: 'rgba(245,158,11,0.15)' };
                    const VIcon = cfg.icon;
                    return (
                      <div style={{
                        background: cfg.bg, border: `1.5px solid ${cfg.border}`, borderRadius: 14,
                        padding: '22px 26px', marginBottom: 20,
                        boxShadow: `0 0 30px ${cfg.glow}`,
                        animation: 'verdictReveal 0.5s ease-out',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                          <div style={{
                            width: 48, height: 48, borderRadius: '50%',
                            background: `${cfg.color}15`, border: `2px solid ${cfg.border}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}>
                            <VIcon size={24} style={{ color: cfg.color }} />
                          </div>
                          <div>
                            <div style={{ fontSize: 20, fontWeight: 800, color: cfg.color, letterSpacing: '0.03em' }}>
                              {cfg.label}
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                              Confidence: <strong style={{ color: 'var(--text)' }}>{verifyResult.confidence}%</strong>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Field-by-field comparison */}
                  <div style={{
                    background: 'var(--surface)', borderRadius: 10, padding: '14px 18px',
                    border: '1px solid var(--border)', marginBottom: 20,
                  }}>
                    <div style={{
                      display: 'grid', gridTemplateColumns: '100px 1fr 1fr auto',
                      gap: 10, marginBottom: 10, padding: '0 0 8px 0',
                      borderBottom: '1px solid var(--border)',
                    }}>
                      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Field</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Form Data</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Document Data</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Result</span>
                    </div>
                    {(verifyResult.field_checks || []).map((check, i) => (
                      <div key={i} style={{
                        display: 'grid', gridTemplateColumns: '100px 1fr 1fr auto',
                        gap: 10, alignItems: 'center', padding: '8px 0',
                        borderBottom: i < (verifyResult.field_checks || []).length - 1 ? '1px solid var(--border)' : 'none',
                      }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text)' }}>{check.field}</span>
                        {[['form_image_url', 'form_value'], ['doc_image_url', 'doc_value']].map(([urlKey, valKey]) => {
                          const kind = check.field === 'Applicant Photo' ? 'photo' : 'signature';
                          return (
                            <span key={valKey} style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                              {check[urlKey]
                                ? <ExtractedImage label={check[valKey]} url={check[urlKey]} kind={kind} size={56} />
                                : (check[valKey] || <em style={{ color: 'var(--muted)' }}>—</em>)}
                              {valKey === 'doc_value' && check.doc_source && (
                                <div style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'inherit', marginTop: 3 }}>
                                  from {check.doc_source}
                                </div>
                              )}
                            </span>
                          );
                        })}
                        <div style={{ textAlign: 'right' }}>
                          <ResultChip result={check.result} score={check.score} />
                          {check.verdict && (
                            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 3 }}>{check.verdict}</div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Summary */}
                  {verifyResult.summary && (
                    <div style={{
                      padding: '14px 18px', borderRadius: 10,
                      background: 'rgba(0,0,0,0.06)', border: '1px solid rgba(255,255,255,0.05)',
                      marginBottom: 20,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        <Sparkles size={11} /> Verification Summary
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7, whiteSpace: 'pre-line' }}>
                        {verifyResult.summary}
                      </div>
                    </div>
                  )}

                  {/* Approve / Disapprove */}
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
                    <button
                      className="btn btn-success"
                      onClick={() => setDecision('approve')}
                      style={{ padding: '10px 28px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}
                    >
                      <CheckCircle size={14} /> Approve
                    </button>
                    <button
                      className="btn btn-danger"
                      onClick={() => setDecision('disapprove')}
                      style={{ padding: '10px 28px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}
                    >
                      <XCircle size={14} /> Disapprove
                    </button>
                  </div>

                  {decision && (
                    <Modal
                      title={decision === 'approve' ? 'Approve KYC?' : 'Disapprove KYC?'}
                      onClose={() => setDecision(null)}
                      footer={
                        <>
                          <button className="btn btn-ghost" onClick={() => setDecision(null)}>Cancel</button>
                          <button
                            className={`btn ${decision === 'approve' ? 'btn-success' : 'btn-danger'}`}
                            onClick={() => { setDecisionDone(decision); setDecision(null); }}
                          >
                            {decision === 'approve' ? <CheckCircle size={14} /> : <XCircle size={14} />}
                            {decision === 'approve' ? 'Yes, Approve' : 'Yes, Disapprove'}
                          </button>
                        </>
                      }
                    >
                      <div style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                        Are you sure you want to {decision} this KYC application?
                      </div>
                    </Modal>
                  )}

                  {decisionDone && createPortal(
                    <div className="modal-overlay">
                      <div style={{
                        background: 'var(--card)', border: '1px solid var(--border-hi)',
                        borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow)',
                        padding: '24px 32px', textAlign: 'center',
                        animation: 'slide-in 200ms var(--ease)',
                      }}>
                        <div style={{
                          width: 52, height: 52, borderRadius: '50%', margin: '0 auto 12px',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: 'var(--success)', color: '#fff',
                        }}>
                          <Check size={28} strokeWidth={3} />
                        </div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                          KYC {decisionDone === 'approve' ? 'Approved' : 'Disapproved'}
                        </div>
                      </div>
                    </div>,
                    document.body,
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Application List */}
      {loading ? (
        <div className="card" style={{ textAlign: 'center', padding: '40px 20px' }}>
          <Loader2 size={28} className="spin" style={{ color: 'var(--accent)', margin: '0 auto 10px' }} />
          <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>Loading applications…</div>
        </div>
      ) : loadError ? (
        <div className="card" style={{ borderColor: 'var(--danger-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--danger)', fontSize: 13 }}>
            <AlertTriangle size={15} /> {loadError}
          </div>
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={loadApps}>
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      ) : applications.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '50px 20px' }}>
          <Shield size={40} style={{ color: 'var(--muted)', margin: '0 auto 12px', opacity: 0.3 }} />
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>No Customers</div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>Add a new customer to start the onboarding process.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {applications.map(app => {
            const sc = statusConfig[app.status] || statusConfig.form_submitted;
            return (
              <div
                key={app.kyc_id}
                className="claim-card"
                style={{ cursor: 'pointer' }}
                onClick={() => handleResume(app)}
              >
                <div className="claim-card-main">
                  <div className="claim-card-left">
                    <div className="claim-card-avatar" style={{ background: `${sc.color}15`, borderColor: sc.color }}>
                      <User size={16} style={{ color: sc.color }} />
                    </div>
                    <div className="claim-card-info">
                      <div className="claim-card-name-row">
                        <span className="claim-card-name">{app.applicant_name || 'Unnamed'}</span>
                        <span className="claim-card-id">{app.kyc_id}</span>
                      </div>
                      <div className="claim-card-meta">
                        <span>{app.form_source === 'uploaded' ? '📄 Uploaded' : '✏️ Manual'}</span>
                        <span>·</span>
                        <span>{formatDate(app.created_at)}</span>
                        {app.date_of_birth && (
                          <>
                            <span>·</span>
                            <span>DOB: {app.date_of_birth}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="claim-card-right">
                    <div className={`claim-card-status ${sc.cls}`}>
                      {sc.icon} <span>{sc.label}</span>
                    </div>
                    <div className="claim-card-actions" onClick={e => e.stopPropagation()}>
                      {['completed', 'verified', 'failed'].includes(app.status) && (
                        <button className="btn btn-ghost btn-sm" onClick={() => handleViewResult(app.kyc_id)} title="View Result">
                          <Eye size={13} />
                        </button>
                      )}
                      <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(app.kyc_id)} title="Delete" style={{ color: 'var(--danger)' }}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Style injection */}
      <style>{`
        @keyframes fadeIn {
          0% { opacity: 0; transform: translateY(8px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        @keyframes verdictReveal {
          0% { opacity: 0; transform: translateY(20px) scale(0.97); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  );
}
