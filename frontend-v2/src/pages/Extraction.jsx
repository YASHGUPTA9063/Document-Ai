import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Copy, Download, ChevronDown, ChevronRight, Maximize2, ExternalLink, FileText, FileSearch, CheckCircle2, AlertTriangle, Edit2, Check, X } from 'lucide-react';
import { getExtractedData, getDocumentFileUrl, updateExtractedData } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';

function FieldRow({ label, fieldKey, value, isEditing, onChange, conf }) {
  const pct = conf != null ? Math.round(conf * 100) : null;
  const confClass = pct == null ? '' : pct >= 90 ? 'conf-high' : pct >= 70 ? 'conf-med' : 'conf-low';
  const confColor = pct == null ? '' : pct >= 90 ? 'var(--success)' : pct >= 70 ? 'var(--warn)' : 'var(--danger)';

  return (
    <div className="field-row" style={{ display: 'flex', alignItems: 'center', minHeight: 32 }}>
      <div className="field-key" style={{ width: '40%', flexShrink: 0 }}>{label}</div>
      <div className="field-val" style={{ flexGrow: 1 }}>
        {isEditing ? (
          <input
            type="text"
            className="styled-input"
            value={value ?? ''}
            onChange={(e) => onChange(fieldKey, e.target.value)}
            style={{ width: '100%', padding: '4px 8px', fontSize: 13, background: 'var(--card-alt)' }}
          />
        ) : (
          value == null ? <span style={{ color: 'var(--muted)' }}>—</span> :
          typeof value === 'object' ? <code style={{ fontSize: 11 }}>{JSON.stringify(value)}</code> :
          String(value)
        )}
      </div>
      {!isEditing && pct != null && (
        <div className="field-conf" style={{ flexShrink: 0, marginLeft: 8 }}>
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

function renderFields(data, isEditing, editedData, onChange) {
  if (!data || typeof data !== 'object') return null;
  const groups = {};
  const renderSource = isEditing ? editedData : data;
  Object.entries(renderSource).forEach(([k, v]) => {
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
        <FieldRow
          key={k}
          label={k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
          fieldKey={k}
          value={v}
          isEditing={isEditing}
          onChange={onChange}
        />
      ))}
    </FieldGroup>
  ));
}

/** Inline document viewer — PDF / image / fallback */
function DocumentViewer({ fileUrl, filename, ext }) {
  if (!fileUrl) return null;

  if (ext === 'pdf') {
    return (
      <object
        data={`${fileUrl}#toolbar=1&navpanes=0&view=FitH`}
        type="application/pdf"
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
      >
        {/* Fallback iframe */}
        <iframe
          src={`${fileUrl}#toolbar=1&navpanes=0`}
          style={{ width: '100%', height: '100%', border: 'none' }}
          title={filename}
        />
        {/* Last-resort text fallback */}
        <div style={{ padding: 24, textAlign: 'center' }}>
          <p style={{ color: 'var(--muted)', marginBottom: 12 }}>
            Your browser cannot display PDFs inline.
          </p>
          <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">
            Open PDF
          </a>
        </div>
      </object>
    );
  }

  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
    return (
      <div style={{
        width: '100%', height: '100%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--surface)', padding: 16,
      }}>
        <img
          src={fileUrl}
          alt={filename}
          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 6 }}
        />
      </div>
    );
  }

  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--surface)', padding: 24, textAlign: 'center',
    }}>
      <div className="empty-icon-wrap">
        <FileText size={32} />
      </div>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6, color: 'var(--text)' }}>{filename}</div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 20 }}>
        Preview not supported for .{ext} files in-browser.
      </div>
      <a href={fileUrl} download={filename} className="btn btn-ghost btn-sm" style={{ border: '1px solid var(--border)' }}>
        Download File
      </a>
    </div>
  );
}

export function Extraction() {
  const { completedDocs } = useApp();
  const { refresh } = useDocumentList();
  const [activeId, setActiveId] = useState(null);
  const [extracted, setExtracted] = useState(null);
  const [loadingEx, setLoadingEx] = useState(false);
  const [error, setError] = useState(null);
  const [viewerExpanded, setViewerExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedData, setEditedData] = useState({});
  const [saving, setSaving] = useState(false);
  const { toast } = useApp();
  const navigate = useNavigate();

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (completedDocs.length > 0 && !activeId) {
      setActiveId(completedDocs[0].id);
    }
  }, [completedDocs, activeId]);

  useEffect(() => {
    if (!activeId) return;
    setLoadingEx(true); setError(null); setExtracted(null); setIsEditing(false); setEditedData({});
    getExtractedData(activeId)
      .then((data) => {
        setExtracted(data);
        if (data?.validated_data) {
          setEditedData(data.validated_data);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingEx(false));
  }, [activeId]);

  const copyJSON = () => {
    if (extracted) {
      navigator.clipboard.writeText(JSON.stringify(extracted.validated_data, null, 2));
    }
  };

  const handleFieldChange = (key, val) => {
    setEditedData((prev) => ({
      ...prev,
      [key]: val,
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateExtractedData(activeId, editedData);
      toast('Extracted data updated successfully ✓', 'success');
      const data = await getExtractedData(activeId);
      setExtracted(data);
      if (data?.validated_data) {
        setEditedData(data.validated_data);
      }
      setIsEditing(false);
    } catch (err) {
      toast('Failed to save changes: ' + err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (extracted?.validated_data) {
      setEditedData(extracted.validated_data);
    }
    setIsEditing(false);
  };

  const activeDoc = completedDocs.find((d) => d.id === activeId);
  const fileUrl = activeId ? getDocumentFileUrl(activeId) : '';
  const ext = activeDoc?.filename?.split('.').pop()?.toLowerCase() ?? '';

  if (completedDocs.length === 0) {
    return (
      <div className="page">
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon-wrap">
              <FileSearch size={32} />
            </div>
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
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <FileText size={13} />
            {doc.filename.length > 24 ? doc.filename.slice(0, 24) + '…' : doc.filename}
          </div>
        ))}
      </div>

      {/* ── Full-screen overlay viewer ── */}
      {viewerExpanded && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(8,11,20,0.90)', backdropFilter: 'blur(16px)',
            display: 'flex', flexDirection: 'column',
            animation: 'fade-in 150ms ease',
          }}
          onClick={(e) => e.target === e.currentTarget && setViewerExpanded(false)}
        >
          {/* Header bar */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 20px', borderBottom: '1px solid var(--border)',
            background: 'var(--card)', flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontWeight: 700, fontSize: 14, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <FileText size={15} />
                {activeDoc?.filename}
              </span>
              {activeDoc?.doc_type && <span className="badge badge-cyan">{activeDoc.doc_type}</span>}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">
                <ExternalLink size={13} /> Open in new tab
              </a>
              <button className="btn btn-ghost btn-sm" onClick={() => setViewerExpanded(false)}>✕ Close</button>
            </div>
          </div>
          {/* Full viewer body */}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <DocumentViewer fileUrl={fileUrl} filename={activeDoc?.filename ?? ''} ext={ext} />
          </div>
        </div>
      )}

      {/* ── Side-by-side split layout ── */}
      <div className="extraction-grid" style={{ alignItems: 'start' }}>

        {/* ── LEFT: Sticky document viewer panel ── */}
        <div
          className="doc-preview"
          style={{
            position: 'sticky',
            top: 16,
            padding: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            height: 'min(82vh, 720px)',
          }}
        >
          {/* Panel header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '11px 14px', borderBottom: '1px solid var(--border)',
            flexShrink: 0, background: 'var(--card)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Source Document
              </span>
              {activeDoc?.doc_type && <span className="badge badge-cyan">{activeDoc.doc_type}</span>}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                id="extraction-viewer-expand"
                className="btn btn-ghost btn-sm"
                title="Expand to fullscreen"
                onClick={() => setViewerExpanded(true)}
                style={{ fontSize: 11, padding: '3px 9px', gap: 5 }}
              >
                <Maximize2 size={12} /> Expand
              </button>
              <a
                href={fileUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 11, padding: '3px 9px', gap: 5 }}
              >
                <ExternalLink size={12} /> New tab
              </a>
            </div>
          </div>

          {/* Embedded viewer */}
          <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
            <DocumentViewer fileUrl={fileUrl} filename={activeDoc?.filename ?? ''} ext={ext} />
          </div>

          {/* Confidence banner pinned to bottom */}
          {extracted && (
            <div style={{
              padding: '9px 14px', flexShrink: 0,
              borderTop: '1px solid var(--border)',
              background: extracted.confidence_score >= 0.8
                ? 'rgba(16,185,129,0.06)'
                : 'rgba(245,158,11,0.06)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{
                fontSize: 12, fontWeight: 600,
                color: extracted.confidence_score >= 0.8 ? 'var(--success)' : 'var(--warn)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
              }}>
                {extracted.confidence_score >= 0.8 ? (
                  <>
                    <CheckCircle2 size={13} />
                    High Confidence
                  </>
                ) : (
                  <>
                    <AlertTriangle size={13} />
                    Review Recommended
                  </>
                )}
              </span>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                Confidence: <strong style={{ color: 'var(--text)' }}>{Math.round(extracted.confidence_score * 100)}%</strong>
                {extracted.reviewer_corrections && Object.keys(extracted.reviewer_corrections).length > 0 && (
                  <span style={{ marginLeft: 8, color: 'var(--accent)' }}>
                    · {Object.keys(extracted.reviewer_corrections).length} corrected
                  </span>
                )}
              </span>
            </div>
          )}
        </div>

        {/* ── RIGHT: Extracted fields panel (scrollable) ── */}
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
              {isEditing ? (
                <>
                  <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Check size={12} /> Save
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={handleCancel} disabled={saving} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <X size={12} /> Cancel
                  </button>
                </>
              ) : (
                <>
                  <button className="btn btn-ghost btn-sm" onClick={() => setIsEditing(true)} disabled={!extracted} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Edit2 size={12} /> Edit Fields
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={copyJSON} disabled={!extracted} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Copy size={12} /> Copy JSON
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={!extracted}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(extracted?.validated_data, null, 2)], { type: 'application/json' });
                      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
                      a.download = `${activeDoc?.filename?.replace(/\.[^.]+$/, '') || 'extracted'}.json`;
                      a.click();
                    }}
                  >
                    <Download size={12} /> Export
                  </button>
                </>
              )}
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
            <div style={{ color: 'var(--danger)', fontSize: 13, padding: 12, background: 'rgba(239,68,68,0.08)', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          {extracted && !loadingEx && (
            <>
              {extracted.validated_data ? (
                renderFields(extracted.validated_data, isEditing, editedData, handleFieldChange)
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
