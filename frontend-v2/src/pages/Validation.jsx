import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Edit3, RefreshCw, AlertTriangle, FileText, X, Plus, Shield } from 'lucide-react';
import { resumeReview, resumeDuplicate, getExtractedData } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Modal } from '../components/ui/Modal';

function parseArrayOfText(value) {
  if (value === null || value === undefined) return null;
  let parsed = value;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        parsed = JSON.parse(trimmed);
      } catch (e) {
        return null;
      }
    } else {
      return null;
    }
  }
  
  if (Array.isArray(parsed)) {
    if (parsed.length === 0) {
      return parsed;
    }
    if (parsed.every(item => item !== null && typeof item !== 'object')) {
      return parsed.map(String);
    }
  }
  return null;
}

function parseObjectData(value) {
  if (value === null || value === undefined) return null;
  let parsed = value;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        parsed = JSON.parse(trimmed);
      } catch (e) {
        return null;
      }
    } else {
      return null;
    }
  }

  if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) {
    return parsed;
  }
  return null;
}

function parseValidationMessage(msg) {
  if (!msg) return [];
  let cleaned = String(msg).trim();
  if (!cleaned) return [];

  if (/^Mandatory field\(s\) missing or empty:\s*/i.test(cleaned)) {
    cleaned = cleaned.replace(/^Mandatory field\(s\) missing or empty:\s*/i, '');
  }

  let items = [];
  if (cleaned.includes('\n')) {
    items = cleaned.split('\n');
  } else if (cleaned.includes('•')) {
    items = cleaned.split('•');
  } else if (cleaned.includes('.,')) {
    items = cleaned.split(/\.,\s*/);
  } else {
    items = cleaned.split(/,\s*(?=(?:The|Mandatory|Field|Validation|Date|[A-Z]['a-zA-Z]))/);
  }

  const rawList = [];
  const seen = new Set();

  for (let item of items) {
    let text = item.replace(/^[•\-\*\s]+/, '').trim();
    if (!text) continue;
    if (!/[.!?]$/.test(text)) {
      text += '.';
    }
    const key = text.toLowerCase().replace(/['"]/g, '');
    if (!seen.has(key)) {
      seen.add(key);
      rawList.push(text);
    }
  }

  const finalItems = [];
  for (let text of rawList) {
    const match = text.match(/^Mandatory field missing or empty:\s*['"]?([^'"]+)['"]?/i);
    if (match) {
      const fieldName = match[1];
      const alreadyCovered = rawList.some(
        other => other !== text && other.toLowerCase().includes(fieldName.toLowerCase())
      );
      if (alreadyCovered) continue;
    }
    finalItems.push(text);
  }

  return finalItems;
}

/**
 * Inline field-level corrections editor.
 * Renders extracted fields as styled inputs so reviewers can correct
 * individual values instead of hand-editing raw JSON.
 */
function InlineCorrectionsEditor({ validatedData, onChange }) {
  const [edits, setEdits] = useState(() => {
    // Initialise with current values so the reviewer sees pre-filled inputs
    const init = {};
    if (validatedData && typeof validatedData === 'object') {
      Object.entries(validatedData).forEach(([k, v]) => {
        const arr = parseArrayOfText(v);
        if (arr) {
          init[k] = arr;
        } else if (v != null && typeof v !== 'object') {
          init[k] = String(v);
        }
      });
    }
    return init;
  });

  // Track which keys have been changed from the original
  const [changed, setChanged] = useState(new Set());

  const handleChange = (key, newVal) => {
    const original = validatedData?.[key];
    const isChanged = Array.isArray(newVal)
      ? JSON.stringify(parseArrayOfText(original) || []) !== JSON.stringify(newVal)
      : String(original) !== newVal;

    setChanged((prev) => {
      const next = new Set(prev);
      isChanged ? next.add(key) : next.delete(key);
      return next;
    });

    const next = { ...edits, [key]: newVal };
    setEdits(next);

    // Re-derive corrections from the changed set after this update
    const finalChanged = new Set(changed);
    isChanged ? finalChanged.add(key) : finalChanged.delete(key);
    const finalCorrections = {};
    finalChanged.forEach((k) => {
      let valToSend = next[k];
      if (Array.isArray(valToSend)) {
        const origVal = validatedData?.[k];
        if (typeof origVal === 'string') {
          valToSend = JSON.stringify(valToSend);
        }
      }
      finalCorrections[k] = valToSend;
    });
    onChange(finalCorrections);
  };

  if (!validatedData || typeof validatedData !== 'object') {
    return (
      <div style={{ fontSize: 13, color: 'var(--muted)', padding: '12px 0' }}>
        No extracted fields available to edit.
      </div>
    );
  }

  const primitiveEntries = Object.entries(validatedData).filter(
    ([, v]) => v != null && typeof v !== 'object' && parseArrayOfText(v) === null
  );
  const textArrayEntries = Object.entries(validatedData).filter(
    ([, v]) => v != null && parseArrayOfText(v) !== null
  );
  const objectEntries = Object.entries(validatedData).filter(
    ([, v]) => v != null && typeof v === 'object' && parseArrayOfText(v) === null
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {changed.size > 0 && (
        <div style={{
          fontSize: 12, color: 'var(--accent)', fontWeight: 600,
          padding: '6px 10px', background: 'var(--accent-dim)',
          borderRadius: 6, border: '1px solid rgba(79,110,247,0.2)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
        }}>
          <Edit3 size={13} />
          {changed.size} field{changed.size !== 1 ? 's' : ''} modified
        </div>
      )}

      {primitiveEntries.map(([key, originalVal]) => {
        const isModified = changed.has(key);
        return (
          <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{
              fontSize: 11, fontWeight: 600, color: isModified ? 'var(--accent)' : 'var(--muted)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
              {key.replace(/_/g, ' ')}
              {isModified && (
                <span style={{
                  fontSize: 10, background: 'var(--accent)', color: 'white',
                  borderRadius: 99, padding: '1px 6px',
                }}>modified</span>
              )}
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id={`correction-field-${key}`}
                type="text"
                className="styled-input"
                value={(edits[key] === 'null' || edits[key] === 'NULL') ? '' : (edits[key] ?? '')}
                onChange={(e) => handleChange(key, e.target.value)}
                placeholder={originalVal == null || originalVal === 'null' || originalVal === 'NULL' ? '' : String(originalVal)}
                style={{
                  borderColor: isModified ? 'var(--accent)' : undefined,
                  boxShadow: isModified ? '0 0 0 3px var(--accent-dim)' : undefined,
                  paddingRight: isModified ? 70 : undefined,
                  transition: 'all 0.2s ease',
                }}
              />
              {isModified && (
                <button
                  type="button"
                  onClick={() => handleChange(key, String(originalVal))}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    fontSize: 10, color: 'var(--muted)', background: 'var(--card-alt)',
                    border: '1px solid var(--border)', borderRadius: 4,
                    padding: '2px 7px', cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  title="Reset to original"
                >
                  ↩ reset
                </button>
              )}
            </div>
            {isModified && (
              <div style={{ fontSize: 11, color: 'var(--muted)', paddingLeft: 2 }}>
                Original: <span style={{ fontFamily: 'monospace', color: 'var(--text-dim)' }}>{originalVal == null || originalVal === 'null' || originalVal === 'NULL' ? '' : String(originalVal)}</span>
              </div>
            )}
          </div>
        );
      })}

      {textArrayEntries.map(([key, originalVal]) => {
        const isModified = changed.has(key);
        const currentArray = edits[key] || [];

        const handleAdd = (val) => {
          if (!val.trim()) return;
          handleChange(key, [...currentArray, val.trim()]);
        };

        const handleRemove = (idxToRemove) => {
          handleChange(key, currentArray.filter((_, i) => i !== idxToRemove));
        };

        return (
          <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{
              fontSize: 11, fontWeight: 600, color: isModified ? 'var(--accent)' : 'var(--muted)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
              {key.replace(/_/g, ' ')}
              {isModified && (
                <span style={{
                  fontSize: 10, background: 'var(--accent)', color: 'white',
                  borderRadius: 99, padding: '1px 6px',
                }}>modified</span>
              )}
            </label>
            
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 4, background: 'var(--surface)', padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
              {currentArray.length === 0 ? (
                <span style={{ color: 'var(--muted)', fontStyle: 'italic', fontSize: 12 }}>No items</span>
              ) : (
                currentArray.map((item, idx) => (
                  <span key={idx} style={{
                    background: 'var(--card-alt)',
                    color: 'var(--text)',
                    padding: '3px 8px',
                    borderRadius: '12px',
                    border: '1px solid var(--border)',
                    fontSize: 11,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4
                  }}>
                    {item}
                    <button
                      type="button"
                      onClick={() => handleRemove(idx)}
                      style={{
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--muted)',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: 0
                      }}
                    >
                      <X size={10} />
                    </button>
                  </span>
                ))
              )}
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="text"
                placeholder="Add item..."
                id={`add-input-${key}`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAdd(e.target.value);
                    e.target.value = '';
                  }
                }}
                style={{
                  flexGrow: 1,
                  padding: '6px 10px',
                  fontSize: 12,
                  background: 'var(--card-alt)',
                  border: '1px solid var(--border)',
                  borderRadius: 4
                }}
              />
              <button
                type="button"
                onClick={() => {
                  const input = document.getElementById(`add-input-${key}`);
                  if (input) {
                    handleAdd(input.value);
                    input.value = '';
                  }
                }}
                className="btn btn-ghost btn-sm"
                style={{ height: 30, padding: '0 10px', fontSize: 11 }}
              >
                <Plus size={11} /> Add
              </button>
            </div>
            
            {isModified && (
              <div style={{ fontSize: 11, color: 'var(--muted)', paddingLeft: 2, marginTop: 2 }}>
                Original: <span style={{ fontFamily: 'monospace', color: 'var(--text-dim)' }}>
                  {JSON.stringify(parseArrayOfText(originalVal))}
                </span>
              </div>
            )}
          </div>
        );
      })}

      {objectEntries.length > 0 && (
        <div style={{
          fontSize: 11, color: 'var(--muted)', padding: '8px 10px',
          background: 'var(--surface)', borderRadius: 6,
          border: '1px solid var(--border)',
        }}>
          <strong>Note:</strong> Complex/nested fields (
          {objectEntries.map(([k]) => <code key={k} style={{ margin: '0 3px' }}>{k}</code>)}
          ) cannot be edited inline and are passed through unchanged.
        </div>
      )}
    </div>
  );
}

/** Recursively flatten all leaf numbers from a nested confidence structure and average them. */
function getAverageWordConfidence(extracted) {
  const confidences = extracted?.raw_extracted?.field_confidences;
  if (!confidences || typeof confidences !== 'object') return 0;

  const flatConfidences = [];
  const traverse = (obj) => {
    if (typeof obj === 'number') {
      flatConfidences.push(obj);
    } else if (Array.isArray(obj)) {
      obj.forEach(item => traverse(item));
    } else if (obj && typeof obj === 'object') {
      Object.values(obj).forEach(val => traverse(val));
    }
  };
  traverse(confidences);

  if (flatConfidences.length === 0) return 0;
  return flatConfidences.reduce((sum, val) => sum + val, 0) / flatConfidences.length;
}

function ReviewCard({ doc, onAction }) {
  const [extracted, setExtracted] = useState(null);
  const [showEdit, setShowEdit] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [corrections, setCorrections] = useState({});
  const [loading, setLoading] = useState(false);
  const { toast, confidenceMode, autoApproveThreshold } = useApp();

  useEffect(() => {
    getExtractedData(doc.id)
      .then(setExtracted)
      .catch(() => {});
  }, [doc.id]);

  // Use the same confidence logic as the Extraction page
  const wordConf = extracted ? getAverageWordConfidence(extracted) : 0;
  const pageConf = extracted ? (extracted.confidence_score ?? 0) : 0;
  const score = extracted
    ? (confidenceMode === 'page'
      ? pageConf
      : confidenceMode === 'word'
        ? wordConf
        : Math.min(wordConf, pageConf))
    : null;
  const threshold = (autoApproveThreshold ?? 80) / 100;
  const scoreColor = score == null ? 'var(--muted)' : score >= threshold ? 'var(--success)' : 'var(--warn)';

  const handle = async (approved, corr = null, reason = null) => {
    setLoading(true);
    try {
      await resumeReview(doc.workflow_run_id, approved, corr, reason);
      onAction(doc.id, approved ? 'approved' : 'rejected');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    } finally {
      setLoading(false);
      setShowEdit(false);
      setShowRejectConfirm(false);
      setRejectionReason('');
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
      setRejectionReason('');
    }
  };

  const isDuplicateWait = doc.message?.toLowerCase().includes('duplicate');
  const validationIssues = parseValidationMessage(doc.message);

  const handleSaveAndApprove = () => {
    // Pass corrections only if any fields were changed
    handle(true, Object.keys(corrections).length > 0 ? corrections : null);
  };

  const handleConfirmReject = () => {
    if (isDuplicateWait) {
      handleDuplicate(false);
    } else {
      handle(false, null, rejectionReason.trim() || null);
    }
  };

  return (
    <>
      <div className="card" style={{ borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.03)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
              <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
              {doc.filename}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <StatusBadge status={doc.status} />
              {doc.doc_type && <span className="badge badge-cyan">{doc.doc_type}</span>}
              {score != null && (
                <span className="badge badge-yellow">
                  Doc Score: <strong style={{ color: scoreColor }}>{Math.round(score * 100)}%</strong>
                </span>
              )}
            </div>
          </div>
          {validationIssues.length > 0 && (
            <span className="badge badge-yellow" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
              <AlertTriangle size={12} /> {validationIssues.length} Warning{validationIssues.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Validation warnings banner */}
        {validationIssues.length > 0 && (
          <div style={{
            background: 'rgba(245, 158, 11, 0.07)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            borderRadius: 8,
            padding: '10px 14px',
            marginBottom: 14
          }}>
            <div style={{
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--warn)',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 6
            }}>
              <AlertTriangle size={13} />
              Validation Warnings &amp; Issues
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text)', lineHeight: 1.6 }}>
              {validationIssues.map((issue, idx) => (
                <li key={idx} style={{ color: 'var(--warn)', marginBottom: idx < validationIssues.length - 1 ? 3 : 0 }}>
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Extracted fields summary */}
        {extracted?.validated_data && (
          <div style={{ background: 'var(--surface)', borderRadius: 8, padding: 12, marginBottom: 14, fontSize: 12 }}>
            <div style={{ color: 'var(--muted)', marginBottom: 8, fontWeight: 600, fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Extracted Fields
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {Object.entries(extracted.validated_data)
                .filter(([k, v]) => {
                  if (v == null || v === 'null' || v === 'NULL') return false;
                  return true;
                })
                .slice(0, 8)
                .map(([k, v]) => {
                  const arr = parseArrayOfText(v);
                  const obj = parseObjectData(v);
                  const displayVal = arr
                    ? arr.join(', ')
                    : obj
                      ? Object.entries(obj).map(([sk, sv]) => `${sk.replace(/_/g, ' ')}: ${sv ?? '—'}`).join(' | ')
                      : String(v);
                  return (
                    <div key={k}>
                      <span style={{ color: 'var(--muted)' }}>{k.replace(/_/g, ' ')}: </span>
                      <span style={{ color: 'var(--text)', fontWeight: 500 }} title={displayVal}>
                        {displayVal.length > 30 ? displayVal.slice(0, 27) + '...' : displayVal}
                      </span>
                    </div>
                  );
                })}
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
              <button className="btn btn-ghost" onClick={() => { setCorrections({}); setShowEdit(true); }} disabled={loading}>
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
          onClose={() => { setShowRejectConfirm(false); setRejectionReason(''); }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => { setShowRejectConfirm(false); setRejectionReason(''); }}>Cancel</button>
              <button
                className="btn btn-danger"
                onClick={handleConfirmReject}
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
            marginBottom: 12,
          }}>
            <AlertTriangle size={16} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: 1 }} />
            <span style={{ color: 'var(--danger)' }}>Rejecting stops the workflow and marks this document as failed.</span>
          </div>
          {!isDuplicateWait && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Rejection Reason <span style={{ color: 'var(--muted)', fontWeight: 400, textTransform: 'none' }}>(optional)</span>
              </label>
              <textarea
                id="rejection-reason-input"
                rows={3}
                placeholder="e.g. Poor document quality, missing fields, suspected fraud…"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  padding: '8px 10px',
                  fontSize: 12,
                  background: 'var(--card-alt)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  color: 'var(--text)',
                  resize: 'vertical',
                  lineHeight: 1.5,
                  fontFamily: 'inherit',
                  outline: 'none',
                }}
                onFocus={(e) => { e.target.style.borderColor = 'var(--danger)'; e.target.style.boxShadow = '0 0 0 3px var(--danger-dim)'; }}
                onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none'; }}
              />
            </div>
          )}
        </Modal>
      )}

      {/* ── Feature 21: Inline edit modal with individual field inputs ── */}
      {showEdit && (
        <Modal
          title="Edit &amp; Approve"
          subtitle={`Correct extracted fields for ${doc.filename} — only changed values are submitted.`}
          onClose={() => setShowEdit(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowEdit(false)}>Cancel</button>
              <button
                id="corrections-save-btn"
                className="btn btn-primary"
                onClick={handleSaveAndApprove}
                disabled={loading}
              >
                {Object.keys(corrections).length > 0
                  ? `Save ${Object.keys(corrections).length} Correction${Object.keys(corrections).length !== 1 ? 's' : ''} & Approve`
                  : 'Approve without changes'}
              </button>
            </>
          }
        >
          <InlineCorrectionsEditor
            validatedData={extracted?.validated_data}
            onChange={setCorrections}
          />
        </Modal>
      )}
    </>
  );
}






const RULES = [
  { label: 'Review Confidence Threshold',               badge: '< 80%', variant: 'badge-green' },
  { label: 'Mandatory Field Completeness Check',       badge: 'Enabled', variant: 'badge-green' },
  { label: 'Financial Total Reconciliation',           badge: 'Enabled', variant: 'badge-green' },
  { label: 'Line Item & Subtotal Verification',        badge: 'Enabled', variant: 'badge-green' },
  { label: 'Issue & Expiration Date Chronology Check', badge: 'Enabled', variant: 'badge-green' },
  { label: 'Document Template Schema Alignment',       badge: 'Enabled', variant: 'badge-green' },
  { label: 'OCR Error & Typo Normalization',           badge: 'Enabled', variant: 'badge-green' },
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
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertTriangle size={16} style={{ color: 'var(--warn)' }} />
                  Pending Human Review
                </div>
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
                <div className="empty-icon-wrap" style={{ color: 'var(--success)', background: 'var(--success-dim)', border: '1px solid var(--success-border)' }}>
                  <CheckCircle size={32} />
                </div>
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

          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>How Review Works</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7 }}>
              <p style={{ marginBottom: 8 }}>Documents are automatically approved if confidence ≥ 80%. Otherwise, they enter this review queue.</p>
              <p style={{ marginBottom: 8 }}><strong>Approve</strong> — signals the workflow to finalize and store extracted data.</p>
              <p style={{ marginBottom: 8 }}><strong>Edit &amp; Approve</strong> — opens an inline field editor. Each extracted field appears as a styled input — just change what's wrong and the corrections are tracked automatically. No manual JSON required.</p>
              <p><strong>Reject</strong> — marks the document as rejected and stops processing.</p>
            </div>
          </div>
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
        </div>
      </div>
    </div>
  );
}
