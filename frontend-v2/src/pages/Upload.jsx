import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud, X, FileText, Image, File,
  CheckCircle2, ScanSearch, Brain, ShieldCheck, UserCheck, Share2,
  XCircle, Layers, RefreshCw, AlertTriangle, Zap,
} from 'lucide-react';
import { uploadDocumentsBatch } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentPoller } from '../hooks/useDocumentPoller';

// ─── Constants ────────────────────────────────────────────────────────────────
const ALLOWED = {
  'application/pdf': { ext: 'PDF', icon: FileText, color: '#ef4444' },
  'image/jpeg':      { ext: 'JPG', icon: Image,    color: '#f59e0b' },
  'image/png':       { ext: 'PNG', icon: Image,    color: '#10b981' },
  'image/webp':      { ext: 'WEBP', icon: Image,   color: '#06b6d4' },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                     { ext: 'DOCX', icon: File,    color: '#3b82f6' },
};
const MAX_BATCH = 20;

// ─── QueueItem ────────────────────────────────────────────────────────────────
function QueueItem({ item, onRemove, locked }) {
  const meta   = ALLOWED[item.file.type] || {};
  const Icon   = meta.icon || File;
  const isDone    = item.status === 'done';
  const isError   = item.status === 'error';
  const isUploading = item.status === 'uploading';

  const thumbStyle = isDone
    ? { background: 'var(--success-dim)', borderColor: 'var(--success-border)' }
    : isError
    ? { background: 'var(--danger-dim)', borderColor: 'var(--danger-border)' }
    : isUploading
    ? { background: 'var(--accent-dim)', borderColor: 'rgba(79,110,247,0.3)' }
    : {};

  const iconColor = isDone ? 'var(--success)'
    : isError      ? 'var(--danger)'
    : isUploading  ? 'var(--accent)'
    : (meta.color  || 'var(--accent)');

  return (
    <div
      className="doc-card"
      style={
        isDone  ? { borderColor: 'var(--success-border)', background: 'rgba(16,185,129,0.03)' }
        : isError ? { borderColor: 'var(--danger-border)', background: 'rgba(239,68,68,0.03)' }
        : {}
      }
    >
      {/* Thumb */}
      <div className="doc-thumb" style={thumbStyle}>
        <Icon size={18} color={iconColor} />
      </div>

      {/* Info */}
      <div className="doc-info">
        <div className="doc-name">{item.file.name}</div>
        <div className="doc-meta">
          {(item.file.size / 1024).toFixed(0)} KB
          {meta.ext && <span style={{ marginLeft: 6, opacity: 0.7 }}>· {meta.ext}</span>}
          {isError && (
            <span style={{ color: 'var(--danger)', marginLeft: 8 }}>
              <AlertTriangle size={10} style={{ display: 'inline', marginRight: 3 }} />
              {item.error}
            </span>
          )}
        </div>
      </div>

      {/* Status + remove */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
        {item.status === 'ready' && (
          <span className="badge badge-gray">Ready</span>
        )}
        {isUploading && (
          <span className="badge badge-blue" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block', width: 10, height: 10,
                border: '1.5px solid rgba(37,99,235,0.3)', borderTopColor: '#2563eb',
                borderRadius: '50%', animation: 'spin 0.8s linear infinite',
              }}
            />
            In Batch
          </span>
        )}
        {isDone && (
          <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <CheckCircle2 size={11} />
            Submitted
          </span>
        )}
        {isError && <span className="badge badge-red">Failed</span>}

        {!locked && item.status !== 'uploading' && (
          <button
            onClick={() => onRemove(item.id)}
            title="Remove"
            style={{
              background: 'none', border: 'none',
              color: 'var(--muted)', cursor: 'pointer', padding: 4,
              borderRadius: 4, lineHeight: 0,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--danger)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
          >
            <X size={13} />
          </button>
        )}
      </div>
    </div>
  );
}

// ─── DocPoller — mounts one poller per successfully uploaded doc id ─────────
function DocPoller({ docId }) {
  useDocumentPoller(docId);
  return null;
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export function Upload() {
  const [isDragover, setIsDragover]     = useState(false);
  const [queue, setQueue]               = useState([]);
  const [uploading, setUploading]       = useState(false);
  const [batchProgress, setBatchProgress] = useState(0);
  const [batchResult, setBatchResult]   = useState(null);
  const [uploadedIds, setUploadedIds]   = useState([]);

  const fileInputRef = useRef(null);
  const itemIdRef    = useRef(0);
  const { addDocument, toast } = useApp();
  const navigate = useNavigate();

  // ── File queue management ──────────────────────────────────────────────────
  const addFiles = useCallback((files) => {
    const newItems = Array.from(files)
      .filter((f) => {
        if (!ALLOWED[f.type]) {
          toast(`Unsupported type: ${f.name}`, 'warn');
          return false;
        }
        return true;
      })
      .map((f) => ({
        id:       ++itemIdRef.current,
        file:     f,
        status:   'ready',
        error:    null,
        documentId: null,
      }));

    setQueue((q) => {
      const combined = [...q, ...newItems];
      if (combined.length > MAX_BATCH) {
        toast(`Batch limit is ${MAX_BATCH} files. Extra files ignored.`, 'warn');
        return combined.slice(0, MAX_BATCH);
      }
      return combined;
    });
  }, [toast]);

  const removeItem = (id) => setQueue((q) => q.filter((i) => i.id !== id));
  const clearAll   = () => { if (!uploading) { setQueue([]); setBatchResult(null); } };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragover(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };
  const handleFileChange = (e) => {
    if (e.target.files.length) addFiles(e.target.files);
    // Reset input so same file can be re-added after removal
    e.target.value = '';
  };

  // ── Retry failed items ─────────────────────────────────────────────────────
  const retryFailed = () => {
    setQueue((q) => q.map((i) =>
      i.status === 'error' ? { ...i, status: 'ready', error: null } : i
    ));
    setBatchResult(null);
  };

  // ── Batch upload ───────────────────────────────────────────────────────────
  const processBatch = async () => {
    const ready = queue.filter((i) => i.status === 'ready');
    if (!ready.length) return;

    const readyIds = new Set(ready.map((r) => r.id));

    setUploading(true);
    setBatchProgress(0);
    setBatchResult(null);

    // Mark all ready items as uploading
    setQueue((q) => q.map((i) =>
      readyIds.has(i.id) ? { ...i, status: 'uploading' } : i
    ));

    try {
      const files  = ready.map((i) => i.file);
      const result = await uploadDocumentsBatch(files, (pct) => setBatchProgress(pct));

      setBatchResult(result);

      // Map queue-item IDs back to results by positional index
      const idToResult = {};
      ready.forEach((item, idx) => { idToResult[item.id] = result.results[idx]; });

      setQueue((q) => q.map((item) => {
        if (!readyIds.has(item.id)) return item;
        const r = idToResult[item.id];
        if (r?.success) return { ...item, status: 'done', documentId: r.document_id };
        return { ...item, status: 'error', error: r?.error || 'Server error' };
      }));

      // Register successful docs in global store + start pollers
      const successful = result.results.filter((r) => r.success);
      successful.forEach((r) => {
        addDocument({
          id:              r.document_id,
          filename:        r.filename,
          status:          r.status,
          workflow_run_id: r.workflow_run_id,
        });
      });
      setUploadedIds((ids) => [...ids, ...successful.map((r) => r.document_id)]);

      if (result.succeeded > 0) {
        toast(`${result.succeeded} file${result.succeeded > 1 ? 's' : ''} submitted to AI pipeline!`, 'success');
        setTimeout(() => navigate('/processing'), 1500);
      }
      if (result.failed > 0)
        toast(`${result.failed} file${result.failed > 1 ? 's' : ''} failed to upload`, 'warn');

    } catch (err) {
      setQueue((q) => q.map((i) =>
        readyIds.has(i.id) ? { ...i, status: 'error', error: err.message } : i
      ));
      toast(`Batch upload failed: ${err.message}`, 'error');
    }

    setUploading(false);
  };

  // ── Derived counts ─────────────────────────────────────────────────────────
  const readyCount     = queue.filter((i) => i.status === 'ready').length;
  const failedCount    = queue.filter((i) => i.status === 'error').length;
  const doneCount      = queue.filter((i) => i.status === 'done').length;
  const uploadingCount = queue.filter((i) => i.status === 'uploading').length;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="page">
      {/* Mount one status-poller per successfully uploaded doc */}
      {uploadedIds.map((id) => <DocPoller key={id} docId={id} />)}

      <div style={{ maxWidth: 780, margin: '0 auto' }}>

        {/* ── Upload Zone ── */}
        <div className={isDragover ? 'animated-border-active' : ''} style={{ marginBottom: 24 }}>
          <div
            className={`upload-zone ${isDragover ? 'dragover' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setIsDragover(true); }}
            onDragLeave={() => setIsDragover(false)}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            {/* Glowing Icon Circle with Outer Dashed Spinner */}
            <div className="upload-icon-circle">
              <UploadCloud size={32} strokeWidth={1.5} style={{ transform: isDragover ? 'scale(1.1) translateY(-2px)' : 'none', transition: 'all 0.3s ease' }} />
            </div>

            <h3 className="upload-main-heading">
              Drag &amp; drop documents here or <span className="upload-accent-text">browse files</span>
            </h3>

            <p className="upload-sub-description">
              Upload documents to start the automated AI ingestion pipeline. Your files will be classified, structured data extracted, and formulas validated in parallel.
            </p>

            {/* Redesigned File Type Chips */}
            <div className="upload-types-grid" style={{ marginBottom: 24 }}>
              {[
                { name: 'PDF', icon: FileText, color: '#ef4444' },
                { name: 'DOCX', icon: File, color: '#3b82f6' },
                { name: 'PNG', icon: Image, color: '#10b981' },
                { name: 'JPG', icon: Image, color: '#f59e0b' },
                { name: 'WEBP', icon: Image, color: '#06b6d4' },
              ].map((t) => {
                const Icon = t.icon;
                return (
                  <span key={t.name} className="upload-type-badge">
                    <Icon size={12} style={{ color: t.color }} />
                    {t.name}
                  </span>
                );
              })}
            </div>

            {/* Ingestion Pipeline Strip Info badge */}
            <div className="upload-batch-strip">
              <Layers size={13} />
              <span>Batch Ingestion Mode (Up to {MAX_BATCH} files)</span>
              <span style={{ opacity: 0.3 }}>•</span>
              <Zap size={12} />
              <span>Concurrently Processed via Mistral AI</span>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.png,.jpg,.jpeg,.webp"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
          </div>
        </div>

        {/* ── Upload Queue ── */}
        {queue.length > 0 && (
          <div className="card" style={{ marginBottom: 20 }}>

            {/* Queue header */}
            <div className="card-header">
              <div>
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Layers size={15} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                  Upload Queue
                  <span className="batch-mode-chip" style={{ fontSize: 10, padding: '2px 8px' }}>Batch</span>
                </div>
                <div className="card-sub" style={{ marginTop: 4 }}>
                  {queue.length} file{queue.length !== 1 ? 's' : ''}
                  {doneCount > 0      && <span style={{ color: 'var(--success)', marginLeft: 6 }}>· {doneCount} done</span>}
                  {uploadingCount > 0 && <span style={{ color: 'var(--accent)',  marginLeft: 6 }}>· {uploadingCount} uploading</span>}
                  {readyCount > 0     && <span style={{ color: 'var(--muted)',   marginLeft: 6 }}>· {readyCount} ready</span>}
                  {failedCount > 0    && <span style={{ color: 'var(--danger)',  marginLeft: 6 }}>· {failedCount} failed</span>}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                {failedCount > 0 && !uploading && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={retryFailed}
                    style={{ color: 'var(--warn)', borderColor: 'var(--warn-border)' }}
                  >
                    <RefreshCw size={12} /> Retry {failedCount} Failed
                  </button>
                )}
                {!uploading && (
                  <button className="btn btn-ghost btn-sm" onClick={clearAll}>
                    Clear All
                  </button>
                )}
              </div>
            </div>

            {/* Batch overall progress — shown while uploading */}
            {uploading && (
              <div className="batch-progress-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 'var(--text-md)', fontWeight: 600 }}>
                    Uploading {uploadingCount} file{uploadingCount !== 1 ? 's' : ''} as one batch…
                  </span>
                  <span style={{ fontSize: 'var(--text-lg)', fontWeight: 800, color: 'var(--accent)', letterSpacing: '-0.02em' }}>
                    {batchProgress}%
                  </span>
                </div>

                {/* Progress bar */}
                <div className="progress-bar" style={{ height: 8 }}>
                  <div
                    className="progress-fill"
                    style={{ width: `${batchProgress}%`, transition: 'width 0.4s ease' }}
                  />
                </div>

                {/* Server-side note */}
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-sm)', color: 'var(--muted)' }}>
                  <span style={{
                    display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
                    background: 'var(--accent)', animation: 'pulse 1.5s ease-in-out infinite',
                  }} />
                  Server is processing all files concurrently with Mistral AI Workflows
                </div>
              </div>
            )}

            {/* File list */}
            <div style={{ marginTop: uploading ? 8 : 0 }}>
              {queue.map((item) => (
                <QueueItem
                  key={item.id}
                  item={item}
                  onRemove={removeItem}
                  locked={uploading}
                />
              ))}
            </div>

            {/* Action footer */}
            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button
                id="batch-upload-btn"
                className="btn btn-primary"
                style={{ flex: 1, fontSize: 'var(--text-md)' }}
                onClick={processBatch}
                disabled={uploading || readyCount === 0}
              >
                {uploading ? (
                  <>
                    <span style={{
                      display: 'inline-block', width: 14, height: 14,
                      border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white',
                      borderRadius: '50%', animation: 'spin 0.8s linear infinite',
                    }} />
                    Uploading Batch…
                  </>
                ) : (
                  <>
                    <Layers size={14} />
                    Send {readyCount} File{readyCount !== 1 ? 's' : ''} for Extraction
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ── Batch Result Card ── */}
        {batchResult && (
          <div
            className="card"
            style={{
              marginBottom: 20,
              borderColor: batchResult.failed === 0 ? 'var(--success-border)' : 'var(--warn-border)',
              background: batchResult.failed === 0
                ? 'rgba(16,185,129,0.04)'
                : 'rgba(245,158,11,0.04)',
            }}
          >
            {/* Label */}
            <div style={{
              fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.09em', color: 'var(--muted)', marginBottom: 16,
            }}>
              Batch Result
            </div>

            {/* Stats row */}
            <div className="batch-stats-row">
              {/* Succeeded */}
              <div className="batch-stat-cell">
                <div className="batch-stat-icon" style={{ background: 'var(--success-dim)', color: 'var(--success)' }}>
                  <CheckCircle2 size={22} />
                </div>
                <div>
                  <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, color: 'var(--success)', letterSpacing: '-0.04em', lineHeight: 1 }}>
                    {batchResult.succeeded}
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 3 }}>Submitted</div>
                </div>
              </div>

              {/* Divider */}
              <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch', margin: '0 8px' }} />

              {/* Failed */}
              <div className="batch-stat-cell">
                <div className="batch-stat-icon" style={{
                  background: batchResult.failed > 0 ? 'var(--danger-dim)' : 'var(--card-alt)',
                  color: batchResult.failed > 0 ? 'var(--danger)' : 'var(--muted)',
                }}>
                  <XCircle size={22} />
                </div>
                <div>
                  <div style={{
                    fontSize: 'var(--text-3xl)', fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1,
                    color: batchResult.failed > 0 ? 'var(--danger)' : 'var(--muted)',
                  }}>
                    {batchResult.failed}
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 3 }}>Failed</div>
                </div>
              </div>

              {/* Divider */}
              <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch', margin: '0 8px' }} />

              {/* Total */}
              <div className="batch-stat-cell">
                <div className="batch-stat-icon" style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}>
                  <Layers size={22} />
                </div>
                <div>
                  <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1 }}>
                    {batchResult.total}
                  </div>
                  <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 3 }}>Total Files</div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' }}>
              {batchResult.succeeded > 0 && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate('/processing')}>
                  View Processing →
                </button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => navigate('/')}>
                Back to Dashboard
              </button>
              {batchResult.failed > 0 && (
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={retryFailed}
                  style={{ color: 'var(--warn)', borderColor: 'var(--warn-border)' }}
                >
                  <RefreshCw size={12} />
                  Retry {batchResult.failed} Failed File{batchResult.failed > 1 ? 's' : ''}
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Pipeline Info Card (shown only when queue is empty) ── */}
        {queue.length === 0 && (
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">AI Processing Pipeline</div>
              </div>
              <span className="batch-mode-chip">
                <Zap size={11} /> Parallel
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {[
                { icon: <CheckCircle2 size={15} />, label: 'Ingestion',     desc: 'Duplicate detection via SHA-256 & initial validation' },
                { icon: <ShieldCheck size={15} />,  label: 'Quality Check',   desc: 'Verification of document readability, layout alignment, and security constraints' },
                { icon: <Brain size={15} />,        label: 'Pre Processing',  desc: 'Automatic image enhancement, deskewing, and formatting conversion' },
                { icon: <Layers size={15} />,       label: 'Classification',  desc: 'AI determines document type and selects extraction schema automatically' },
                { icon: <ScanSearch size={15} />,   label: 'Extraction',      desc: 'Mistral OCR + structured field extraction per document type' },
                { icon: <ShieldCheck size={15} />,  label: 'Validation',      desc: 'Math cross-checks, required fields, and custom schema validation' },
                { icon: <UserCheck size={15} />,    label: 'Human Review',    desc: 'Human approval required when extraction confidence is low' },
                { icon: <Share2 size={15} />,       label: 'Output',          desc: 'Structured JSON persisted & ready for downstream export' },
              ].map(({ icon, label, desc }) => (
                <div key={label} className="info-row">
                  <div className="info-row-icon">{icon}</div>
                  <div className="info-row-label">{label}</div>
                  <div className="info-row-desc">{desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
