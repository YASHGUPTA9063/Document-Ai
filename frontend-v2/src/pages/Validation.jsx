import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Edit3, RefreshCw, AlertTriangle } from 'lucide-react';
import { resumeReview, resumeDuplicate, getExtractedData } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Modal } from '../components/ui/Modal';

function ReviewCard({ doc, onAction }) {
  const [extracted, setExtracted] = useState(null);
  const [showEdit, setShowEdit] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [corrections, setCorrections] = useState('{}');
  const [loading, setLoading] = useState(false);
  const { toast } = useApp();

  useEffect(() => {
    getExtractedData(doc.id)
      .then(setExtracted)
      .catch(() => {});
  }, [doc.id]);

  const score = extracted?.confidence_score;
  const scoreColor = score == null ? 'var(--muted)' : score >= 0.8 ? 'var(--success)' : 'var(--warn)';

  const handle = async (approved, corr = null) => {
    setLoading(true);
    try {
      await resumeReview(doc.workflow_run_id, approved, corr);
      onAction(doc.id, approved ? 'approved' : 'rejected');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    } finally {
      setLoading(false);
      setShowEdit(false);
      setShowRejectConfirm(false);
    }
  };

  const handleDuplicate = async (override) => {
    setLoading(true);
    try {
      await resumeDuplicate(doc.workflow_run_id, override);
      onAction(doc.id, override ? 'override' : 'rejected');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const isDuplicateWait = doc.message?.toLowerCase().includes('duplicate');

  return (
    <>
      <div className="card" style={{ borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.03)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>
              <span className="doc-icon">📄</span>{doc.filename}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <StatusBadge status={doc.status} />
              {doc.doc_type && <span className="badge badge-cyan">{doc.doc_type}</span>}
              {score != null && (
                <span className="badge badge-yellow">
                  Confidence: <strong style={{ color: scoreColor }}>{Math.round(score * 100)}%</strong>
                </span>
              )}
            </div>
          </div>
          {doc.message && (
            <span style={{ fontSize: 11, color: 'var(--warn)', maxWidth: 200, textAlign: 'right' }}>
              ⚠ {doc.message}
            </span>
          )}
        </div>

        {/* Extracted fields summary */}
        {extracted?.validated_data && (
          <div style={{ background: 'var(--surface)', borderRadius: 8, padding: 12, marginBottom: 14, fontSize: 12 }}>
            <div style={{ color: 'var(--muted)', marginBottom: 8, fontWeight: 600, fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Extracted Fields
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {Object.entries(extracted.validated_data)
                .filter(([, v]) => v != null && typeof v !== 'object')
                .slice(0, 8)
                .map(([k, v]) => (
                  <div key={k}>
                    <span style={{ color: 'var(--muted)' }}>{k.replace(/_/g, ' ')}: </span>
                    <span style={{ color: 'var(--text)', fontWeight: 500 }}>{String(v)}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          {isDuplicateWait ? (
            <>
              <button className="btn btn-primary" onClick={() => handleDuplicate(true)} disabled={loading}>
                <CheckCircle size={14} /> Override Duplicate
              </button>
              <button className="btn btn-danger" onClick={() => setShowRejectConfirm(true)} disabled={loading}>
                <XCircle size={14} /> Reject
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-success" onClick={() => handle(true)} disabled={loading}>
                <CheckCircle size={14} /> Approve
              </button>
              <button className="btn btn-danger" onClick={() => setShowRejectConfirm(true)} disabled={loading}>
                <XCircle size={14} /> Reject
              </button>
              <button className="btn btn-ghost" onClick={() => setShowEdit(true)} disabled={loading}>
                <Edit3 size={14} /> Edit &amp; Approve
              </button>
            </>
          )}
        </div>
      </div>

      {/* Reject confirmation modal */}
      {showRejectConfirm && (
        <Modal
          title="Reject Document?"
          subtitle={`This will stop processing for "${doc.filename}". This cannot be undone.`}
          onClose={() => setShowRejectConfirm(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowRejectConfirm(false)}>Cancel</button>
              <button
                className="btn btn-danger"
                onClick={() => isDuplicateWait ? handleDuplicate(false) : handle(false)}
                disabled={loading}
              >
                <XCircle size={14} /> Confirm Reject
              </button>
            </>
          }
        >
          <div style={{
            display: 'flex', gap: 12, alignItems: 'flex-start',
            padding: '12px 14px',
            background: 'var(--danger-dim)', border: '1px solid var(--danger-border)',
            borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-md)',
          }}>
            <AlertTriangle size={16} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 1 }} />
            <span style={{ color: 'var(--danger)' }}>Rejecting stops the workflow and marks this document as failed.</span>
          </div>
        </Modal>
      )}

      {/* Edit modal */}
      {showEdit && (
        <Modal
          title="Edit &amp; Approve"
          subtitle={`Correct extracted fields for ${doc.filename}`}
          onClose={() => setShowEdit(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowEdit(false)}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  try {
                    const corr = JSON.parse(corrections);
                    handle(true, corr);
                  } catch {
                    toast('Invalid JSON — please check your corrections', 'error');
                  }
                }}
              >
                Save &amp; Approve
              </button>
            </>
          }
        >
          <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', marginBottom: 8 }}>
            Enter corrections as JSON (field_name: corrected_value):
          </div>
          <textarea
            className="styled-input"
            rows={8}
            value={corrections}
            onChange={(e) => setCorrections(e.target.value)}
            style={{ fontFamily: 'monospace', fontSize: 'var(--text-base)', resize: 'vertical' }}
            placeholder={'{\n  "vendor_name": "Corrected Corp",\n  "total_amount": 1234.56\n}'}
          />
        </Modal>
      )}
    </>
  );
}

const RULES = [
  { label: 'Confidence threshold triggers review', badge: '< 80%', variant: 'badge-green' },
  { label: 'Math cross-check on financial docs',   badge: 'Enabled', variant: 'badge-green' },
  { label: 'Date format normalization (ISO 8601)', badge: 'Enabled', variant: 'badge-green' },
  { label: 'Duplicate detection (SHA-256 hash)',   badge: 'Enabled', variant: 'badge-green' },
];

export function Validation() {
  const { reviewDocs, updateDocument, toast } = useApp();
  const { refresh, loading } = useDocumentList();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(new Set());

  useEffect(() => { refresh(); }, []);

  const handleAction = (docId, action) => {
    setDismissed((d) => new Set([...d, docId]));
    const newStatus = action === 'approved' ? 'completed' : 
                      action === 'override' ? 'processing' : 'rejected';
    updateDocument({ id: docId, status: newStatus });
    toast(
      action === 'approved' ? 'Document approved ✓' :
      action === 'override' ? 'Duplicate overridden, processing continues' :
      'Document rejected',
      action === 'rejected' ? 'warn' : 'success'
    );
  };

  const visible = reviewDocs.filter((d) => !dismissed.has(d.id));

  return (
    <div className="page">
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <div>
                <div className="card-title">⚠️ Pending Human Review</div>
                <div className="card-sub">{visible.length} document{visible.length !== 1 ? 's' : ''} awaiting decision</div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>
                <RefreshCw size={12} className={loading ? 'spin' : ''} />
              </button>
            </div>
          </div>

          {visible.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <div className="empty-icon">✅</div>
                <div className="empty-title">All clear!</div>
                <div className="empty-sub">No documents are currently awaiting review.</div>
                <button className="btn btn-ghost btn-sm" style={{ marginTop: 14 }} onClick={() => navigate('/documents')}>
                  View All Documents
                </button>
              </div>
            </div>
          ) : (
            visible.map((doc) => (
              <ReviewCard key={doc.id} doc={doc} onAction={handleAction} />
            ))
          )}
        </div>

        <div>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>Validation Rules</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
              {RULES.map((r) => (
                <div key={r.label} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 12px', background: 'var(--surface)', borderRadius: 8,
                }}>
                  <span>{r.label}</span>
                  <span className={`badge ${r.variant}`}>{r.badge}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>How Review Works</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7 }}>
              <p style={{ marginBottom: 8 }}>Documents are automatically approved if confidence ≥ 80%. Otherwise, they enter this review queue.</p>
              <p style={{ marginBottom: 8 }}><strong>Approve</strong> — signals the workflow to finalize and store extracted data.</p>
              <p style={{ marginBottom: 8 }}><strong>Edit &amp; Approve</strong> — allows correcting individual fields before approval. Corrections are stored.</p>
              <p><strong>Reject</strong> — marks the document as rejected and stops processing.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
