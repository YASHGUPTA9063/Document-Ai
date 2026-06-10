import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Cpu, CheckCircle, ListTodo, FileText } from 'lucide-react';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { useDocumentPoller } from '../hooks/useDocumentPoller';
import { StatusBadge } from '../components/ui/StatusBadge';
import { PipelineSteps } from '../components/ui/PipelineSteps';

// Renders one poller per active doc
function PollersRenderer({ ids }) {
  return ids.map((id) => <SinglePoller key={id} docId={id} />);
}
function SinglePoller({ docId }) {
  useDocumentPoller(docId);
  return null;
}

export function Processing() {
  const { documents, pendingDocs } = useApp();
  const { refresh, loading } = useDocumentList();
  const navigate = useNavigate();

  useEffect(() => { refresh(); }, []);

  // Most recently active doc for the live pipeline display
  const featured = pendingDocs[0];

  return (
    <div className="page">
      {/* Activate pollers for all pending docs */}
      <PollersRenderer ids={pendingDocs.map((d) => d.id)} />

      {/* Live Pipeline for featured doc */}
      {featured ? (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Cpu size={16} style={{ color: 'var(--accent)' }} />
                Live Processing Pipeline
              </div>
              <div className="card-sub">
                Processing: <strong style={{ color: 'var(--accent)' }}>{featured.filename}</strong>
              </div>
            </div>
            <div className="chip" style={{ gap: 6 }}>
              <span className="pulse-dot" style={{ width: 6, height: 6 }} />
              Live
            </div>
          </div>
          <PipelineSteps status={featured.status} />
        </div>
      ) : (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon-wrap" style={{ color: 'var(--success)', background: 'var(--success-dim)', border: '1px solid var(--success-border)' }}>
              <CheckCircle size={32} />
            </div>
            <div className="empty-title">No active processing</div>
            <div className="empty-sub">All documents have been processed or the queue is empty.</div>
            <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => navigate('/upload')}>
              Upload Documents
            </button>
          </div>
        </div>
      )}

      {/* Processing Queue Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ListTodo size={16} style={{ color: 'var(--accent)' }} />
            Processing Queue
          </div>
          <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>
            <RefreshCw size={12} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>

        {pendingDocs.length === 0 ? (
          <div className="empty-state" style={{ padding: '24px' }}>
            <div className="empty-sub">No documents currently in the processing pipeline.</div>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Workflow Run</th>
                </tr>
              </thead>
              <tbody>
                {pendingDocs.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
                      <span style={{ fontSize: 12 }}>{doc.filename}</span>
                    </td>
                    <td>
                      {doc.doc_type
                        ? <span className="badge badge-cyan">{doc.doc_type}</span>
                        : <span style={{ color: 'var(--muted)', fontSize: 11 }}>Classifying…</span>}
                    </td>
                    <td><StatusBadge status={doc.status} /></td>
                    <td>
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'monospace' }}>
                        {doc.workflow_run_id?.slice(0, 16) || '—'}…
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* All Documents Mini Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">All Documents</div>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/documents')}>
            Full List →
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th><th>Type</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {documents.slice(0, 10).map((doc) => (
                <tr key={doc.id} style={{ cursor: 'pointer' }} onClick={() => navigate('/extraction')}>
                  <td>
                    <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
                    <span style={{ fontSize: 12 }}>{doc.filename}</span>
                  </td>
                  <td>
                    {doc.doc_type
                      ? <span className="badge badge-cyan">{doc.doc_type}</span>
                      : <span style={{ color: 'var(--muted)', fontSize: 11 }}>—</span>}
                  </td>
                  <td><StatusBadge status={doc.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
