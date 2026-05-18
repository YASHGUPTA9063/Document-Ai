import { useState } from 'react';
import { Card, CardHeader } from '../components/ui/Card';
import { Btn } from '../components/ui/Btn';
import { Badge } from '../components/ui/Badge';
import { useApp } from '../context/AppContext';
import { initialQueueFiles } from '../data/mockData';

export function Upload() {
  const { setShowModal } = useApp();
  const [isDragover, setIsDragover] = useState(false);
  const [queue, setQueue] = useState(initialQueueFiles);
  const [confVal, setConfVal] = useState(85);

  const handleDragOver = (e) => { e.preventDefault(); setIsDragover(true); };
  const handleDragLeave = () => setIsDragover(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragover(false);
    if (e.dataTransfer.files.length) alert(`${e.dataTransfer.files.length} file(s) added to queue!`);
  };
  const handleFileSelect = (e) => {
    if (e.target.files.length) {
      const names = Array.from(e.target.files).map((f) => f.name).join(', ');
      alert(`Added to queue: ${names}`);
    }
  };
  const removeFile = (id) => setQueue((q) => q.filter((f) => f.id !== id));

  return (
    <div className="page page-enter">
      <div style={{ maxWidth: 780, margin: '0 auto' }}>
        {/* Upload Zone */}
        <div className="animated-border" style={{ marginBottom: 24 }}>
          <div
            className={`upload-zone ${isDragover ? 'dragover' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => document.getElementById('fileInput').click()}
          >
            <div className="upload-icon">📁</div>
            <div className="upload-title">Drop documents here or click to browse</div>
            <div className="upload-sub">Powered by agentic AI — automatically classifies, extracts, and validates</div>
            <div className="upload-types">
              {['📄 PDF', '📝 DOCX', '🖼️ PNG/JPG', '📊 XLSX', '✉️ EML', '🗜️ ZIP'].map((t) => (
                <span key={t} className="type-chip">{t}</span>
              ))}
            </div>
            <input
              type="file"
              id="fileInput"
              multiple
              accept=".pdf,.docx,.png,.jpg,.xlsx,.eml"
              style={{ display: 'none' }}
              onChange={handleFileSelect}
            />
          </div>
        </div>

        {/* Upload Queue */}
        <Card style={{ marginBottom: 20 }}>
          <CardHeader
            title="Upload Queue"
            action={<Badge variant="blue">{queue.length} files</Badge>}
          />
          <div>
            {queue.map((f) => (
              <div key={f.id} className="doc-card" style={{ cursor: 'default' }}>
                <div className="doc-thumb">{f.icon}</div>
                <div className="doc-info">
                  <div className="doc-name">{f.name}</div>
                  <div className="doc-meta">
                    {f.size} · Auto-classified: <strong>{f.type}</strong>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Badge variant="green">Ready</Badge>
                  <button
                    onClick={() => removeFile(f.id)}
                    style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 16, cursor: 'pointer', padding: 4 }}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
            <Btn variant="primary" onClick={() => setShowModal(true)} style={{ flex: 1 }}>
              🚀 Process All with AI Agents
            </Btn>
            <Btn variant="ghost" onClick={() => setQueue([])}>Clear Queue</Btn>
          </div>
        </Card>

        {/* Processing Config */}
        <Card>
          <CardHeader title="⚡ Processing Configuration" />
          <div className="grid-2" style={{ marginBottom: 0 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>Orchestration Model</div>
              <select className="styled-select">
                <option>Claude claude-sonnet-4-6 (Recommended)</option>
                <option>Claude Opus 4.7 (Best accuracy)</option>
                <option>Claude Haiku 4.5 (Fastest)</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>Processing Pipeline</div>
              <select className="styled-select">
                <option>Full Agentic (Classify → Extract → Validate)</option>
                <option>Extract Only</option>
                <option>Classify Only</option>
                <option>Custom Pipeline</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>Output Format</div>
              <select className="styled-select">
                <option>Structured JSON</option>
                <option>CSV Export</option>
                <option>API Webhook</option>
                <option>Database Push</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>Confidence Threshold</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
                <input
                  type="range" min="50" max="99" value={confVal}
                  style={{ flex: 1 }}
                  onChange={(e) => setConfVal(e.target.value)}
                />
                <span style={{ fontSize: 13, fontWeight: 600, width: 36 }}>{confVal}%</span>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
