import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, ArrowRight } from 'lucide-react';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatCard } from '../components/ui/StatCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { DonutChart } from '../components/ui/DonutChart';
import { PipelineSteps } from '../components/ui/PipelineSteps';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';

export function Dashboard() {
  const { documents, reviewDocs, pendingDocs, completedDocs } = useApp();
  const { refresh, loading } = useDocumentList();
  const navigate = useNavigate();

  useEffect(() => { refresh(); }, []);

  // Auto-refresh every 10s
  useEffect(() => {
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, [refresh]);

  // ── Computed stats ─────────────────────────────
  const totalCount  = documents.length;
  const errorCount  = documents.filter((d) => d.status === 'error').length;
  const successRate = totalCount > 0
    ? Math.round((completedDocs.length / totalCount) * 100)
    : 0;

  // Document type distribution
  const typeData = useMemo(() => {
    const map = {};
    documents.forEach((d) => {
      if (d.doc_type) map[d.doc_type] = (map[d.doc_type] || 0) + 1;
    });
    return Object.entries(map).map(([label, value]) => ({ label, value }));
  }, [documents]);

  // Most recent active doc for pipeline display
  const activeDoc = pendingDocs[0] || completedDocs[0];

  // Confidence distribution bars
  const confBars = [
    { label: 'Completed', value: completedDocs.length / Math.max(totalCount, 1) },
    { label: 'In Review',  value: reviewDocs.length  / Math.max(totalCount, 1) },
    { label: 'Processing', value: pendingDocs.length / Math.max(totalCount, 1) },
    { label: 'Errors',     value: errorCount          / Math.max(totalCount, 1) },
  ];

  return (
    <div className="page">
      {/* Stat Cards */}
      <div className="stats-row">
        <StatCard
          icon="📄"
          label="Total Documents"
          value={totalCount.toLocaleString()}
          delta={loading ? 'Syncing…' : `${pendingDocs.length} in pipeline`}
          deltaType={pendingDocs.length > 0 ? 'warn' : 'up'}
        />
        <StatCard
          icon="🎯"
          label="Success Rate"
          value={successRate}
          unit="%"
          delta={`${completedDocs.length} completed`}
          deltaType="up"
        />
        <StatCard
          icon="⏳"
          label="Pending Review"
          value={reviewDocs.length}
          delta={reviewDocs.length > 0 ? '⚠ Action required' : '✓ All clear'}
          deltaType={reviewDocs.length > 0 ? 'warn' : 'up'}
        />
        <StatCard
          icon="⚠️"
          label="Errors"
          value={errorCount}
          delta={errorCount > 0 ? 'Needs attention' : 'No errors'}
          deltaType={errorCount > 0 ? 'down' : 'up'}
        />
      </div>

      {/* Recent Docs + Chart */}
      <div className="grid-2">
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Recent Documents</div>
              <div className="card-sub">Latest processing queue</div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/documents')}>
              View All <ArrowRight size={12} />
            </button>
          </div>
          {documents.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📂</div>
              <div className="empty-title">No documents yet</div>
              <div className="empty-sub">Upload a document to get started</div>
              <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => navigate('/upload')}>
                <Upload size={13} /> Upload Document
              </button>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Type</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.slice(0, 8).map((doc) => (
                    <tr
                      key={doc.id}
                      style={{ cursor: 'pointer' }}
                      onClick={() => navigate('/extraction')}
                    >
                      <td>
                        <span className="doc-icon">📄</span>
                        <span style={{ fontSize: 12 }}>{doc.filename}</span>
                      </td>
                      <td>
                        {doc.doc_type ? (
                          <span className="badge badge-cyan">{doc.doc_type}</span>
                        ) : (
                          <span style={{ color: 'var(--muted)', fontSize: 11 }}>—</span>
                        )}
                      </td>
                      <td><StatusBadge status={doc.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ marginBottom: 0 }}>
            <div className="card-header">
              <div>
                <div className="card-title">Document Types</div>
                <div className="card-sub">Distribution across all docs</div>
              </div>
            </div>
            <DonutChart data={typeData} />
          </div>
        </div>
      </div>

      {/* Active Pipeline */}
      {activeDoc && (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🤖 Active Pipeline</div>
              <div className="card-sub">
                Processing: <strong style={{ color: 'var(--accent)' }}>{activeDoc.filename}</strong>
              </div>
            </div>
            <div className="chip">
              Live <span className="pulse-dot" style={{ width: 6, height: 6, marginLeft: 6, display: 'inline-block' }} />
            </div>
          </div>
          <PipelineSteps status={activeDoc.status} />
        </div>
      )}

      {/* Status breakdown bars */}
      <div className="grid-2">
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Processing Status Breakdown</div>
          </div>
          {confBars.map((b) => (
            <ConfidenceBar key={b.label} label={b.label} value={b.value} />
          ))}
        </div>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Quick Actions</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button className="btn btn-primary" onClick={() => navigate('/upload')}>
              <Upload size={14} /> Upload New Document
            </button>
            {reviewDocs.length > 0 && (
              <button className="btn btn-ghost" onClick={() => navigate('/validation')} style={{ borderColor: 'var(--warn)', color: 'var(--warn)' }}>
                ⚠ Review {reviewDocs.length} Pending Document{reviewDocs.length > 1 ? 's' : ''}
              </button>
            )}
            <button className="btn btn-ghost" onClick={() => navigate('/documents')}>
              View All Documents
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
