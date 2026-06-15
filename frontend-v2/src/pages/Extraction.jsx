import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Copy, Download, ChevronDown, ChevronRight, Maximize2, ExternalLink, FileText, FileSearch, CheckCircle2, AlertTriangle, Edit2, Check, X, Trash2, Plus } from 'lucide-react';
import { getExtractedData, getDocumentFileUrl, updateExtractedData, getTemplates } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';

function parseTableData(value, key) {
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
    if (parsed.every(item => item !== null && typeof item === 'object' && !Array.isArray(item))) {
      return parsed;
    }
  }
  return null;
}

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

const getTableHeaders = (items) => {
  const keysSet = new Set();
  items.forEach(item => {
    if (item && typeof item === 'object') {
      Object.keys(item).forEach(key => keysSet.add(key));
    }
  });
  return Array.from(keysSet);
};

/** Recursively collect all leaf numbers from a nested confidence structure and average them. */
function flattenConfidence(conf) {
  if (conf == null) return null;
  if (typeof conf === 'number') return conf;
  const nums = [];
  const collect = (node) => {
    if (typeof node === 'number') {
      nums.push(node);
    } else if (Array.isArray(node)) {
      node.forEach(collect);
    } else if (node && typeof node === 'object') {
      Object.values(node).forEach(collect);
    }
  };
  collect(conf);
  if (nums.length === 0) return null;
  return nums.reduce((s, n) => s + n, 0) / nums.length;
}

const getDefaultHeaders = (key) => {
  const k = (key || '').toLowerCase();
  if (k.includes('item')) {
    return ['description', 'quantity', 'unit_price', 'total'];
  }
  if (k.includes('transaction')) {
    return ['date', 'description', 'debit', 'credit', 'balance'];
  }
  return ['description', 'quantity', 'unit_price', 'total'];
};

function FieldRow({ label, fieldKey, value, isEditing, onChange, conf, confHighThreshold = 90, confMedThreshold = 70, fieldHighlightThreshold = 95 }) {
  const [newInputVal, setNewInputVal] = useState('');
  // conf may be a nested structure for table/array fields — flatten to a single average number
  const resolvedConf = flattenConfidence(conf);
  const pct = resolvedConf != null ? Math.round(resolvedConf * 100) : null;
  const confClass = pct == null ? '' : pct >= confHighThreshold ? 'conf-high' : pct >= confMedThreshold ? 'conf-med' : 'conf-low';
  const confColor = pct == null ? '' : pct >= confHighThreshold ? 'var(--success)' : pct >= confMedThreshold ? 'var(--warn)' : 'var(--danger)';

  const tableData = parseTableData(value, fieldKey);
  const stringArray = parseArrayOfText(value);

  if (tableData) {
    let headers = getTableHeaders(tableData);
    if (headers.length === 0) {
      headers = getDefaultHeaders(fieldKey);
    }

    const handleCellChange = (rowIndex, key, cellValue) => {
      const updatedData = tableData.map((row, rIdx) => {
        if (rIdx === rowIndex) {
          const originalValue = row[key];
          let typedValue = cellValue;
          if (typeof originalValue === 'number') {
            const parsedNum = Number(cellValue);
            if (!isNaN(parsedNum)) {
              typedValue = parsedNum;
            }
          }
          return { ...row, [key]: typedValue };
        }
        return row;
      });

      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updatedData));
      } else {
        onChange(fieldKey, updatedData);
      }
    };

    const handleAddRow = () => {
      const newRow = {};
      headers.forEach(h => {
        newRow[h] = h === 'description' || h === 'date' ? '' : 0;
      });
      const updatedData = [...tableData, newRow];
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updatedData));
      } else {
        onChange(fieldKey, updatedData);
      }
    };

    const handleDeleteRow = (rowIndex) => {
      const updatedData = tableData.filter((_, rIdx) => rIdx !== rowIndex);
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updatedData));
      } else {
        onChange(fieldKey, updatedData);
      }
    };

    return (
      <div className="field-row-table-container" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="field-key" style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-dim)' }}>{label}</div>
          {!isEditing && pct != null && (
            <div className="field-conf" style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 'var(--text-sm)' }}>
              <div className={`conf-dot ${confClass}`} />
              <span style={{ color: confColor }}>{pct}%</span>
            </div>
          )}
        </div>
        
        <div className="table-wrap" style={{ 
          background: 'var(--surface-sunken)', 
          border: '1px solid var(--border)', 
          borderRadius: 'var(--radius-sm)', 
          overflowX: 'auto',
          marginTop: 4
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--card-alt)' }}>
                {headers.map(h => (
                  <th key={h} style={{ 
                    padding: '8px 12px', 
                    fontSize: 11, 
                    fontWeight: 700, 
                    textAlign: 'left', 
                    borderBottom: '1px solid var(--border)',
                    textTransform: 'uppercase',
                    color: 'var(--muted)'
                  }}>
                    {h.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </th>
                ))}
                {isEditing && (
                  <th style={{ 
                    padding: '8px 12px', 
                    fontSize: 11, 
                    fontWeight: 700, 
                    textAlign: 'center', 
                    borderBottom: '1px solid var(--border)',
                    textTransform: 'uppercase',
                    color: 'var(--muted)',
                    width: 50
                  }}>
                    Actions
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {tableData.length === 0 ? (
                <tr>
                  <td colSpan={headers.length + (isEditing ? 1 : 0)} style={{ padding: '16px', textAlign: 'center', color: 'var(--muted)', fontStyle: 'italic' }}>
                    No items in table. Click "Add Row" below to add one.
                  </td>
                </tr>
              ) : (
                tableData.map((row, rIdx) => (
                  <tr key={rIdx} style={{ borderBottom: rIdx === tableData.length - 1 ? 'none' : '1px solid var(--border)', cursor: 'default' }}>
                    {headers.map(h => {
                      const cellVal = row[h];
                      return (
                        <td key={h} style={{ padding: '8px 12px', verticalAlign: 'middle', maxWidth: 'none', overflow: 'visible', whiteSpace: 'normal' }}>
                          {isEditing ? (
                            <input
                              type="text"
                              className="styled-input"
                              value={cellVal ?? ''}
                              onChange={(e) => handleCellChange(rIdx, h, e.target.value)}
                              style={{ 
                                width: '100%', 
                                padding: '4px 8px', 
                                fontSize: 12, 
                                background: 'var(--card-alt)',
                                border: '1px solid var(--border)',
                                borderRadius: 4
                              }}
                            />
                          ) : (
                            cellVal == null ? <span style={{ color: 'var(--muted)' }}>—</span> : String(cellVal)
                          )}
                        </td>
                      );
                    })}
                    {isEditing && (
                      <td style={{ padding: '8px 12px', textAlign: 'center', verticalAlign: 'middle' }}>
                        <button
                          type="button"
                          onClick={() => handleDeleteRow(rIdx)}
                          className="btn btn-icon btn-danger btn-sm"
                          style={{ padding: 4, borderRadius: 4, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
                          title="Delete row"
                        >
                          <Trash2 size={12} />
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {isEditing && (
          <button
            type="button"
            onClick={handleAddRow}
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 4, display: 'inline-flex', alignItems: 'center', gap: 6, width: 'fit-content' }}
          >
            <Plus size={13} /> Add Row
          </button>
        )}
      </div>
    );
  }

  if (stringArray) {
    const handleAddArrayItem = () => {
      if (!newInputVal.trim()) return;
      const updated = [...stringArray, newInputVal.trim()];
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updated));
      } else {
        onChange(fieldKey, updated);
      }
      setNewInputVal('');
    };

    const handleRemoveArrayItem = (index) => {
      const updated = stringArray.filter((_, i) => i !== index);
      if (typeof value === 'string') {
        onChange(fieldKey, JSON.stringify(updated));
      } else {
        onChange(fieldKey, updated);
      }
    };

    return (
      <div className="field-row-array-container" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="field-key" style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-dim)' }}>{label}</div>
          {!isEditing && pct != null && (
            <div className="field-conf" style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 'var(--text-sm)' }}>
              <div className={`conf-dot ${confClass}`} />
              <span style={{ color: confColor }}>{pct}%</span>
            </div>
          )}
        </div>
        
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
          {stringArray.length === 0 ? (
            <span style={{ color: 'var(--muted)', fontStyle: 'italic', fontSize: 12 }}>No items</span>
          ) : (
            stringArray.map((item, idx) => (
              <span key={idx} style={{
                background: 'var(--surface-sunken)',
                color: 'var(--text)',
                padding: '4px 10px',
                borderRadius: '16px',
                border: '1px solid var(--border)',
                fontSize: 12,
                fontWeight: 500,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6
              }}>
                {item}
                {isEditing && (
                  <button
                    type="button"
                    onClick={() => handleRemoveArrayItem(idx)}
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
                    <X size={12} />
                  </button>
                )}
              </span>
            ))
          )}
        </div>

        {isEditing && (
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            <input
              type="text"
              placeholder="Add item..."
              value={newInputVal}
              onChange={(e) => setNewInputVal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddArrayItem();
                }
              }}
              style={{
                flexGrow: 1,
                padding: '4px 8px',
                fontSize: 12,
                background: 'var(--card-alt)',
                border: '1px solid var(--border)',
                borderRadius: 4
              }}
            />
            <button
              type="button"
              onClick={handleAddArrayItem}
              className="btn btn-ghost btn-sm"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, height: 26, padding: '0 8px' }}
            >
              <Plus size={12} /> Add
            </button>
          </div>
        )}
      </div>
    );
  }

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
          (() => {
            const renderedText = typeof value === 'object' ? 
              <code style={{ fontSize: 11, background: 'transparent', color: 'inherit' }}>{JSON.stringify(value)}</code> : 
              String(value);
            
            if (!isEditing && pct != null && pct < fieldHighlightThreshold) {
              return (
                <span style={{ 
                  background: 'rgba(245, 158, 11, 0.12)', 
                  color: 'var(--warn)', 
                  padding: '3px 8px', 
                  borderRadius: '4px',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  fontWeight: 500,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6
                }}>
                  {renderedText}
                </span>
              );
            }
            return renderedText;
          })()
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

function renderFields(data, isEditing, editedData, onChange, confidences = {}, confidenceMode = 'word', confHighThreshold = 90, confMedThreshold = 70, fieldHighlightThreshold = 95, fieldThresholds = {}) {
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
          conf={(confidenceMode === 'word' || confidenceMode === 'both') ? confidences[k] : null}
          confHighThreshold={confHighThreshold}
          confMedThreshold={confMedThreshold}
          fieldHighlightThreshold={fieldThresholds[k] ?? fieldHighlightThreshold}
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

export function Extraction() {
  const { completedDocs, confidenceMode, fieldHighlightThreshold, autoApproveThreshold, confHighThreshold, confMedThreshold } = useApp();
  const { refresh } = useDocumentList();
  const [activeId, setActiveId] = useState(null);
  const [extracted, setExtracted] = useState(null);
  const [loadingEx, setLoadingEx] = useState(false);
  const [error, setError] = useState(null);
  const [viewerExpanded, setViewerExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedData, setEditedData] = useState({});
  const [saving, setSaving] = useState(false);
  const [templates, setTemplates] = useState({});
  const { toast } = useApp();
  const navigate = useNavigate();

  useEffect(() => {
    getTemplates()
      .then(data => setTemplates(data || {}))
      .catch(err => console.error('Failed to load templates:', err));
  }, []);

  const wordConf = extracted ? getAverageWordConfidence(extracted) : 0;
  const pageConf = extracted ? (extracted.confidence_score ?? 0) : 0;

  const displayConfidence = extracted
    ? (confidenceMode === 'page'
        ? pageConf
        : confidenceMode === 'word'
        ? wordConf
        : Math.min(wordConf, pageConf))
    : 0;

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

  const fieldThresholds = useMemo(() => {
    const map = {};
    if (activeDoc?.doc_type) {
      const docTypeKey = activeDoc.doc_type.toLowerCase().replace(/\s+/g, '_');
      const fields = templates[docTypeKey] || [];
      fields.forEach(f => {
        if (f.confidence_threshold !== undefined && f.confidence_threshold !== null) {
          map[f.key] = f.confidence_threshold;
        }
      });
    }
    return map;
  }, [templates, activeDoc?.doc_type]);

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
              background: displayConfidence >= autoApproveThreshold / 100
                ? 'rgba(16,185,129,0.06)'
                : 'rgba(245,158,11,0.06)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{
                fontSize: 12, fontWeight: 600,
                color: displayConfidence >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
              }}>
                {displayConfidence >= autoApproveThreshold / 100 ? (
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
                {confidenceMode === 'word' && (
                  <>
                    Word Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(wordConf * 100)}%</strong>
                  </>
                )}
                {confidenceMode === 'page' && (
                  <>
                    Page Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(pageConf * 100)}%</strong>
                  </>
                )}
                {confidenceMode === 'both' && (
                  <>
                    Word Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(wordConf * 100)}%</strong> · Page Conf: <strong style={{ color: 'var(--text)' }}>{Math.round(pageConf * 100)}%</strong>
                  </>
                )}
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
                  {confidenceMode === 'word' && (
                    <>
                      Word Confidence: <span style={{ color: wordConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(wordConf * 100)}%</span>
                    </>
                  )}
                  {confidenceMode === 'page' && (
                    <>
                      Page Confidence: <span style={{ color: pageConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(pageConf * 100)}%</span>
                    </>
                  )}
                  {confidenceMode === 'both' && (
                    <>
                      Word: <span style={{ color: wordConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(wordConf * 100)}%</span> · Page: <span style={{ color: pageConf >= autoApproveThreshold / 100 ? 'var(--success)' : 'var(--warn)', fontWeight: 600 }}>{Math.round(pageConf * 100)}%</span>
                    </>
                  )}
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
                renderFields(extracted.validated_data, isEditing, editedData, handleFieldChange, extracted.raw_extracted?.field_confidences || {}, confidenceMode, confHighThreshold, confMedThreshold, fieldHighlightThreshold, fieldThresholds)
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
