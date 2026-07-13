import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ClipboardList, FileSearch, Plus, Sparkles, TrendingUp, Clock,
  AlertTriangle, CheckCircle, User, Trash2, ChevronDown, ChevronUp,
  Play, Loader2, FileText, ShieldCheck, ShieldOff, X, Upload, UploadCloud,
} from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { CLAIM_TYPES, PRIORITY_OPTIONS } from './claimData';
import {
  createClaim, listClaims, getClaimStatus, runClaimWorkflow, uploadClaimDocument, deleteClaim,
} from '../api/client';

/* ─── Helpers ─── */
function formatCurrency(amount) {
  if (!amount) return '—';
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
}
function formatCompactCurrency(amount) {
  if (!amount) return '₹0';
  if (amount >= 1_000_000) return `₹${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `₹${(amount / 1_000).toFixed(0)}K`;
  return `₹${amount}`;
}
function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* ─── Status config ─── */
const statusConfig = {
  creating:   { label: 'Creating Request…', icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  extracting: { label: 'Extracting Docs…',  icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  ready:      { label: 'Ready to Process',  icon: <CheckCircle size={14} />,              cls: 'approved'   },
  processing: { label: 'Processing…',       icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_integrity: { label: 'Processing… (Integrity)', icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_medical:   { label: 'Processing… (Medical)',   icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_treatment: { label: 'Processing… (Treatment)', icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_disability:{ label: 'Processing… (Disability)',icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  checking_litigation:{ label: 'Processing… (Litigation)',icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  generating_report:  { label: 'Processing… (Report)',    icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  completed:  { label: 'Report Ready',      icon: <FileText size={14} />,                 cls: 'pending'    },
  approved:   { label: 'Approved',          icon: <ShieldCheck size={14} />,              cls: 'approved'   },
  rejected:   { label: 'Rejected',          icon: <X size={14} />,                        cls: 'rejected'   },
  failed:     { label: 'Failed',            icon: <AlertTriangle size={14} />,            cls: 'missing'    },
};

const borderMap = {
  ready:      'border-success',
  processing: 'border-info',
  failed:     'border-warn',
};



/* ─── Main component ─── */
export function ClaimProcess() {
  const navigate = useNavigate();
  const [claims, setClaims]       = useState([]);
  const [loading, setLoading]     = useState(true);
  const [loadError, setLoadError] = useState('');
  const [expandedId, setExpanded] = useState(null);
  const [dialogOpen, setDialog]   = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [deletingId, setDeletingId] = useState(null);

  /* Form state */
  const [fName, setFName]         = useState('');
  const [fPriority, setFPriority] = useState('medium');
  const [fDesc, setFDesc]         = useState('');
  const [fFiles, setFFiles]       = useState([]);
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef(null);

  /* Per-claim doc status cache for expanded card */
  const [docStatuses, setDocStatuses] = useState({});

  const pollRef = useRef(null);

  /* ── Load claims from API ─────────────────────────────────────── */
  const loadClaims = useCallback(async () => {
    try {
      setLoadError('');
      const data = await listClaims();
      setClaims(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to load claims:', e);
      setLoadError(e.message || 'Failed to load claims');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClaims();
  }, [loadClaims]);

  /* ── Poll active claims every 6s ─────────────────────────────── */
  useEffect(() => {
    const ACTIVE = ['creating', 'extracting', 'processing'];
    const hasActive = claims.some(c => ACTIVE.includes(c.status));
    if (hasActive) {
      pollRef.current = setInterval(loadClaims, 6000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [claims, loadClaims]);

  /* ── Fetch doc statuses for expanded claim ───────────────────── */
  useEffect(() => {
    if (!expandedId) return;
    const fetchDocStatus = async () => {
      try {
        const data = await getClaimStatus(expandedId);
        setDocStatuses(prev => ({ ...prev, [expandedId]: data }));
      } catch (e) {
        console.error('Failed to fetch doc status:', e);
      }
    };
    fetchDocStatus();
    const interval = setInterval(fetchDocStatus, 5000);
    return () => clearInterval(interval);
  }, [expandedId]);

  const resetForm = useCallback(() => {
    setFName(''); setFPriority('medium');
    setFDesc(''); setFFiles([]);
    setSubmitError('');
  }, []);

  const handleToggle = useCallback((id) => setExpanded(prev => prev === id ? null : id), []);

  /* ── Process: trigger workflow ───────────────────────────────── */
  const handleProcess = useCallback(async (claimId) => {
    try {
      await runClaimWorkflow(claimId);
      navigate(`/claim-workflow?claim_id=${claimId}`);
    } catch (e) {
      alert(`Failed to start workflow: ${e.message}`);
    }
  }, [navigate]);

  /* ── View report (already completed) ────────────────────────── */
  const handleViewReport = useCallback((claimId) => {
    navigate(`/claim-workflow?claim_id=${claimId}&view_report=1`);
  }, [navigate]);

  /* ── Delete claim ─────────────────────────────────────────────── */
  const handleDelete = useCallback(async (claimId, claimantName) => {
    if (!window.confirm(`Delete claim for "${claimantName}"? This cannot be undone.`)) return;
    setDeletingId(claimId);
    try {
      await deleteClaim(claimId);
      setClaims(prev => prev.filter(c => c.claim_id !== claimId));
      if (expandedId === claimId) setExpanded(null);
    } catch (e) {
      alert(`Failed to delete claim: ${e.message}`);
    } finally {
      setDeletingId(null);
    }
  }, [expandedId]);

  /* ── Bulk file upload helpers ─────────────────────────────────── */
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFFiles(prev => [...prev, ...newFiles]);
    }
  }, []);

  const handleFileSelect = useCallback((e) => {
    if (e.target.files && e.target.files[0]) {
      const newFiles = Array.from(e.target.files);
      setFFiles(prev => [...prev, ...newFiles]);
    }
  }, []);

  const removeFile = useCallback((idxToRemove) => {
    setFFiles(prev => prev.filter((_, i) => i !== idxToRemove));
  }, []);

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  /* ── Create claim + upload docs ──────────────────────────────── */
  const handleCreate = useCallback(async () => {
    if (!fName.trim() || fFiles.length === 0) return;
    setSubmitting(true);
    setSubmitError('');

    try {
      // 1. Create claim record
      const claimData = await createClaim({
        claimant_name: fName.trim(),
        claim_type: 'unknown',
        policy_number: 'unknown',
        description: fDesc.trim() || undefined,
        priority: fPriority,
        amount: 0,
      });

      const claimId = claimData.claim_id;

      // 2. Upload each doc sequentially
      for (const file of fFiles) {
        try {
          await uploadClaimDocument(claimId, file, undefined);
        } catch (uploadErr) {
          console.error(`Failed to upload ${file.name}:`, uploadErr);
        }
      }

      // 3. Refresh list and close modal
      await loadClaims();
      resetForm();
      setDialog(false);
    } catch (e) {
      setSubmitError(e.message || 'Failed to create claim. Check backend connection.');
    } finally {
      setSubmitting(false);
    }
  }, [fName, fDesc, fPriority, fFiles, loadClaims, resetForm]);

  const isFormValid = fName.trim() && fFiles.length > 0;

  /* ── Stats ────────────────────────────────────────────────────── */
  const pendingCount  = claims.filter(c => ['creating', 'extracting', 'ready'].includes(c.status)).length;
  const activeCount   = claims.filter(c => c.status === 'processing').length;
  const totalAmount   = claims.reduce((s, c) => s + (c.amount || 0), 0);

  return (
    <div className="claim-page">
      {/* Header */}
      <div className="claim-page-header" style={{ marginBottom: 20 }}>
        <div>
          <div className="chip" style={{ marginBottom: 6 }}>
            <Sparkles size={12} /> Claims Dashboard
          </div>
          <div className="claim-page-title">
            Claim Approval <span className="grad">Requests</span>
          </div>
          <div className="claim-page-sub">
            Create a claim, upload documents, and run the AI validation pipeline.
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setDialog(true)}>
          <Plus size={14} /> Create New Request
        </button>
      </div>

      {/* Stats */}
      <div className="claim-stats-grid anim-slide-in" style={{ marginBottom: 20 }}>
        <div className="claim-stat">
          <div className="claim-stat-icon accent"><ClipboardList size={16} /></div>
          <div>
            <div className="claim-stat-value">{claims.length}</div>
            <div className="claim-stat-label">Total Claims</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon info"><Clock size={16} /></div>
          <div>
            <div className="claim-stat-value">{pendingCount}</div>
            <div className="claim-stat-label">Pending / Ready</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon warn"><AlertTriangle size={16} /></div>
          <div>
            <div className="claim-stat-value">{activeCount}</div>
            <div className="claim-stat-label">Processing</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon success"><TrendingUp size={16} /></div>
          <div>
            <div className="claim-stat-value">{formatCompactCurrency(totalAmount)}</div>
            <div className="claim-stat-label">Total Value</div>
          </div>
        </div>
      </div>

      {/* List header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <FileSearch size={14} color="var(--muted)" />
        <span style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>
          All Requests ({claims.length})
        </span>
      </div>

      {/* Claim list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {loading ? (
          <div className="card-glass" style={{ textAlign: 'center', padding: '56px 24px' }}>
            <Loader2 size={24} className="spin" style={{ margin: '0 auto 12px', display: 'block', color: 'var(--accent)' }} />
            <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>Loading claims…</div>
          </div>
        ) : loadError ? (
          <div className="card-glass" style={{ textAlign: 'center', padding: '56px 24px' }}>
            <AlertTriangle size={24} style={{ margin: '0 auto 12px', display: 'block', color: 'var(--warn)' }} />
            <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>{loadError}</div>
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 12 }} onClick={loadClaims}>Retry</button>
          </div>
        ) : claims.length === 0 ? (
          <div className="card-glass" style={{ textAlign: 'center', padding: '56px 24px' }}>
            <div className="empty-icon-wrap"><ClipboardList size={24} /></div>
            <div className="empty-title">No claim requests</div>
            <div className="empty-sub">Click "Create New Request" to add your first claim.</div>
          </div>
        ) : (
          claims.map((claim, i) => {
            const status   = statusConfig[claim.status] || statusConfig.failed;
            const border   = borderMap[claim.status] || '';
            const expanded = expandedId === claim.id || expandedId === claim.claim_id;
            const cid      = claim.claim_id;
            const docStatus = docStatuses[cid];

            return (
              <div
                key={cid}
                className={`claim-card ${border} anim-slide-in`}
                style={{ animationDelay: `${i * 40}ms` }}
              >
                {/* Main row */}
                <div className="claim-card-main">
                  <div className="claim-card-left">
                    <div className="claim-card-avatar"><User size={18} /></div>
                    <div className="claim-card-info">
                      <div className="claim-card-name-row">
                        <span className="claim-card-name">{claim.claimant_name}</span>
                        <span className="claim-card-id">{cid}</span>
                        {claim.priority && (
                          <span className={`priority-badge ${claim.priority}`}>
                            <span className="priority-dot" />
                            {claim.priority.charAt(0).toUpperCase() + claim.priority.slice(1)}
                          </span>
                        )}
                      </div>
                      <div className="claim-card-meta">
                        {claim.claim_type} · Policy {claim.policy_number} · {formatDate(claim.submitted_at)}
                      </div>
                      {claim.description && (
                        <div className="claim-card-desc">{claim.description}</div>
                      )}
                    </div>
                  </div>

                  <div className="claim-card-right">
                    <div className="claim-card-amount">
                      <div className="claim-card-amount-value">{formatCurrency(claim.amount)}</div>
                      <div className={`claim-card-status ${status.cls}`}>
                        {status.icon} {status.label}
                      </div>
                    </div>
                    <div className="claim-card-actions">
                      <button className="btn btn-ghost btn-icon btn-sm" title="Toggle" onClick={() => handleToggle(cid)}>
                        {(expandedId === cid) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>

                      {/* Delete button */}
                      <button
                        className="btn btn-ghost btn-icon btn-sm"
                        title="Delete claim"
                        disabled={deletingId === cid}
                        onClick={(e) => { e.stopPropagation(); handleDelete(cid, claim.claimant_name); }}
                        style={{ color: 'var(--error, #dc2626)' }}
                      >
                        {deletingId === cid ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
                      </button>

                      {/* Process button — only when ready */}
                      {claim.status === 'ready' && (
                        <button className="claim-btn-process" onClick={() => handleProcess(cid)}>
                          <Play size={14} /> Process
                        </button>
                      )}

                      {/* Spinner while extracting/creating/processing */}
                      {['creating', 'extracting', 'processing'].includes(claim.status) && (
                        <button className="btn btn-ghost btn-sm" disabled>
                          <Loader2 size={14} className="spin" />
                          {claim.status === 'processing' ? 'Processing' : 'Extracting'}
                        </button>
                      )}

                      {/* View report for completed/approved/rejected */}
                      {['completed', 'approved', 'rejected'].includes(claim.status) && (
                        <button className="claim-btn-process" style={{ background: 'var(--surface-2)', color: 'var(--text)' }} onClick={() => handleViewReport(cid)}>
                          <FileText size={14} /> View Report
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded doc panel */}
                {expandedId === cid && (
                  <div className="claim-card-expand">
                    <div className="claim-docs-grid">
                      <div>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 10 }}>
                          Documents {docStatus ? `(${docStatus.completed_docs}/${docStatus.total_docs} extracted)` : ''}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          {docStatus?.doc_statuses?.length > 0 ? docStatus.doc_statuses.map(doc => (
                            <div key={doc.document_id} className={`claim-doc-item ${doc.status === 'completed' ? 'present' : 'missing'}`}>
                              <FileText size={14} className="doc-status-icon" />
                              <span className="doc-name">{doc.filename} <span style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)' }}>({doc.doc_type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())})</span></span>
                              {doc.status === 'completed'
                                ? <CheckCircle size={14} className="doc-status-icon" />
                                : doc.status === 'failed'
                                ? <X size={14} className="doc-status-icon" style={{ color: 'var(--error)' }} />
                                : <Loader2 size={14} className="spin doc-status-icon" />
                              }
                            </div>
                          )) : (
                            <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>No documents uploaded yet.</div>
                          )}
                        </div>
                      </div>

                      {docStatus?.ready_to_process && (
                        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                          <div className="claim-docs-verified">
                            <ShieldCheck size={20} color="var(--success)" />
                            <div>
                              <div className="claim-docs-verified-title">All documents extracted</div>
                              <div className="claim-docs-verified-sub">Ready for AI claim processing</div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', fontSize: 'var(--text-sm)', color: 'var(--muted)', padding: '32px 0 16px' }}>
        Atlas · Document Intelligence · Claim Processing
      </div>

      {/* Create Dialog */}
      {dialogOpen && (
        <Modal
          title="Create New Claim Request"
          subtitle="Fill in claim details and upload all documents. Document classification is performed automatically during processing."
          onClose={() => { setDialog(false); resetForm(); }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => { setDialog(false); resetForm(); }} disabled={submitting}>Cancel</button>
              <button className="btn btn-primary" disabled={!isFormValid || submitting} onClick={handleCreate}>
                {submitting ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
                {submitting ? 'Creating…' : 'Create & Upload'}
              </button>
            </>
          }
        >
          {/* Claimant + Priority */}
          <div className="claim-form-grid">
            <div>
              <label className="claim-form-label">Claimant Name <span className="required">*</span></label>
              <input className="styled-input" placeholder="e.g. Priya S. Kapoor" value={fName} onChange={e => setFName(e.target.value)} />
            </div>
            <div>
              <label className="claim-form-label">Priority</label>
              <select className="styled-select" value={fPriority} onChange={e => setFPriority(e.target.value)}>
                {PRIORITY_OPTIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
          </div>

          {/* Description */}
          <div style={{ marginTop: 14 }}>
            <label className="claim-form-label">Description</label>
            <textarea 
              className="styled-input" 
              placeholder="Brief description of claim details, incident, or remarks…" 
              value={fDesc} 
              onChange={e => setFDesc(e.target.value)}
              style={{ minHeight: 80, resize: 'vertical', width: '100%', fontFamily: 'inherit' }}
            />
          </div>

          {/* Bulk Document upload section */}
          <div style={{ marginTop: 20 }}>
            <label className="claim-form-label" style={{ marginBottom: 10, display: 'block' }}>
              Documents <span className="required">*</span>
              <span style={{ fontWeight: 400, color: 'var(--muted)', marginLeft: 6 }}>(upload all files at once)</span>
            </label>
            
            <div 
              className={`bulk-upload-zone ${dragActive ? 'drag-active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud className="bulk-upload-icon" size={28} />
              <div className="bulk-upload-title">Drag & drop your files here or <span style={{ color: 'var(--accent)', textDecoration: 'underline' }}>browse</span></div>
              <div className="bulk-upload-sub">Supports PDF, JPG, PNG, WEBP, DOCX up to 10MB</div>
              <input 
                type="file" 
                ref={fileInputRef} 
                style={{ display: 'none' }} 
                multiple 
                onChange={handleFileSelect} 
                accept=".pdf,.jpg,.jpeg,.png,.webp,.docx" 
              />
            </div>

            {fFiles.length > 0 && (
              <div className="bulk-file-list">
                {fFiles.map((file, i) => (
                  <div key={i} className="bulk-file-item">
                    <div className="bulk-file-info">
                      <FileText size={14} color="var(--accent)" />
                      <span className="bulk-file-name" title={file.name}>{file.name}</span>
                      <span className="bulk-file-size">({formatFileSize(file.size)})</span>
                    </div>
                    <button 
                      className="btn btn-ghost btn-icon btn-sm" 
                      onClick={(e) => { e.stopPropagation(); removeFile(i); }} 
                      title="Remove file"
                      type="button"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {submitError && (
            <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--error-dim, rgba(220,38,38,0.1))', border: '1px solid var(--error, #dc2626)', borderRadius: 8, color: 'var(--error, #dc2626)', fontSize: 'var(--text-sm)' }}>
              {submitError}
            </div>
          )}

          <div className="claim-form-note" style={{ marginTop: 16 }}>
            <strong>Note:</strong> Documents are automatically classified (e.g. claim form, policy document, medical report) and synced during processing.
          </div>
        </Modal>
      )}
    </div>
  );
}
