import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, X, FileText, Image, File } from 'lucide-react';
import { uploadDocument } from '../api/client';
import { useApp } from '../store/AppStore';
import { useDocumentPoller } from '../hooks/useDocumentPoller';

const ALLOWED = {
  'application/pdf': { ext: 'PDF', icon: FileText },
  'image/jpeg':      { ext: 'JPG', icon: Image },
  'image/png':       { ext: 'PNG', icon: Image },
  'image/webp':      { ext: 'WEBP', icon: Image },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': { ext: 'DOCX', icon: File },
};

function QueueItem({ item, onRemove }) {
  const Icon = ALLOWED[item.file.type]?.icon || File;
  const pct = item.progress;
  const isUploading = item.status === 'uploading';
  const isError = item.status === 'error';

  return (
    <div className="doc-card">
      <div className="doc-thumb">
        <Icon size={20} color="var(--accent)" />
      </div>
      <div className="doc-info">
        <div className="doc-name">{item.file.name}</div>
        <div className="doc-meta">
          {(item.file.size / 1024).toFixed(0)} KB · {ALLOWED[item.file.type]?.ext || 'Unknown'}
          {isError && <span style={{ color: 'var(--danger)', marginLeft: 8 }}>⚠ {item.error}</span>}
        </div>
        {isUploading && (
          <div className="progress-bar" style={{ marginTop: 6 }}>
            <div className="progress-fill" style={{ width: pct + '%' }} />
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {item.status === 'ready' && <span className="badge badge-gray">Ready</span>}
        {item.status === 'uploading' && <span className="badge badge-blue">⬆ {pct}%</span>}
        {item.status === 'done' && <span className="badge badge-green">✓ Uploaded</span>}
        {item.status === 'error' && <span className="badge badge-red">Error</span>}
        {item.status !== 'uploading' && (
          <button onClick={() => onRemove(item.id)} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 4 }}>
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

// Poller activator — one per uploaded doc id
function DocPoller({ docId }) {
  useDocumentPoller(docId);
  return null;
}

export function Upload() {
  const [isDragover, setIsDragover] = useState(false);
  const [queue, setQueue] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadedIds, setUploadedIds] = useState([]);
  const fileInputRef = useRef(null);
  const { addDocument, toast } = useApp();
  const navigate = useNavigate();
  let itemId = useRef(0);

  const addFiles = useCallback((files) => {
    const newItems = Array.from(files)
      .filter((f) => {
        if (!ALLOWED[f.type]) {
          toast(`Unsupported type: ${f.name}`, 'warn');
          return false;
        }
        return true;
      })
      .map((f) => ({ id: ++itemId.current, file: f, status: 'ready', progress: 0, error: null }));
    setQueue((q) => [...q, ...newItems]);
  }, [toast]);

  const handleDrop = (e) => {
    e.preventDefault(); setIsDragover(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };
  const handleFileChange = (e) => { if (e.target.files.length) addFiles(e.target.files); };

  const updateItem = (id, patch) => setQueue((q) => q.map((i) => i.id === id ? { ...i, ...patch } : i));
  const removeItem = (id) => setQueue((q) => q.filter((i) => i.id !== id));

  const processAll = async () => {
    const ready = queue.filter((i) => i.status === 'ready');
    if (!ready.length) return;
    setUploading(true);

    for (const item of ready) {
      updateItem(item.id, { status: 'uploading', progress: 0 });
      try {
        const res = await uploadDocument(item.file, (pct) => updateItem(item.id, { progress: pct }));
        updateItem(item.id, { status: 'done' });
        addDocument({ id: res.document_id, filename: res.filename, status: res.status, workflow_run_id: res.workflow_run_id });
        setUploadedIds((ids) => [...ids, res.document_id]);
        toast(`${item.file.name} uploaded — workflow started!`, 'success');
      } catch (err) {
        updateItem(item.id, { status: 'error', error: err.message });
        toast(`Upload failed: ${err.message}`, 'error');
      }
    }
    setUploading(false);
  };

  const readyCount = queue.filter((i) => i.status === 'ready').length;

  return (
    <div className="page">
      {/* Start pollers for all uploaded docs */}
      {uploadedIds.map((id) => <DocPoller key={id} docId={id} />)}

      <div style={{ maxWidth: 780, margin: '0 auto' }}>
        {/* Upload Zone */}
        <div className="animated-border" style={{ marginBottom: 24 }}>
          <div
            className={`upload-zone ${isDragover ? 'dragover' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setIsDragover(true); }}
            onDragLeave={() => setIsDragover(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <div style={{ fontSize: 42, marginBottom: 12 }}>
              <UploadCloud size={48} color="var(--accent)" strokeWidth={1.5} />
            </div>
            <div className="upload-title">Drop documents here or click to browse</div>
            <div className="upload-sub">Powered by Mistral AI — automatically classifies, extracts &amp; validates</div>
            <div className="upload-types">
              {['📄 PDF', '📝 DOCX', '🖼️ PNG', '🖼️ JPG', '🖼️ WEBP'].map((t) => (
                <span key={t} className="type-chip">{t}</span>
              ))}
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

        {/* Upload Queue */}
        {queue.length > 0 && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <div>
                <div className="card-title">Upload Queue</div>
                <div className="card-sub">{queue.length} file{queue.length !== 1 ? 's' : ''} — {readyCount} ready</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => setQueue([])}>
                  Clear All
                </button>
              </div>
            </div>

            <div>
              {queue.map((item) => (
                <QueueItem key={item.id} item={item} onRemove={removeItem} />
              ))}
            </div>

            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                onClick={processAll}
                disabled={uploading || readyCount === 0}
              >
                {uploading ? (
                  <>
                    <span className="spin" style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%' }} />
                    Uploading…
                  </>
                ) : (
                  <>🚀 Process {readyCount} File{readyCount !== 1 ? 's' : ''} with AI Agents</>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Post-upload navigation */}
        {uploadedIds.length > 0 && (
          <div className="card" style={{ borderColor: 'var(--success)', background: 'rgba(16,185,129,0.05)' }}>
            <div style={{ color: 'var(--success)', fontWeight: 700, marginBottom: 8 }}>
              ✅ {uploadedIds.length} document{uploadedIds.length > 1 ? 's' : ''} submitted to pipeline
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate('/processing')}>
                View Processing →
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate('/dashboard')}>
                Back to Dashboard
              </button>
            </div>
          </div>
        )}

        {/* Info */}
        {queue.length === 0 && (
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12 }}>⚡ Processing Pipeline</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                ['📥 Intake', 'Duplicate detection & initial validation'],
                ['🏷️ Classify', 'AI determines document type (invoice, contract, medical…)'],
                ['🔍 Extract', 'Mistral OCR + structured field extraction'],
                ['✅ Validate', 'Math cross-checks, date logic, schema validation'],
                ['👤 Review', 'Human approval if confidence &lt; 80%'],
                ['📤 Output', 'Structured JSON stored & ready to export'],
              ].map(([step, desc]) => (
                <div key={step} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', fontSize: 13 }}>
                  <span style={{ color: 'var(--accent)', fontWeight: 700, flexShrink: 0, width: 100 }}>{step}</span>
                  <span style={{ color: 'var(--text-dim)' }} dangerouslySetInnerHTML={{ __html: desc }} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
