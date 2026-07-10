import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ClipboardList, FileSearch, Plus, Sparkles, TrendingUp, Clock,
  AlertTriangle, CheckCircle, User, Trash2, ChevronDown, ChevronUp,
  Play, Loader2, FileText, ShieldCheck, ShieldOff, X,
} from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import {
  SAMPLE_CLAIMS, CLAIM_TYPES, PRIORITY_OPTIONS, DEFAULT_DOCUMENTS,
} from './claimData';

/* ─── Helpers ─── */
function formatCurrency(amount) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
}
function formatCompactCurrency(amount) {
  if (amount >= 1_000_000) return `₹${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `₹${(amount / 1_000).toFixed(0)}K`;
  return `₹${amount}`;
}
function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* ─── Status / Priority config ─── */
const statusConfig = {
  pending:      { label: 'Pending Review',    icon: <Clock size={14} />,                cls: 'pending' },
  processing:   { label: 'Processing…',       icon: <Loader2 size={14} className="spin" />, cls: 'processing' },
  missing_docs: { label: 'Missing Documents', icon: <AlertTriangle size={14} />,         cls: 'missing' },
  approved:     { label: 'Approved',          icon: <CheckCircle size={14} />,           cls: 'approved' },
  rejected:     { label: 'Rejected',          icon: <X size={14} />,                     cls: 'rejected' },
};

const borderMap = {
  missing_docs: 'border-warn',
  approved:     'border-success',
  processing:   'border-info',
};

export function ClaimProcess() {
  const navigate = useNavigate();
  const [claims, setClaims]       = useState(SAMPLE_CLAIMS);
  const [expandedId, setExpanded] = useState(null);
  const [dialogOpen, setDialog]   = useState(false);

  /* Form state */
  const [fName, setFName]         = useState('');
  const [fType, setFType]         = useState('');
  const [fAmount, setFAmount]     = useState('');
  const [fPolicy, setFPolicy]     = useState('');
  const [fPriority, setFPriority] = useState('medium');
  const [fDesc, setFDesc]         = useState('');

  const resetForm = useCallback(() => {
    setFName(''); setFType(''); setFAmount('');
    setFPolicy(''); setFPriority('medium'); setFDesc('');
  }, []);

  const handleToggle = useCallback((id) => setExpanded(prev => prev === id ? null : id), []);

  const handleProcess = useCallback((id) => {
    const claim = claims.find(c => c.id === id);
    if (!claim) return;
    const missing = claim.documents.filter(d => !d.present);
    if (missing.length === 0) {
      setClaims(prev => prev.map(c => c.id === id ? { ...c, status: 'processing' } : c));
      setTimeout(() => navigate(`/claim-workflow?docCount=${claim.documents.length}`), 1500);
    } else {
      setClaims(prev => prev.map(c => c.id === id ? { ...c, status: 'missing_docs' } : c));
      setExpanded(id);
    }
  }, [claims, navigate]);

  const handleDelete = useCallback((id) => {
    setClaims(prev => prev.filter(c => c.id !== id));
    setExpanded(prev => prev === id ? null : prev);
  }, []);

  const handleCreate = useCallback(() => {
    if (!fName.trim() || !fType || !fAmount.trim()) return;
    const newClaim = {
      id: `CLM-${new Date().getFullYear()}-${String(Date.now()).slice(-3)}`,
      claimantName: fName.trim(),
      claimType: fType,
      amount: Number(fAmount) || 0,
      dateSubmitted: new Date().toISOString().split('T')[0],
      priority: fPriority,
      status: 'pending',
      policyNumber: fPolicy.trim() || `POL-${String(Date.now()).slice(-8)}`,
      documents: DEFAULT_DOCUMENTS.map(d => ({ ...d })),
      description: fDesc.trim() || `${fType} claim submitted by ${fName.trim()}.`,
    };
    setClaims(prev => [newClaim, ...prev]);
    resetForm();
    setDialog(false);
  }, [fName, fType, fAmount, fPolicy, fPriority, fDesc, resetForm]);

  const pendingCount     = claims.filter(c => c.status === 'pending').length;
  const missingDocsCount = claims.filter(c => c.status === 'missing_docs').length;
  const totalAmount      = claims.reduce((sum, c) => sum + c.amount, 0);
  const isFormValid      = fName.trim() && fType && fAmount.trim() && Number(fAmount) > 0;

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
            Review and process incoming insurance claim requests. Atlas validates
            document sufficiency and runs the AI workflow automatically.
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
            <div className="claim-stat-label">Pending</div>
          </div>
        </div>
        <div className="claim-stat">
          <div className="claim-stat-icon warn"><AlertTriangle size={16} /></div>
          <div>
            <div className="claim-stat-value">{missingDocsCount}</div>
            <div className="claim-stat-label">Missing Docs</div>
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

      {/* Claim list header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <FileSearch size={14} color="var(--muted)" />
        <span style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>
          All Requests ({claims.length})
        </span>
      </div>

      {/* Claim list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {claims.length === 0 ? (
          <div className="card-glass" style={{ textAlign: 'center', padding: '56px 24px' }}>
            <div className="empty-icon-wrap"><ClipboardList size={24} /></div>
            <div className="empty-title">No claim requests</div>
            <div className="empty-sub">Click "Create New Request" to add your first claim.</div>
          </div>
        ) : (
          claims.map((claim, i) => {
            const status   = statusConfig[claim.status];
            const border   = borderMap[claim.status] || '';
            const expanded = expandedId === claim.id;
            const missing  = claim.documents.filter(d => !d.present);
            const present  = claim.documents.filter(d => d.present);
            const allPresent = missing.length === 0;

            return (
              <div
                key={claim.id}
                className={`claim-card ${border} anim-slide-in`}
                style={{ animationDelay: `${i * 40}ms` }}
              >
                {/* Main row */}
                <div className="claim-card-main">
                  <div className="claim-card-left">
                    <div className="claim-card-avatar"><User size={18} /></div>
                    <div className="claim-card-info">
                      <div className="claim-card-name-row">
                        <span className="claim-card-name">{claim.claimantName}</span>
                        <span className="claim-card-id">{claim.id}</span>
                        <span className={`priority-badge ${claim.priority}`}>
                          <span className="priority-dot" />
                          {claim.priority.charAt(0).toUpperCase() + claim.priority.slice(1)}
                        </span>
                      </div>
                      <div className="claim-card-meta">
                        {claim.claimType} · Policy {claim.policyNumber} · Submitted {formatDate(claim.dateSubmitted)}
                      </div>
                      <div className="claim-card-desc">{claim.description}</div>
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
                      <button className="btn btn-ghost btn-icon btn-sm" title="Delete" onClick={() => handleDelete(claim.id)}>
                        <Trash2 size={14} />
                      </button>
                      <button className="btn btn-ghost btn-icon btn-sm" title="Toggle" onClick={() => handleToggle(claim.id)}>
                        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                      {claim.status === 'pending' && (
                        <button className="claim-btn-process" onClick={() => handleProcess(claim.id)}>
                          <Play size={14} /> Process
                        </button>
                      )}
                      {claim.status === 'processing' && (
                        <button className="btn btn-ghost btn-sm" disabled>
                          <Loader2 size={14} className="spin" /> Processing
                        </button>
                      )}
                      {claim.status === 'missing_docs' && (
                        <button
                          className="btn btn-sm"
                          style={{ borderColor: 'var(--warn-border)', color: 'var(--warn)', background: 'var(--warn-dim)' }}
                          onClick={() => handleToggle(claim.id)}
                        >
                          <AlertTriangle size={14} /> View Issues
                        </button>
                      )}
                      {claim.status === 'approved' && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 6, background: 'var(--success-dim)', color: 'var(--success)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                          <ShieldCheck size={14} /> Approved
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded details */}
                {expanded && (
                  <div className="claim-card-expand">
                    <div className="claim-docs-grid">
                      {/* Present docs */}
                      <div>
                        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 10 }}>
                          Submitted Documents ({present.length})
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          {present.map(doc => (
                            <div key={doc.name} className="claim-doc-item present">
                              <FileText size={14} className="doc-status-icon" />
                              <span className="doc-name">{doc.name}</span>
                              <CheckCircle size={14} className="doc-status-icon" />
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Missing docs or all-verified */}
                      {missing.length > 0 ? (
                        <div>
                          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--warn)', marginBottom: 10 }}>
                            Missing Documents ({missing.length})
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {missing.map(doc => (
                              <div key={doc.name} className="claim-doc-item missing">
                                <ShieldOff size={14} className="doc-status-icon" />
                                <span className="doc-name">{doc.name}</span>
                              </div>
                            ))}
                          </div>
                          {claim.status === 'missing_docs' && (
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 12 }}>
                              Please collect the missing documents and resubmit to continue processing.
                            </p>
                          )}
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                          <div className="claim-docs-verified">
                            <ShieldCheck size={20} color="var(--success)" />
                            <div>
                              <div className="claim-docs-verified-title">All documents verified</div>
                              <div className="claim-docs-verified-sub">Ready for AI workflow processing</div>
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
        Atlas · Document Intelligence · v1.0 — design prototype
      </div>

      {/* Create Dialog */}
      {dialogOpen && (
        <Modal
          title="Create New Claim Request"
          subtitle="Fill in the details below to submit a new claim for AI-powered review and processing."
          onClose={() => { setDialog(false); resetForm(); }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => { setDialog(false); resetForm(); }}>Cancel</button>
              <button className="btn btn-primary" disabled={!isFormValid} onClick={handleCreate}>
                <Plus size={14} /> Create Request
              </button>
            </>
          }
        >
          <div className="claim-form-grid">
            <div>
              <label className="claim-form-label">Claimant Name <span className="required">*</span></label>
              <input className="styled-input" placeholder="e.g. Priya S. Kapoor" value={fName} onChange={e => setFName(e.target.value)} />
            </div>
            <div>
              <label className="claim-form-label">Claim Type <span className="required">*</span></label>
              <select className="styled-select" value={fType} onChange={e => setFType(e.target.value)}>
                <option value="">Select type</option>
                {CLAIM_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div className="claim-form-grid" style={{ marginTop: 14 }}>
            <div>
              <label className="claim-form-label">Claim Amount (₹) <span className="required">*</span></label>
              <input className="styled-input" type="number" placeholder="e.g. 245000" min="1" value={fAmount} onChange={e => setFAmount(e.target.value)} />
            </div>
            <div>
              <label className="claim-form-label">Policy Number</label>
              <input className="styled-input" placeholder="e.g. HLT-9827-4501" value={fPolicy} onChange={e => setFPolicy(e.target.value)} />
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <label className="claim-form-label">Priority</label>
            <select className="styled-select" value={fPriority} onChange={e => setFPriority(e.target.value)}>
              {PRIORITY_OPTIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
          <div style={{ marginTop: 14 }}>
            <label className="claim-form-label">Description</label>
            <textarea
              className="styled-input"
              placeholder="Brief description of the claim..."
              rows={3}
              style={{ resize: 'none' }}
              value={fDesc}
              onChange={e => setFDesc(e.target.value)}
            />
          </div>
          <div className="claim-form-note">
            <strong>Note:</strong> Default documents (Aadhaar Card, PAN Card) will be attached. Additional documents can be managed after creation.
          </div>
        </Modal>
      )}
    </div>
  );
}
