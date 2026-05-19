import { useLocation, useNavigate } from 'react-router-dom';
import { RefreshCw, Bell } from 'lucide-react';
import { useApp } from '../../store/AppStore';
import { useDocumentList } from '../../hooks/useDocumentList';

const PAGE_META = {
  '/':           { title: 'Dashboard',   sub: 'Overview & live stats' },
  '/upload':     { title: 'Upload',      sub: 'Add documents to the pipeline' },
  '/processing': { title: 'Processing',  sub: 'Live workflow orchestration' },
  '/extraction': { title: 'Extraction',  sub: 'AI-extracted structured data' },
  '/validation': { title: 'Validation',  sub: 'Human review queue' },
  '/documents':  { title: 'Documents',   sub: 'All processed files' },
  '/agents':     { title: 'Agents',      sub: 'Multi-agent system overview' },
  '/analytics':  { title: 'Analytics',   sub: 'Processing metrics & trends' },
};

export function TopBar() {
  const { pathname } = useLocation();
  const { toasts, reviewDocs } = useApp();
  const { refresh, loading } = useDocumentList();
  const meta = PAGE_META[pathname] || { title: 'DocuMind AI', sub: '' };

  return (
    <div className="topbar">
      <div className="topbar-left">
        <div className="topbar-title">{meta.title}</div>
        {meta.sub && <div className="topbar-sub">{meta.sub}</div>}
      </div>
      <div className="topbar-right">
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => refresh()}
          disabled={loading}
          title="Refresh document list"
        >
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
          {loading ? 'Syncing…' : 'Sync'}
        </button>

        <div style={{ position: 'relative' }}>
          <button className="btn btn-ghost btn-sm">
            <Bell size={13} />
          </button>
          {reviewDocs.length > 0 && (
            <span style={{
              position: 'absolute', top: 2, right: 2,
              width: 8, height: 8, borderRadius: '50%',
              background: 'var(--warn)',
            }} />
          )}
        </div>

        <div style={{
          width: 30, height: 30, borderRadius: '50%',
          background: 'linear-gradient(135deg,var(--accent),var(--accent2))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 700, color: 'white',
        }}>
          U
        </div>
      </div>
    </div>
  );
}
