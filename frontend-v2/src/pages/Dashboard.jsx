import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, ArrowRight, FileText, Target, Clock, AlertCircle,
  CheckCircle2, Loader2, Activity
} from 'lucide-react';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatCard } from '../components/ui/StatCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { DonutChart } from '../components/ui/DonutChart';
import { PipelineSteps } from '../components/ui/PipelineSteps';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';

// Status → activity dot color
const STATUS_COLORS = {
  completed:       'var(--success)',
  awaiting_review: 'var(--warn)',
  error:           'var(--danger)',
  pre_validating:  '#0891b2',
  processing:      'var(--accent)',
  pending:         'var(--muted)',
  rejected:        'var(--danger)',
};

const STATUS_LABELS = {
  completed:       'Completed',
  awaiting_review: 'Awaiting review',
  error:           'Error',
  pre_validating:  'Pre-Validating',
  processing:      'Processing',
  pending:         'Queued',
  rejected:        'Rejected',
};

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

  // ── Computed stats ──────────────────────────────
  const totalCount  = documents.length;
  const errorCount  = documents.filter((d) => d.status === 'error').length;
  const successRate = totalCount > 0
    ? Math.round((completedDocs.length / totalCount) * 100)
    : 0;

  // Document type distribution for donut
  const typeData = useMemo(() => {
    const map = {};
    documents.forEach((d) => {
      if (d.doc_type) map[d.doc_type] = (map[d.doc_type] || 0) + 1;
    });
    return Object.entries(map).map(([label, value]) => ({ label, value }));
  }, [documents]);

  // Most recent active doc for pipeline display
  const activeDoc = pendingDocs[0] || completedDocs[0];

  // Processing status breakdown
  const confBars = [
    { label: 'Completed',   value: completedDocs.length / Math.max(totalCount, 1) },
    { label: 'In Review',   value: reviewDocs.length   / Math.max(totalCount, 1) },
    { label: 'Processing',  value: pendingDocs.length  / Math.max(totalCount, 1) },
    { label: 'Errors',      value: errorCount          / Math.max(totalCount, 1) },
  ];

  // Recent activity feed (last 8 docs sorted by most recent)
  const recentDocs = useMemo(() =>
    [...documents].slice(0, 8),
  [documents]);

  return (
    <div className="page">
      {/* ── Stat Cards ── */}
      <div className="stats-row">
        <StatCard
          icon={<FileText size={18} />}
          iconVariant="accent"
          label="Total Documents"
          value={loading ? '—' : totalCount.toLocaleString()}
          delta={pendingDocs.length > 0 ? `${pendingDocs.length} in pipeline` : 'Queue empty'}
          deltaType={pendingDocs.length > 0 ? 'warn' : 'neutral'}
        />
        <StatCard
          icon={<Target size={18} />}
          iconVariant="success"
          label="Success Rate"
          value={loading ? '—' : successRate}
          unit="%"
          delta={`${completedDocs.length} completed`}
          deltaType="up"
        />
        <StatCard
          icon={<Clock size={18} />}
          iconVariant="warn"
          label="Pending Review"
          value={loading ? '—' : reviewDocs.length}
          delta={reviewDocs.length > 0 ? 'Action required' : 'All clear'}
          deltaType={reviewDocs.length > 0 ? 'warn' : 'up'}
        />
        <StatCard
          icon={<AlertCircle size={18} />}
          iconVariant={errorCount > 0 ? 'danger' : 'success'}
          label="Errors"
          value={loading ? '—' : errorCount}
          delta={errorCount > 0 ? 'Needs attention' : 'No errors'}
          deltaType={errorCount > 0 ? 'down' : 'up'}
        />
      </div>

      {/* ── Recent Docs + Chart ── */}
      <div className="grid-2">
        {/* Recent documents table */}
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
              <div className="empty-icon-wrap">
                <FileText size={28} />
              </div>
              <div className="empty-title">No documents yet</div>
              <div className="empty-sub">Upload a document to get started with the AI pipeline</div>
              <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/upload')}>
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
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {recentDocs.map((doc) => (
                    <tr
                      key={doc.id}
                      onClick={() => navigate('/extraction', { state: { docId: doc.id } })}
                    >
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <FileText size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                          <span style={{ fontSize: 'var(--text-md)' }}>{doc.filename}</span>
                        </div>
                      </td>
                      <td>
                        {doc.doc_type ? (
                          <span className="badge badge-cyan">{doc.doc_type}</span>
                        ) : (
                          <span style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>—</span>
                        )}
                      </td>
                      <td><StatusBadge status={doc.status} /></td>
                      <td style={{ width: 32 }}>
                        <ArrowRight size={13} className="row-arrow" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Donut chart */}
          <div className="card-data card" style={{ marginBottom: 0 }}>
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

      {/* ── Active Pipeline ── */}
      {activeDoc && (
        <div className="card card-accent" style={{ marginTop: 16 }}>
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Activity size={15} style={{ color: 'var(--accent)' }} />
                Active Pipeline
              </div>
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

      {/* ── Status breakdown + Activity feed ── */}
      <div className="grid-2" style={{ marginTop: activeDoc ? 0 : 16 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Processing Status Breakdown</div>
          </div>
          {confBars.map((b) => (
            <ConfidenceBar key={b.label} label={b.label} value={b.value} />
          ))}
        </div>

        {/* Recent Activity Feed */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Recent Activity</div>
            <div className="card-sub" style={{ marginTop: 0 }}>{recentDocs.length} documents</div>
          </div>

          {documents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--muted)', fontSize: 'var(--text-md)' }}>
              No activity yet
            </div>
          ) : (
            <div className="activity-feed">
              {recentDocs.slice(0, 6).map((doc) => (
                <div
                  key={doc.id}
                  className="activity-item"
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate('/extraction', { state: { docId: doc.id } })}
                >
                  <div
                    className="activity-dot"
                    style={{ background: STATUS_COLORS[doc.status] || 'var(--muted)' }}
                  />
                  <div className="activity-content">
                    <div className="activity-title">{doc.filename}</div>
                    <div className="activity-meta">
                      {STATUS_LABELS[doc.status] || doc.status}
                      {doc.doc_type && ` · ${doc.doc_type}`}
                    </div>
                  </div>
                  <ArrowRight size={12} style={{ color: 'var(--muted)', flexShrink: 0 }} />
                </div>
              ))}
            </div>
          )}

          {/* Quick action if pending reviews */}
          {reviewDocs.length > 0 && (
            <button
              className="btn btn-ghost"
              style={{
                width: '100%', marginTop: 12,
                borderColor: 'var(--warn)', color: 'var(--warn)',
              }}
              onClick={() => navigate('/validation')}
            >
              <Clock size={13} />
              Review {reviewDocs.length} Pending Document{reviewDocs.length > 1 ? 's' : ''}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
