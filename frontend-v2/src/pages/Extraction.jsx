import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Copy, Download, ChevronDown, ChevronRight } from 'lucide-react';
import { getExtractedData } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';

function FieldRow({ label, value, conf }) {
  const pct = conf != null ? Math.round(conf * 100) : null;
  const confClass = pct == null ? '' : pct >= 90 ? 'conf-high' : pct >= 70 ? 'conf-med' : 'conf-low';
  const confColor = pct == null ? '' : pct >= 90 ? 'var(--success)' : pct >= 70 ? 'var(--warn)' : 'var(--danger)';

  return (
    <div className="field-row">
      <div className="field-key">{label}</div>
      <div className="field-val">
        {value == null ? <span style={{ color: 'var(--muted)' }}>—</span> :
         typeof value === 'object' ? <code style={{ fontSize: 11 }}>{JSON.stringify(value)}</code> :
         String(value)}
      </div>
      {pct != null && (
        <div className="field-conf">
          <div className={`conf-dot ${confClass}`} />
          <span style={{ color: confColor }}>{pct}%</span>
        </div>
      )}
    </div>
  );
}

function FieldGroup({ title, children }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="field-group">
      <div
        className="field-group-title"
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {title}
      </div>
      {open && children}
    </div>
  );
}

function renderFields(data) {
  if (!data || typeof data !== 'object') return null;
  const groups = {};
  Object.entries(data).forEach(([k, v]) => {
    const group = k.startsWith('vendor') ? 'Vendor' :
                  k.startsWith('bill') || k.startsWith('line') ? 'Billing' :
                  ['subtotal','tax','total_amount','currency'].includes(k) ? 'Financial' :
                  ['due_date','invoice_date','invoice_number','payment_terms'].includes(k) ? 'Header' :
                  'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push([k, v]);
  });

  return Object.entries(groups).map(([group, fields]) => (
    <FieldGroup key={group} title={group}>
      {fields.map(([k, v]) => (
        <FieldRow key={k} label={k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} value={v} />
      ))}
    </FieldGroup>
  ));
}

export function Extraction() {
  const { completedDocs } = useApp();
  const { refresh } = useDocumentList();
  const [activeId, setActiveId] = useState(null);
  const [extracted, setExtracted] = useState(null);
  const [loadingEx, setLoadingEx] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (completedDocs.length > 0 && !activeId) {
      setActiveId(completedDocs[0].id);
    }
  }, [completedDocs, activeId]);

  useEffect(() => {
    if (!activeId) return;
    setLoadingEx(true); setError(null); setExtracted(null);
    getExtractedData(activeId)
      .then(setExtracted)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingEx(false));
  }, [activeId]);

  const copyJSON = () => {
    if (extracted) {
      navigator.clipboard.writeText(JSON.stringify(extracted.validated_data, null, 2));
    }
  };

  const activeDoc = completedDocs.find((d) => d.id === activeId);

  if (completedDocs.length === 0) {
    return (
      <div className="page">
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <div className="empty-title">No completed documents</div>
            <div className="empty-sub">Upload and process a document to see extracted data here.</div>
            <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => navigate('/upload')}>
              Upload Document
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      {/* Document Tabs */}
      <div className="tabs">
        {completedDocs.slice(0, 8).map((doc) => (
          <div
            key={doc.id}
            className={`tab ${activeId === doc.id ? 'active' : ''}`}
            onClick={() => setActiveId(doc.id)}
          >
            📄 {doc.filename.length > 24 ? doc.filename.slice(0, 24) + '…' : doc.filename}
          </div>
        ))}
      </div>

      <div className="extraction-grid">
        {/* Left: Doc info */}
        <div className="doc-preview">
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Document Preview</span>
            {activeDoc?.doc_type && (
              <span className="badge badge-cyan">{activeDoc.doc_type}</span>
            )}
          </div>

          {/* Simulated doc page */}
          <div style={{
            background: 'var(--surface)', borderRadius: 8, padding: 20, minHeight: 300,
            border: '1px solid var(--border)', position: 'relative', overflow: 'hidden',
          }}>
            <div style={{ background: 'var(--border)', height: 6, borderRadius: 2, width: '60%', marginBottom: 8 }} />
            <div style={{ background: 'var(--card)', height: 4, borderRadius: 2, width: '40%', marginBottom: 20 }} />
            {[90, 85, 92, 78, 88, 76, 82, 70, 95].map((w, i) => (
              <div key={i} style={{ background: 'var(--card)', height: 3, borderRadius: 2, width: `${w}%`, marginBottom: 6 }} />
            ))}
            <div style={{ display: 'flex', gap: 6, margin: '16px 0' }}>
              {[1, 1, 1].map((_, i) => (
                <div key={i} style={{ background: 'var(--border)', height: 18, flex: 1, borderRadius: 2 }} />
              ))}
            </div>
            {[88, 76, 82, 68].map((w, i) => (
              <div key={i} style={{ background: 'var(--card)', height: 3, borderRadius: 2, width: `${w}%`, marginBottom: 6 }} />
            ))}
            <div style={{
              position: 'absolute', top: '10%', left: '8%', padding: '3px 8px',
              background: 'rgba(99,102,241,0.2)', border: '1px solid var(--accent)',
              borderRadius: 4, fontSize: 10, color: 'var(--accent)',
            }}>
              Vendor
            </div>
            <div style={{
              position: 'absolute', top: '10%', right: '8%', padding: '3px 8px',
              background: 'rgba(52,211,153,0.15)', border: '1px solid var(--success)',
              borderRadius: 4, fontSize: 10, color: 'var(--success)',
            }}>
              Date
            </div>
            <div style={{
              position: 'absolute', bottom: '20%', right: '8%', padding: '3px 8px',
              background: 'rgba(245,158,11,0.15)', border: '1px solid var(--warn)',
              borderRadius: 4, fontSize: 10, color: 'var(--warn)',
            }}>
              Amount
            </div>
          </div>

          {extracted && (
            <div className="card" style={{ marginTop: 14, marginBottom: 0, borderColor: extracted.confidence_score >= 0.8 ? 'var(--success)' : 'var(--warn)', background: extracted.confidence_score >= 0.8 ? 'rgba(16,185,129,0.05)' : 'rgba(245,158,11,0.05)' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: extracted.confidence_score >= 0.8 ? 'var(--success)' : 'var(--warn)', marginBottom: 8 }}>
                {extracted.confidence_score >= 0.8 ? '✅ High Confidence Extraction' : '⚠ Review Recommended'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                Confidence: <strong style={{ color: 'var(--text)' }}>{Math.round(extracted.confidence_score * 100)}%</strong>
                {extracted.reviewer_corrections && Object.keys(extracted.reviewer_corrections).length > 0 && (
                  <span style={{ marginLeft: 10 }}>· {Object.keys(extracted.reviewer_corrections).length} field(s) corrected by reviewer</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Extracted fields */}
        <div className="fields-panel">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Extracted Data</div>
              {extracted && (
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                  Confidence: <span style={{ color: 'var(--success)', fontWeight: 600 }}>
                    {Math.round(extracted.confidence_score * 100)}%
                  </span>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={copyJSON} disabled={!extracted}>
                <Copy size={12} /> Copy JSON
              </button>
              <button
                className="btn btn-ghost btn-sm"
                disabled={!extracted}
                onClick={() => {
                  const blob = new Blob([JSON.stringify(extracted?.validated_data, null, 2)], { type: 'application/json' });
                  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
                  a.download = `${activeDoc?.filename?.replace(/\.[^.]+$/, '') || 'extracted'}.json`;
                  a.click();
                }}
              >
                <Download size={12} /> Export
              </button>
            </div>
          </div>

          {loadingEx && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[100, 80, 90, 70, 85].map((w, i) => (
                <div key={i} className="skeleton" style={{ height: 32, width: `${w}%` }} />
              ))}
            </div>
          )}

          {error && (
            <div style={{ color: 'var(--danger)', fontSize: 13, padding: 12, background: 'rgba(239,68,68,0.08)', borderRadius: 8 }}>
              ⚠ {error}
            </div>
          )}

          {extracted && !loadingEx && (
            <>
              {extracted.validated_data ? (
                renderFields(extracted.validated_data)
              ) : (
                <div className="empty-state" style={{ padding: 24 }}>
                  <div className="empty-sub">No structured data extracted yet.</div>
                </div>
              )}

              {/* Raw extraction */}
              {extracted.raw_extracted && (
                <FieldGroup title="Raw Extraction (OCR)">
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace', padding: 10, background: 'var(--surface)', borderRadius: 6, overflow: 'auto', maxHeight: 180 }}>
                    <pre>{typeof extracted.raw_extracted === 'string' ? extracted.raw_extracted : JSON.stringify(extracted.raw_extracted, null, 2)}</pre>
                  </div>
                </FieldGroup>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
