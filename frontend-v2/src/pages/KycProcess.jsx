import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield, Plus, Sparkles, User, FileText, Upload as UploadIcon, UploadCloud,
  CheckCircle, XCircle, AlertTriangle, Loader2, Trash2, Eye,
  ChevronRight, ChevronLeft, Edit3, ArrowRight, X, RefreshCw,
  CreditCard, Fingerprint, Calendar, MapPin, Users, Camera, PenTool, Image,
} from 'lucide-react';
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
  const [fFather, setFFather] = useState('');
  const [fDob, setFDob] = useState('');
  const [fAddress, setFAddress] = useState('');
  const [fFile, setFFile] = useState(null);
  const [fFormDragActive, setFFormDragActive] = useState(false);
  const [fPhoto, setFPhoto] = useState(null);
  const [fPhotoPreview, setFPhotoPreview] = useState(null);
  const [fSignature, setFSignature] = useState(null);
  const [fSignaturePreview, setFSignaturePreview] = useState(null);
  const [formExtractStatus, setFormExtractStatus] = useState(null); // null | 'uploading' | 'processing' | 'completed' | 'failed'
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  /* ── Upload ID doc state (Step 3) ── */
  const [idDocType, setIdDocType] = useState('passport');
  const [idFile, setIdFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [extractionStatus, setExtractionStatus] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  /* ── Result state (Step 4) ── */
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);

  const fileInputRef = useRef(null);
  const photoInputRef = useRef(null);
  const signatureInputRef = useRef(null);
  const idFileInputRef = useRef(null);
  const pollRef = useRef(null);
  const formPollRef = useRef(null);

  /* ── Load applications ── */
  const loadApps = useCallback(async () => {
    try {
      setLoadError('');
      const data = await listKycApplications();
      setApplications(Array.isArray(data) ? data : []);
    } catch (e) {
      setLoadError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadApps(); }, [loadApps]);

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
    setFName(''); setFFather(''); setFDob(''); setFAddress('');
    setFFile(null); setFFormDragActive(false);
    setFPhoto(null); setFPhotoPreview(null);
    setFSignature(null); setFSignaturePreview(null);
    setFormExtractStatus(null);
    setSubmitting(false); setSubmitError('');
    setIdDocType('passport'); setIdFile(null);
    setUploading(false); setUploadProgress(0); setExtractionStatus(null);
    setVerifying(false); setVerifyResult(null);
    setDragActive(false);
    clearInterval(formPollRef.current);
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
        fathers_name: fFather.trim() || undefined,
        date_of_birth: fDob.trim() || undefined,
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

      // 3. If upload mode, send the form through OCR pipeline
      if (formMode === 'upload' && fFile) {
        setFormExtractStatus('uploading');
        await uploadKycForm(kycId, fFile);
        setFormExtractStatus('processing');

        // Poll for extraction completion
        const pollForm = async () => {
          try {
            const status = await getKycFormStatus(kycId);
            if (status.status === 'completed') {
              clearInterval(formPollRef.current);
              setFormExtractStatus('completed');
              // Populate form fields from extraction
              if (status.populated) {
                setFName(status.populated.applicant_name || '');
                setFFather(status.populated.fathers_name || '');
                setFDob(status.populated.date_of_birth || '');
                setFAddress(status.populated.address || '');
                // Attempt to fetch extracted images via backend URL
                if (status.populated.photo_url) {
                  // Prepend backend URL logic if needed, but relative URL should work with proxy
                  setFPhotoPreview(status.populated.photo_url);
                }
                if (status.populated.signature_url) {
                  setFSignaturePreview(status.populated.signature_url);
                }
              }
              await loadApps();
              setSubmitting(false);
              setWizardStep(1); // Move to Review with extracted data
            } else if (status.status === 'failed') {
              clearInterval(formPollRef.current);
              setFormExtractStatus('failed');
              setSubmitError('Form extraction failed. You can try again or switch to manual entry.');
              setSubmitting(false);
            }
            // otherwise keep polling (status is 'pending', 'processing', etc.)
          } catch { /* ignore poll errors */ }
        };
        pollForm();
        formPollRef.current = setInterval(pollForm, 3000);
        return; // Don't set submitting=false yet — wait for OCR
      }

      // Manual mode — go to review
      await loadApps();
      setWizardStep(1);
    } catch (e) {
      setSubmitError(e.message || 'Failed to create application');
    } finally {
      if (formMode === 'manual') setSubmitting(false);
    }
  }, [formMode, fName, fFather, fDob, fAddress, fFile, fPhoto, fSignature, loadApps]);

  /* ── Step 3: Upload ID document ── */
  const handleUploadIdDoc = useCallback(async () => {
    if (!idFile || !activeKycId) return;
    setUploading(true);
    setUploadProgress(0);
    try {
      await uploadKycDocument(activeKycId, idFile, idDocType, (pct) => setUploadProgress(pct));
      setUploadProgress(100);

      // Start polling extraction status
      const pollExtraction = async () => {
        try {
          const status = await getKycStatus(activeKycId);
          setExtractionStatus(status);
          if (status.ready_to_verify) {
            clearInterval(pollRef.current);
            await loadApps();
          } else if (status.failed_docs > 0) {
            clearInterval(pollRef.current);
          }
        } catch { /* ignore */ }
      };
      pollExtraction();
      pollRef.current = setInterval(pollExtraction, 3000);
    } catch (e) {
      setSubmitError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }, [idFile, activeKycId, idDocType, loadApps]);

  /* ── Step 4: Run verification ── */
  const handleVerify = useCallback(async () => {
    if (!activeKycId) return;
    setVerifying(true);
    try {
      const result = await runKycVerification(activeKycId);
      setVerifyResult(result);
      await loadApps();
    } catch (e) {
      setSubmitError(e.message || 'Verification failed');
    } finally {
      setVerifying(false);
    }
  }, [activeKycId, loadApps]);

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
  const handleResume = useCallback(async (app) => {
    setActiveKycId(app.kyc_id);
    setFName(app.applicant_name || '');
    setFFather(app.fathers_name || '');
    setFDob(app.date_of_birth || '');
    setFAddress(app.address || '');
    setWizardOpen(true);

    if (app.status === 'form_submitted') {
      setWizardStep(1); // Go to review
    } else if (app.status === 'ready' || app.status === 'doc_uploaded') {
      setWizardStep(2); // Upload ID doc step — also try to load status
      try {
        const status = await getKycStatus(app.kyc_id);
        setExtractionStatus(status);
      } catch { /* ignore */ }
    } else if (app.status === 'extracting') {
      setWizardStep(2);
      // Start polling
      const pollExtraction = async () => {
        try {
          const status = await getKycStatus(app.kyc_id);
          setExtractionStatus(status);
          if (status.ready_to_verify) {
            clearInterval(pollRef.current);
            await loadApps();
          }
        } catch { /* ignore */ }
      };
      pollExtraction();
      pollRef.current = setInterval(pollExtraction, 3000);
    } else if (['completed', 'verified', 'failed'].includes(app.status)) {
      handleViewResult(app.kyc_id);
    }
  }, [loadApps, handleViewResult]);

  /* ── Delete ── */
  const handleDelete = useCallback(async (kycId) => {
    if (!window.confirm('Delete this KYC application? This cannot be undone.')) return;
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
    if (e.dataTransfer.files?.[0]) setIdFile(e.dataTransfer.files[0]);
  }, []);

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
            <Shield size={12} /> KYC Verification
          </div>
          <div className="claim-page-title">
            KYC <span className="grad">Process</span>
          </div>
          <div className="claim-page-sub">
            Submit applicant details, upload identity documents, and run AI-powered verification.
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => { resetWizard(); setWizardOpen(true); }}>
          <Plus size={14} /> New KYC Application
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
            onClick={() => { resetWizard(); setWizardOpen(false); clearInterval(pollRef.current); }}
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
                Fill in the applicant's KYC details manually, or upload a pre-filled application form for automatic extraction.
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
                  {/* Row 1: Name + Father's Name */}
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
                        <Users size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                        Father's Name
                      </label>
                      <input
                        className="styled-input"
                        value={fFather}
                        onChange={e => setFFather(e.target.value)}
                        placeholder="e.g. Vijay Kumar Sharma"
                      />
                    </div>
                  </div>

                  {/* Row 2: DOB + (placeholder for future) */}
                  <div className="claim-form-grid" style={{ marginTop: 14 }}>
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
                    <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 2 }}>
                      <div className="claim-form-note" style={{ margin: 0, padding: '8px 12px', width: '100%' }}>
                        <strong>Tip:</strong> Dates in any format (DD/MM/YYYY, YYYY-MM-DD, etc.) are normalised during verification.
                      </div>
                    </div>
                  </div>

                  {/* Row 3: Address (full width) */}
                  <div style={{ marginTop: 14 }}>
                    <label className="claim-form-label">
                      <MapPin size={12} style={{ display: 'inline', verticalAlign: '-1px', marginRight: 4 }} />
                      Address
                    </label>
                    <textarea
                      className="styled-input"
                      rows={3}
                      value={fAddress}
                      onChange={e => setFAddress(e.target.value)}
                      placeholder="Full residential address — e.g. 42, MG Road, Sector 14, Gurugram, Haryana 122001"
                      style={{ minHeight: 80, resize: 'vertical', width: '100%', fontFamily: 'inherit' }}
                    />
                  </div>

                  {/* Row 4: Photo + Signature uploads */}
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
                    <strong>Note:</strong> The uploaded form will be processed through the document OCR pipeline. Extracted fields (Name, Father's Name, DOB, Address) will auto-populate the application.
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
                    ? (formExtractStatus === 'processing' ? 'Extracting from form…' : 'Creating…')
                    : (formMode === 'upload' ? 'Upload & Extract' : 'Create & Continue')
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
                Confirm the applicant's details before proceeding to document upload.
              </div>

              {/* KYC Card */}
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
                    <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>KYC Application · {activeKycId}</div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  {[
                    { label: 'Full Name', value: fName },
                    { label: "Father's Name", value: fFather },
                    { label: 'Date of Birth', value: fDob },
                    { label: 'Address', value: fAddress },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.06)' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                        {label}
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', wordBreak: 'break-word' }}>
                        {value || <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>Not provided</span>}
                      </div>
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

              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <button className="btn btn-ghost" onClick={() => setWizardStep(0)} style={{ gap: 6, display: 'flex', alignItems: 'center' }}>
                  <ChevronLeft size={14} /> Back
                </button>
                <button className="btn btn-primary" onClick={() => setWizardStep(2)} style={{ padding: '10px 28px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}>
                  <ArrowRight size={14} /> Upload ID Document
                </button>
              </div>
            </div>
          )}

          {/* ─── STEP 3: Upload Identity Document ─── */}
          {wizardStep === 2 && (
            <div style={{ animation: 'fadeIn 0.3s ease' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>
                Upload Identity Document
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 20 }}>
                Upload a Passport or Driving License for verification against the application data.
              </div>

              {/* Document type selection */}
              <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
                {[
                  { key: 'passport', icon: <CreditCard size={14} />, label: 'Passport' },
                  { key: 'driving_license', icon: <Fingerprint size={14} />, label: 'Driving License' },
                ].map(({ key, icon, label }) => (
                  <button
                    key={key}
                    className={`btn ${idDocType === key ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => setIdDocType(key)}
                    disabled={uploading || extractionStatus?.ready_to_verify}
                    style={{ flex: 1, padding: '10px 16px', fontSize: 13, gap: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >
                    {icon} {label}
                  </button>
                ))}
              </div>

              {/* Upload zone OR extraction status */}
              {!extractionStatus?.ready_to_verify ? (
                <>
                  <div
                    style={{
                      border: `2px dashed ${dragActive ? 'var(--accent)' : 'var(--border)'}`,
                      borderRadius: 12, padding: '36px 20px', textAlign: 'center',
                      background: dragActive ? 'rgba(79,110,247,0.05)' : 'var(--surface-sunken)',
                      cursor: uploading ? 'default' : 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                    onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => !uploading && idFileInputRef.current?.click()}
                  >
                    {uploading ? (
                      <>
                        <Loader2 size={32} className="spin" style={{ color: 'var(--accent)', marginBottom: 8 }} />
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Uploading & Extracting…</div>
                        <div style={{ width: '60%', height: 4, borderRadius: 2, background: 'var(--border)', margin: '10px auto 0', overflow: 'hidden' }}>
                          <div style={{ width: `${uploadProgress}%`, height: '100%', background: 'var(--accent)', borderRadius: 2, transition: 'width 0.3s ease' }} />
                        </div>
                      </>
                    ) : (
                      <>
                        <UploadCloud size={36} style={{ color: 'var(--accent)', marginBottom: 10 }} />
                        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                          {idFile ? idFile.name : 'Drop your document here or click to browse'}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                          PDF, PNG, JPG accepted · Will be processed through OCR pipeline
                        </div>
                      </>
                    )}
                    <input ref={idFileInputRef} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp" onChange={e => setIdFile(e.target.files?.[0] || null)} />
                  </div>

                  {/* Extraction progress for docs being processed */}
                  {extractionStatus && !extractionStatus.ready_to_verify && extractionStatus.total_docs > 0 && (
                    <div style={{ marginTop: 14, padding: '12px 16px', borderRadius: 8, background: 'var(--surface)', border: '1px solid var(--border)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                        <Loader2 size={13} className="spin" style={{ color: 'var(--info)' }} />
                        <span style={{ color: 'var(--text)' }}>
                          {extractionStatus.completed_docs < extractionStatus.total_docs
                            ? `Extracting document data… (${extractionStatus.completed_docs}/${extractionStatus.total_docs} complete)`
                            : 'Extracting photo & signature from the ID…'}
                        </span>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div style={{
                  padding: '16px 20px', borderRadius: 10,
                  background: 'var(--success-dim)', border: '1px solid var(--success-border)',
                  display: 'flex', alignItems: 'center', gap: 10,
                }}>
                  <CheckCircle size={18} style={{ color: 'var(--success)' }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--success)' }}>Document Extraction Complete</div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                      {extractionStatus.completed_docs} document(s) processed. Ready for verification.
                    </div>
                  </div>
                </div>
              )}

              {/* Photo / signature extracted from the ID */}
              {extractionStatus?.ready_to_verify && (extractionStatus.doc_statuses || []).map(ds => (
                <div key={ds.document_id} style={{ marginTop: 12, padding: '12px 16px', borderRadius: 10, background: 'var(--surface)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                    Extracted from {ds.doc_type === 'passport' ? 'Passport' : 'Driving License'}
                  </div>
                  <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end' }}>
                    <ExtractedImage label="Photo" url={ds.photo_url} kind="photo" />
                    <ExtractedImage label="Signature" url={ds.signature_url} kind="signature" />
                  </div>
                </div>
              ))}

              {submitError && (
                <div style={{ marginTop: 12, fontSize: 12, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={13} /> {submitError}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 20 }}>
                <button className="btn btn-ghost" onClick={() => setWizardStep(1)} style={{ gap: 6, display: 'flex', alignItems: 'center' }}>
                  <ChevronLeft size={14} /> Back
                </button>
                <div style={{ display: 'flex', gap: 10 }}>
                  {!extractionStatus?.ready_to_verify && idFile && !uploading && (
                    <button className="btn btn-primary" onClick={handleUploadIdDoc} style={{ padding: '10px 24px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}>
                      <UploadIcon size={14} /> Upload & Extract
                    </button>
                  )}
                  {extractionStatus?.ready_to_verify && (
                    <button className="btn btn-primary" onClick={() => setWizardStep(3)} style={{ padding: '10px 28px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}>
                      <ArrowRight size={14} /> Run Verification
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
                KYC Verification Result
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 20 }}>
                Cross-validation of form data against the uploaded identity document.
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
                    <Shield size={16} /> Run KYC Verification
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

                  {/* Done */}
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
                    <button
                      className="btn btn-primary"
                      onClick={() => { resetWizard(); setWizardOpen(false); }}
                      style={{ padding: '10px 28px', fontSize: 13, fontWeight: 600, gap: 6, display: 'flex', alignItems: 'center' }}
                    >
                      <CheckCircle size={14} /> Done
                    </button>
                  </div>
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
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>No KYC Applications</div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>Create a new application to start the KYC verification process.</div>
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
