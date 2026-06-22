import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Copy, Download, ChevronDown, ChevronRight, Maximize2, ExternalLink, FileText, FileSearch, CheckCircle2, AlertTriangle, Edit2, Check, X, Trash2, Plus, ShieldCheck, UserCircle2, PenTool, ZoomIn, Upload, RotateCcw, Shield, Eye, Fingerprint, Users } from 'lucide-react';
import { getExtractedData, getDocumentFileUrl, updateExtractedData, getTemplates, verifySignature } from '../api/client';
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

// Keys that hold KYC image data — excluded from regular field rendering
const KYC_IMAGE_KEYS = new Set(['signature_image', 'photo_image', 'signature_detected', 'photo_detected']);


/** Score classification helper */
function getScoreClass(score, max = 100) {
  const pct = max === 1 ? score * 100 : score;
  if (pct >= 75) return 'high';
  if (pct >= 55) return 'medium';
  return 'low';
}

/** Score bar sub-component */
function ScoreBar({ label, value, max = 100, suffix = '' }) {
  const pct = max === 1 ? (value * 100) : (value / max * 100);
  const displayVal = max === 1 ? value.toFixed(4) : Math.round(value);
  const cls = getScoreClass(value, max);
  return (
    <div className="score-bar-row">
      <div className="score-bar-label">{label}</div>
      <div className="score-bar-track">
        <div className={`score-bar-fill ${cls}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <div className="score-bar-value" style={{ color: cls === 'high' ? '#059669' : cls === 'medium' ? '#d97706' : '#dc2626' }}>
        {displayVal}{suffix}
      </div>
    </div>
  );
}

/** Analysis dimension row */
function AnalysisRow({ name, data }) {
  if (!data) return null;
  const score = data.score ?? 0;
  const cls = getScoreClass(score);
  return (
    <div className="analysis-row">
      <div className="analysis-dimension">{name}</div>
      <div className={`analysis-score ${cls}`}>{score}</div>
      <div className="analysis-observation">{data.observation || '—'}</div>
    </div>
  );
}

/** Authenticity flag row */
function FlagRow({ label, flagged }) {
  return (
    <div className="flag-row">
      <div className={`flag-indicator ${flagged ? 'danger' : 'safe'}`} />
      <div className="flag-label">{label}{flagged ? ' — Detected' : ' — Clear'}</div>
    </div>
  );
}

/** Full verdict panel for signature/photo verification results */
function SignatureVerdictPanel({ result, verificationType, onReset }) {
  if (!result) return null;

  const judge = result.judge || {};
  const dino = result.dino || {};
  const vision = result.mistral_vision || {};
  const scores = judge.scores || {};
  const verdict = (judge.verdict || result.verdict || 'unknown').toLowerCase();
  const confidence = judge.confidence ?? 0;
  const recommendation = judge.recommendation || '';
  const summary = judge.summary || '';

  const verdictIcon = verdict === 'genuine' ? <CheckCircle2 size={16} /> : verdict === 'uncertain' ? <AlertTriangle size={16} /> : <Shield size={16} />;
  const verdictLabel = verdict === 'genuine' ? 'GENUINE' : verdict === 'uncertain' ? 'UNCERTAIN' : 'FORGED';

  const recClass = recommendation.toLowerCase().includes('accept') ? 'accept'
    : recommendation.toLowerCase().includes('review') ? 'review' : 'reject';
  const recIcon = recClass === 'accept' ? <CheckCircle2 size={12} /> : recClass === 'review' ? <Eye size={12} /> : <Shield size={12} />;

  const [showStructural, setShowStructural] = useState(false);
  const [showSpatial, setShowSpatial] = useState(false);
  const [showFlags, setShowFlags] = useState(false);
  const [showUnique, setShowUnique] = useState(false);

  const structural = judge.structural_analysis || vision.structural_analysis || {};
  const spatial = judge.spatial_analysis || vision.spatial_analysis || {};
  const flags = judge.authenticity_flags || vision.authenticity_flags || {};
  const unique = judge.unique_features || vision.unique_features || {};

  return (
    <div className="verdict-panel">
      {/* Header with verdict badge */}
      <div className={`verdict-header ${verdict}`}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className={`verdict-badge ${verdict}`}>
            {verdictIcon} {verdictLabel}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            Confidence: <strong style={{ color: 'var(--text)' }}>{confidence}%</strong>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Fingerprint size={10} />
            {verificationType === 'signature' ? 'Signature' : 'Photo'} Verification
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onReset} style={{ fontSize: 10, padding: '2px 8px', gap: 3 }}>
            <RotateCcw size={10} /> Reset
          </button>
        </div>
      </div>

      {/* Score Breakdown */}
      <div className="score-bar-container">
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 2 }}>Score Breakdown</div>
        <ScoreBar label="DINOv2" value={scores.embedding_cosine_score ?? dino.score ?? 0} max={1} />
        <ScoreBar label="LLM Visual" value={scores.llm_visual_score ?? vision.llm_visual_score ?? 0} max={100} />
        <ScoreBar label="Combined" value={scores.combined_weighted_score ?? 0} max={100} />
        {(scores.penalties_applied != null && scores.penalties_applied > 0) && (
          <div style={{ fontSize: 10, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
            <AlertTriangle size={10} />
            {scores.penalties_applied} point penalty applied
            {scores.penalty_reasons?.length > 0 && ` (${scores.penalty_reasons.join(', ')})`}
          </div>
        )}
      </div>

      {/* Structural Analysis Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowStructural(s => !s)}
        >
          {showStructural ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Structural Analysis (5 dimensions)
        </div>
        {showStructural && (
          <div style={{ padding: '0 18px 12px' }}>
            <AnalysisRow name="Stroke Flow" data={structural.stroke_flow} />
            <AnalysisRow name="Stroke Thickness" data={structural.stroke_thickness} />
            <AnalysisRow name="Loop Morphology" data={structural.loop_morphology} />
            <AnalysisRow name="Connectivity" data={structural.connectivity_pattern} />
            <AnalysisRow name="Entry/Exit" data={structural.entry_exit_strokes} />
          </div>
        )}
      </div>

      {/* Spatial Analysis Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowSpatial(s => !s)}
        >
          {showSpatial ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Spatial Analysis (4 dimensions)
        </div>
        {showSpatial && (
          <div style={{ padding: '0 18px 12px' }}>
            <AnalysisRow name="Slant Angle" data={spatial.slant_angle} />
            <AnalysisRow name="Baseline" data={spatial.baseline_alignment} />
            <AnalysisRow name="Proportions" data={spatial.proportions} />
            <AnalysisRow name="Spacing" data={spatial.spacing} />
          </div>
        )}
      </div>

      {/* Authenticity Flags Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowFlags(s => !s)}
        >
          {showFlags ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Authenticity Flags
        </div>
        {showFlags && (
          <div style={{ padding: '0 18px 12px' }}>
            <FlagRow label="Tremor / Shakiness" flagged={flags.tremor_detected} />
            <FlagRow label="Retouching" flagged={flags.retouching_detected} />
            <FlagRow label="Hesitation Marks" flagged={flags.hesitation_marks} />
            <FlagRow label="Unnatural Slowness" flagged={flags.unnatural_slowness} />
            <FlagRow label="Pen Lift Mismatch" flagged={flags.pen_lift_mismatch} />
            {flags.flag_details && (
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6, fontStyle: 'italic', lineHeight: 1.5 }}>
                {flags.flag_details}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Unique Features Accordion */}
      <div style={{ borderTop: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowUnique(s => !s)}
        >
          {showUnique ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Unique Features
        </div>
        {showUnique && (
          <div style={{ padding: '0 18px 12px' }}>
            <div className="flag-row">
              <div className={`flag-indicator ${unique.idiosyncratic_marks_present ? 'safe' : 'danger'}`} />
              <div className="flag-label">Idiosyncratic marks {unique.idiosyncratic_marks_present ? 'present' : 'not found'}</div>
            </div>
            {unique.idiosyncratic_marks_present && (
              <div className="flag-row">
                <div className={`flag-indicator ${unique.marks_match ? 'safe' : 'danger'}`} />
                <div className="flag-label">Marks {unique.marks_match ? 'match' : 'do not match'}</div>
              </div>
            )}
            {unique.details && (
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6, fontStyle: 'italic', lineHeight: 1.5 }}>
                {unique.details}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Summary */}
      {summary && (
        <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.6, fontStyle: 'italic' }}>
          {summary}
        </div>
      )}

      {/* Override notice */}
      {judge.override_applied && (
        <div style={{ padding: '8px 18px', borderTop: '1px solid var(--border)', fontSize: 10, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(239,68,68,0.03)' }}>
          <AlertTriangle size={10} />
          Override applied: {judge.override_reason}
        </div>
      )}

      {/* Recommendation */}
      {recommendation && (
        <div className={`recommendation-banner ${recClass}`}>
          {recIcon} {recommendation}
        </div>
      )}
    </div>
  );
}

/** Full verdict panel for face/photo verification results (multi-agent pipeline) */
function FaceVerdictPanel({ result, onReset }) {
  if (!result) return null;

  const mod1 = result.module1 || {};
  const mod2 = result.module2 || {};
  const mod3 = result.module3 || {};
  const outputCode = result.output_code;
  const verdict = (result.verdict || 'needs_review').toLowerCase();
  const verdictLabel = result.verdict_label || 'NEEDS REVIEW';

  const verdictIcon = verdict === 'same_person' ? <CheckCircle2 size={16} /> : verdict === 'different_person' ? <Shield size={16} /> : <AlertTriangle size={16} />;
  const verdictClass = verdict === 'same_person' ? 'genuine' : verdict === 'different_person' ? 'forged' : 'uncertain';

  const [showMod1, setShowMod1] = useState(false);
  const [showMod2, setShowMod2] = useState(false);
  const [showMod3, setShowMod3] = useState(false);

  const getSignalBadge = (signal) => {
    if (!signal) return null;
    const cls = signal === 'supports_same' ? 'face-signal-same' : signal === 'supports_different' ? 'face-signal-diff' : 'face-signal-inc';
    const label = signal === 'supports_same' ? 'Supports Same' : signal === 'supports_different' ? 'Supports Different' : 'Inconclusive';
    return <span className={`face-signal-badge ${cls}`}>{label}</span>;
  };

  const renderFeaturePoints = (label, same, diff, confidence) => (
    <div className="face-feature-block">
      <div className="face-feature-header">
        <span className="face-feature-name">{label}</span>
        {confidence && <span className={`face-conf-badge ${confidence}`}>{confidence}</span>}
      </div>
      {same && same.length > 0 && (
        <div className="face-points-list same">
          <span className="face-points-label">✓ Similar:</span>
          {same.map((p, i) => <span key={i} className="face-point">{p}</span>)}
        </div>
      )}
      {diff && diff.length > 0 && (
        <div className="face-points-list diff">
          <span className="face-points-label">✗ Different:</span>
          {diff.map((p, i) => <span key={i} className="face-point">{p}</span>)}
        </div>
      )}
    </div>
  );

  return (
    <div className="verdict-panel" style={{ marginTop: 12 }}>
      {/* Header */}
      <div className={`verdict-header ${verdictClass}`}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className={`verdict-badge ${verdictClass}`}>
            {verdictIcon} {verdictLabel}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            Score: <strong style={{ color: 'var(--text)' }}>{outputCode}/5</strong>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Users size={10} /> Face Verification
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onReset} style={{ fontSize: 10, padding: '2px 8px', gap: 3 }}>
            <RotateCcw size={10} /> Reset
          </button>
        </div>
      </div>

      {/* Module Signals Overview */}
      <div style={{ padding: '12px 18px', display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>Agent Signals</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>M1: {getSignalBadge(mod1.signal)}</span>
          <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>M2: {getSignalBadge(mod2.signal)}</span>
          <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>M3: {getSignalBadge(mod3.signal)}</span>
        </div>
      </div>

      {/* Module 1 — Morphology Part 1 */}
      <div style={{ borderBottom: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowMod1(s => !s)}
        >
          {showMod1 ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Module 1 — Face Geometry / Eyes / Nose
          <span style={{ marginLeft: 'auto' }}>{getSignalBadge(mod1.signal)}</span>
        </div>
        {showMod1 && (
          <div style={{ padding: '0 18px 12px' }}>
            {mod1.features?.facial_geometry && renderFeaturePoints('Facial Geometry', mod1.features.facial_geometry.same_points, mod1.features.facial_geometry.different_points, mod1.features.facial_geometry.confidence)}
            {mod1.features?.eyes && renderFeaturePoints('Eyes', mod1.features.eyes.same_points, mod1.features.eyes.different_points, mod1.features.eyes.confidence)}
            {mod1.features?.nose && renderFeaturePoints('Nose', mod1.features.nose.same_points, mod1.features.nose.different_points, mod1.features.nose.confidence)}
            {mod1.asymmetry && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Asymmetry</span></div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                  <div>Image A: {mod1.asymmetry.image_a || '—'}</div>
                  <div>Image B: {mod1.asymmetry.image_b || '—'}</div>
                  <div>Match: <strong>{mod1.asymmetry.match || '—'}</strong></div>
                </div>
              </div>
            )}
            {mod1.anchor_features && mod1.anchor_features.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
                <strong>Anchor features:</strong> {mod1.anchor_features.join(', ')}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Module 2 — Morphology Part 2 */}
      <div style={{ borderBottom: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowMod2(s => !s)}
        >
          {showMod2 ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Module 2 — Mouth / Ears / Jaw / Secondary
          <span style={{ marginLeft: 'auto' }}>{getSignalBadge(mod2.signal)}</span>
        </div>
        {showMod2 && (
          <div style={{ padding: '0 18px 12px' }}>
            {mod2.features?.mouth_lips && renderFeaturePoints('Mouth & Lips', mod2.features.mouth_lips.same_points, mod2.features.mouth_lips.different_points, mod2.features.mouth_lips.confidence)}
            {mod2.features?.ears && renderFeaturePoints('Ears', mod2.features.ears.same_points, mod2.features.ears.different_points, mod2.features.ears.confidence)}
            {mod2.features?.jaw_chin_secondary && renderFeaturePoints('Jaw / Chin / Secondary', mod2.features.jaw_chin_secondary.same_points, mod2.features.jaw_chin_secondary.different_points, mod2.features.jaw_chin_secondary.confidence)}
            {mod2.variability_factors && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Variability Factors</span></div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4 }}>
                  {Object.entries(mod2.variability_factors).map(([k, v]) => (
                    <span key={k} className={`face-variability-chip ${v === 'none' ? 'ok' : v === 'mild' ? 'mild' : 'sig'}`}>
                      {k.replace(/_/g, ' ')}: {v}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Module 3 — Age Variation */}
      <div style={{ borderBottom: '1px solid var(--border)' }}>
        <div
          style={{ padding: '10px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          onClick={() => setShowMod3(s => !s)}
        >
          {showMod3 ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          Module 3 — Age Variation Analysis
          <span style={{ marginLeft: 'auto' }}>{getSignalBadge(mod3.signal)}</span>
        </div>
        {showMod3 && (
          <div style={{ padding: '0 18px 12px' }}>
            {mod3.estimated_age_gap && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Estimated Age Gap</span></div>
                <span className="face-age-gap-badge">{(mod3.estimated_age_gap || '').replace(/_/g, ' ')}</span>
                {mod3.age_cues_used && mod3.age_cues_used.length > 0 && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>Cues: {mod3.age_cues_used.join(', ')}</div>
                )}
              </div>
            )}
            {mod3.stable_features && (
              <div className="face-feature-block">
                <div className="face-feature-header">
                  <span className="face-feature-name">Stable Features (Bone-Anchored)</span>
                  {mod3.stable_features.confidence && <span className={`face-conf-badge ${mod3.stable_features.confidence}`}>{mod3.stable_features.confidence}</span>}
                </div>
                {mod3.stable_features.consistent && mod3.stable_features.consistent.length > 0 && (
                  <div className="face-points-list same">
                    <span className="face-points-label">✓ Consistent:</span>
                    {mod3.stable_features.consistent.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
                {mod3.stable_features.inconsistent && mod3.stable_features.inconsistent.length > 0 && (
                  <div className="face-points-list diff">
                    <span className="face-points-label">✗ Inconsistent:</span>
                    {mod3.stable_features.inconsistent.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
              </div>
            )}
            {mod3.soft_tissue_differences && (
              <div className="face-feature-block">
                <div className="face-feature-header"><span className="face-feature-name">Soft Tissue Differences</span></div>
                {mod3.soft_tissue_differences.age_explained && mod3.soft_tissue_differences.age_explained.length > 0 && (
                  <div className="face-points-list same">
                    <span className="face-points-label">Age-explained:</span>
                    {mod3.soft_tissue_differences.age_explained.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
                {mod3.soft_tissue_differences.biologically_inconsistent && mod3.soft_tissue_differences.biologically_inconsistent.length > 0 && (
                  <div className="face-points-list diff">
                    <span className="face-points-label">⚠ Biologically inconsistent:</span>
                    {mod3.soft_tissue_differences.biologically_inconsistent.map((p, i) => <span key={i} className="face-point">{p}</span>)}
                  </div>
                )}
              </div>
            )}
            {mod3.non_age_explained_differences && mod3.non_age_explained_differences.length > 0 && (
              <div style={{ padding: '8px 0', fontSize: 11, color: 'var(--danger)', display: 'flex', alignItems: 'flex-start', gap: 4 }}>
                <AlertTriangle size={11} style={{ flexShrink: 0, marginTop: 1 }} />
                <span>Non-age-explained differences: {mod3.non_age_explained_differences.join(', ')}</span>
              </div>
            )}
            {mod3.aging_trajectory && (
              <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-dim)' }}>
                Aging trajectory: <strong>{mod3.aging_trajectory}</strong>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recommendation */}
      {outputCode && (
        <div className={`recommendation-banner ${outputCode === 5 ? 'accept' : outputCode === 3 ? 'review' : 'reject'}`}>
          {outputCode === 5 ? <CheckCircle2 size={12} /> : outputCode === 3 ? <Eye size={12} /> : <Shield size={12} />}
          {outputCode === 5 ? 'Accept — Same Person' : outputCode === 3 ? 'Manual Review Required' : 'Reject — Different Person'}
        </div>
      )}
    </div>
  );
}

function renderFields(data, isEditing, editedData, onChange, confidences = {}, confidenceMode = 'word', confHighThreshold = 90, confMedThreshold = 70, fieldHighlightThreshold = 95, fieldThresholds = {}) {
  if (!data || typeof data !== 'object') return null;
  const groups = {};
  const renderSource = isEditing ? editedData : data;
  Object.entries(renderSource).forEach(([k, v]) => {
    // Skip KYC image fields — they are rendered separately in the Identity Verification section
    if (KYC_IMAGE_KEYS.has(k)) return;
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


/** KYC Image Card — glassmorphic card for displaying cropped signature/photo */
function KycImageCard({ label, icon: Icon, base64Data, detected, accentColor, verificationType, documentId, verificationResult, onVerify, isVerifying }) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [refFile, setRefFile] = useState(null);
  const [refPreview, setRefPreview] = useState(null);
  const fileInputRef = React.useRef(null);

  const handleDownload = () => {
    if (!base64Data) return;
    const a = document.createElement('a');
    a.href = `data:image/png;base64,${base64Data}`;
    a.download = `${label.toLowerCase().replace(/\s+/g, '_')}.png`;
    a.click();
  };

  const handleFileSelect = (file) => {
    if (!file || !file.type.startsWith('image/')) return;
    setRefFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setRefPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    handleFileSelect(file);
  };

  const handleVerifyClick = () => {
    if (refFile && onVerify) {
      onVerify(refFile, verificationType);
    }
  };

  const handleReset = () => {
    setRefFile(null);
    setRefPreview(null);
    setShowUpload(false);
  };

  if (!detected || !base64Data) {
    return (
      <div style={{
        flex: 1,
        minWidth: 200,
        padding: '20px 16px',
        borderRadius: 'var(--radius)',
        border: '1.5px dashed var(--border)',
        background: 'var(--surface-sunken)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        textAlign: 'center',
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: '50%',
          background: 'rgba(107,114,128,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Icon size={20} style={{ color: 'var(--muted)', opacity: 0.6 }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>{label}</span>
        <span style={{
          fontSize: 10, color: 'var(--warn)',
          background: 'rgba(245,158,11,0.08)',
          border: '1px solid rgba(245,158,11,0.2)',
          padding: '2px 8px', borderRadius: 99,
          display: 'inline-flex', alignItems: 'center', gap: 4
        }}>
          <AlertTriangle size={10} /> Not Detected
        </span>
      </div>
    );
  }

  const isPhotoType = verificationType === 'photo';

  return (
    <>
      <div className={isVerifying ? 'kyc-card-verifying' : ''} style={{
        flex: 1,
        minWidth: 200,
        padding: 0,
        borderRadius: 'var(--radius)',
        border: `1.5px solid ${accentColor}25`,
        background: `linear-gradient(135deg, ${accentColor}08, ${accentColor}03)`,
        backdropFilter: 'blur(12px)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
      }}
        onMouseEnter={(e) => {
          if (!isVerifying) {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = `0 8px 24px ${accentColor}15`;
          }
        }}
        onMouseLeave={(e) => {
          if (!isVerifying) {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }
        }}
      >
        {/* Header */}
        <div style={{
          padding: '8px 12px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: `1px solid ${accentColor}15`,
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: accentColor, display: 'flex', alignItems: 'center', gap: 5, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            <Icon size={12} /> {label}
          </span>
          <span style={{
            fontSize: 9, fontWeight: 600,
            color: 'var(--success)',
            background: 'rgba(16,185,129,0.08)',
            border: '1px solid rgba(16,185,129,0.2)',
            padding: '1px 6px', borderRadius: 99,
            display: 'inline-flex', alignItems: 'center', gap: 3
          }}>
            <CheckCircle2 size={8} /> Detected
          </span>
        </div>

        {/* Image */}
        <div
          style={{
            padding: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 100,
            cursor: 'pointer',
            position: 'relative',
          }}
          onClick={() => setLightboxOpen(true)}
          title="Click to expand"
        >
          <img
            src={`data:image/png;base64,${base64Data}`}
            alt={label}
            style={{
              maxWidth: '100%',
              maxHeight: 140,
              objectFit: 'contain',
              borderRadius: 4,
              border: '1px solid var(--border)',
            }}
          />
          <div style={{
            position: 'absolute', bottom: 16, right: 16,
            background: 'rgba(0,0,0,0.5)', color: '#fff',
            borderRadius: '50%', width: 24, height: 24,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: 0.7, transition: 'opacity 0.2s',
          }}>
            <ZoomIn size={12} />
          </div>
        </div>

        {/* Verification Loading State */}
        {isVerifying && (
          <div className="verification-loading">
            <div className="verify-spinner" />
            <div className="verify-text">Analyzing {verificationType}...</div>
            <div className="verify-subtext">{verificationType === 'photo' ? 'Running 3 forensic face analysis agents in parallel' : 'Running DINOv2 embeddings and Mistral Vision forensic analysis'}</div>
          </div>
        )}

        {/* Upload area (when verify mode is active and not currently verifying) */}
        {showUpload && !isVerifying && !verificationResult && (
          <div style={{ padding: '0 12px 8px' }}>
            <div
              className={`verify-dropzone ${dragOver ? 'dragover' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="verify-drop-icon">
                <Upload size={14} />
              </div>
              <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-dim)' }}>
                Drop reference {verificationType} or click to browse
              </span>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => handleFileSelect(e.target.files?.[0])}
              />
            </div>

            {/* Reference preview */}
            {refPreview && (
              <div className="ref-preview">
                <img src={refPreview} alt="Reference" />
                <span className="ref-name">{refFile?.name}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); setRefFile(null); setRefPreview(null); }}
                  style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 0, display: 'flex' }}
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 6, marginTop: 8, justifyContent: 'flex-end' }}>
              <button
                className="btn btn-ghost btn-sm"
                onClick={(e) => { e.stopPropagation(); handleReset(); }}
                style={{ fontSize: 10, padding: '2px 8px' }}
              >
                Cancel
              </button>
              {isPhotoType ? (
                <button
                  className="btn btn-primary btn-sm"
                  disabled={!refFile}
                  onClick={(e) => { e.stopPropagation(); handleVerifyClick(); }}
                  style={{ fontSize: 10, padding: '2px 10px', gap: 4, background: '#3b82f6', borderColor: '#3b82f6' }}
                >
                  <Users size={10} /> Run Face Verification
                </button>
              ) : (
                <button
                  className="btn btn-primary btn-sm"
                  disabled={!refFile}
                  onClick={(e) => { e.stopPropagation(); handleVerifyClick(); }}
                  style={{ fontSize: 10, padding: '2px 10px', gap: 4, background: '#a855f7', borderColor: '#a855f7' }}
                >
                  <Fingerprint size={10} /> Run Verification
                </button>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{
          padding: '6px 12px 8px',
          display: 'flex', gap: 6, justifyContent: 'flex-end',
          borderTop: `1px solid ${accentColor}10`,
        }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleDownload}
            style={{ fontSize: 10, padding: '2px 8px', gap: 4 }}
          >
            <Download size={10} /> Download
          </button>
          {!verificationResult && !showUpload && !isVerifying && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowUpload(true)}
              style={{ fontSize: 10, padding: '2px 8px', gap: 4, color: '#a855f7', borderColor: 'rgba(168,85,247,0.25)' }}
            >
              <Fingerprint size={10} /> Verify
            </button>
          )}
          {verificationResult && (
            <span style={{
              fontSize: 9, fontWeight: 600,
              padding: '2px 8px', borderRadius: 99,
              display: 'inline-flex', alignItems: 'center', gap: 3,
              ...(verificationResult.verdict === 'genuine'
                ? { color: '#059669', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }
                : verificationResult.verdict === 'uncertain'
                ? { color: '#d97706', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }
                : { color: '#dc2626', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' })
            }}>
              {verificationResult.verdict === 'genuine' ? <CheckCircle2 size={8} /> : verificationResult.verdict === 'uncertain' ? <AlertTriangle size={8} /> : <Shield size={8} />}
              {(verificationResult.verdict || 'unknown').toUpperCase()}
            </span>
          )}
        </div>
      </div>

      {/* Lightbox modal */}
      {lightboxOpen && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 1100,
            background: 'rgba(8,11,20,0.92)', backdropFilter: 'blur(20px)',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            animation: 'fade-in 150ms ease',
            cursor: 'pointer',
          }}
          onClick={() => setLightboxOpen(false)}
        >
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            position: 'absolute', top: 20, right: 20,
          }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={(e) => { e.stopPropagation(); handleDownload(); }}
              style={{ color: '#fff', borderColor: 'rgba(255,255,255,0.2)', fontSize: 11, gap: 5 }}
            >
              <Download size={12} /> Download
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setLightboxOpen(false)}
              style={{ color: '#fff', borderColor: 'rgba(255,255,255,0.2)', fontSize: 11 }}
            >
              ✕ Close
            </button>
          </div>
          <div style={{
            fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.7)',
            marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <Icon size={14} /> {label}
          </div>
          <img
            src={`data:image/png;base64,${base64Data}`}
            alt={label}
            style={{
              maxWidth: '90vw', maxHeight: '80vh',
              objectFit: 'contain', borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.1)',
              boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
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
  const [sigVerifying, setSigVerifying] = useState(false);
  const [sigResult, setSigResult] = useState(null);
  const [photoVerifying, setPhotoVerifying] = useState(false);
  const [photoResult, setPhotoResult] = useState(null);
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
        // Load persisted verification results
        setSigResult(data?.signature_verification || null);
        setPhotoResult(data?.photo_verification || null);
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

  const handleVerify = async (file, type) => {
    if (!activeId) return;
    const setVerifying = type === 'signature' ? setSigVerifying : setPhotoVerifying;
    const setResult = type === 'signature' ? setSigResult : setPhotoResult;
    setVerifying(true);
    try {
      const result = await verifySignature(activeId, file, type);
      setResult(result);
      toast(`${type === 'signature' ? 'Signature' : 'Photo'} verification complete: ${(result.verdict || 'unknown').toUpperCase()}`, 
        result.verdict === 'genuine' ? 'success' : result.verdict === 'uncertain' ? 'warn' : 'error'
      );
    } catch (err) {
      toast(`Verification failed: ${err.message}`, 'error');
    } finally {
      setVerifying(false);
    }
  };

  const handleResetVerification = (type) => {
    if (type === 'signature') {
      setSigResult(null);
    } else {
      setPhotoResult(null);
    }
  };

  const activeDoc = completedDocs.find((d) => d.id === activeId);

  const fieldThresholds = useMemo(() => {
    const map = {};
    if (activeDoc?.doc_type) {
      const docTypeKey = activeDoc.doc_type.toLowerCase().replace(/\s+/g, '_');
      const raw = templates[docTypeKey];
      // Handle both old (list) and new ({fields, is_kyc}) formats
      const fields = Array.isArray(raw) ? raw : (raw?.fields || []);
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
              {/* ── Identity Verification Section (KYC signature/photo) ── */}
              {extracted.validated_data && (
                extracted.validated_data.signature_image || extracted.validated_data.photo_image ||
                extracted.validated_data.signature_detected !== undefined || extracted.validated_data.photo_detected !== undefined
              ) && (
                <FieldGroup title="Identity Verification">
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    marginBottom: 10, padding: '6px 0',
                  }}>
                    <ShieldCheck size={14} style={{ color: 'var(--accent)' }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)' }}>
                      KYC Document — Signature & Photo Extraction
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <KycImageCard
                      label="Signature"
                      icon={PenTool}
                      base64Data={extracted.validated_data.signature_image}
                      detected={extracted.validated_data.signature_detected}
                      accentColor="#7c3aed"
                      verificationType="signature"
                      documentId={activeId}
                      verificationResult={sigResult}
                      onVerify={handleVerify}
                      isVerifying={sigVerifying}
                    />
                    <KycImageCard
                      label="Photo"
                      icon={UserCircle2}
                      base64Data={extracted.validated_data.photo_image}
                      detected={extracted.validated_data.photo_detected}
                      accentColor="#3b82f6"
                      verificationType="photo"
                      documentId={activeId}
                      verificationResult={photoResult}
                      onVerify={handleVerify}
                      isVerifying={photoVerifying}
                    />
                  </div>

                  {/* Signature Verification Verdict Panel */}
                  {sigResult && (
                    <SignatureVerdictPanel
                      result={sigResult}
                      verificationType="signature"
                      onReset={() => handleResetVerification('signature')}
                    />
                  )}

                  {/* Photo Verification Verdict Panel (Face multi-agent pipeline) */}
                  {photoResult && (
                    <FaceVerdictPanel
                      result={photoResult}
                      onReset={() => handleResetVerification('photo')}
                    />
                  )}
                </FieldGroup>
              )}

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
