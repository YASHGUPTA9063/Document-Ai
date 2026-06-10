import { useEffect, useMemo } from 'react';
import { useApp } from '../store/AppStore';
import { useDocumentList } from '../hooks/useDocumentList';
import { StatCard } from '../components/ui/StatCard';
import { DonutChart } from '../components/ui/DonutChart';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';
import { FileText, CheckCircle2, XCircle, Loader2, BarChart2 } from 'lucide-react';

function BarChart({ data }) {
  if (!data || data.length === 0) return <div className="empty-state" style={{ padding: 24 }}><div className="empty-sub">No data yet</div></div>;
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120, paddingTop: 8 }}>
      {data.map(({ label, value }) => (
        <div key={label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, height: '100%', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>{value}</span>
          <div style={{
            width: '100%', background: 'var(--accent)',
            height: `${(value / max) * 85}%`, minHeight: value > 0 ? 4 : 0,
            borderRadius: '4px 4px 0 0', opacity: 0.8,
            transition: 'height 0.5s ease',
          }} />
          <span style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'center', lineHeight: 1.2 }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

export function Analytics() {
  const { documents } = useApp();
  const { refresh, loading } = useDocumentList();

  useEffect(() => { refresh(); }, []);

  const total = documents.length;
  const completed = documents.filter((d) => d.status === 'completed').length;
  const rejected  = documents.filter((d) => d.status === 'rejected').length;
  const errors    = documents.filter((d) => d.status === 'error').length;
  const pending   = documents.filter((d) => ['pending','processing'].includes(d.status)).length;
  const inReview  = documents.filter((d) => d.status === 'awaiting_review').length;

  const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;
  const rejectionRate = total > 0 ? Math.round((rejected / total) * 100) : 0;

  // Doc type donut
  const typeData = useMemo(() => {
    const map = {};
    documents.forEach((d) => {
      if (d.doc_type) map[d.doc_type] = (map[d.doc_type] || 0) + 1;
    });
    return Object.entries(map).map(([label, value]) => ({ label, value }));
  }, [documents]);

  // Status bar chart
  const statusBars = [
    { label: 'Completed', value: completed },
    { label: 'In Review', value: inReview },
    { label: 'Processing', value: pending },
    { label: 'Rejected', value: rejected },
    { label: 'Errors', value: errors },
  ];

  // Status breakdown bars
  const breakdownBars = [
    { label: 'Success Rate',    value: successRate / 100 },
    { label: 'Rejection Rate',  value: rejectionRate / 100 },
    { label: 'Review Rate',     value: total > 0 ? inReview / total : 0 },
    { label: 'Error Rate',      value: total > 0 ? errors / total : 0 },
  ];

  return (
    <div className="page">
      <div className="stats-row">
        <StatCard icon={<FileText size={18} />}    iconVariant="accent"                     label="Total Documents" value={total.toLocaleString()} delta="All time" deltaType="neutral" />
        <StatCard icon={<CheckCircle2 size={18} />} iconVariant="success"                    label="Success Rate"    value={successRate} unit="%" delta={`${completed} completed`} deltaType="up" />
        <StatCard icon={<XCircle size={18} />}      iconVariant={rejectionRate > 10 ? 'danger' : 'success'} label="Rejection Rate" value={rejectionRate} unit="%" delta={`${rejected} rejected`} deltaType={rejectionRate > 10 ? 'down' : 'up'} />
        <StatCard icon={<Loader2 size={18} />}      iconVariant={inReview > 0 ? 'warn' : 'accent'}            label="In Pipeline"    value={pending + inReview} delta={inReview > 0 ? `${inReview} awaiting review` : 'Nothing pending'} deltaType={inReview > 0 ? 'warn' : 'up'} />
      </div>

      <div className="grid-2">
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Document Types</div>
            <div className="card-sub">Distribution by type</div>
          </div>
          <DonutChart data={typeData} />
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">Status Distribution</div>
            <div className="card-sub">Count by processing status</div>
          </div>
          <BarChart data={statusBars} />
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div className="card-title">Performance Breakdown</div>
        </div>
        {breakdownBars.map((b) => (
          <ConfidenceBar key={b.label} label={b.label} value={b.value} />
        ))}
      </div>

      {total === 0 && (
        <div className="card">
          <div className="empty-state">
            <BarChart2 className="empty-icon" size={36} />
            <div className="empty-title">No analytics yet</div>
            <div className="empty-sub">Upload and process documents to see metrics here.</div>
          </div>
        </div>
      )}
    </div>
  );
}
