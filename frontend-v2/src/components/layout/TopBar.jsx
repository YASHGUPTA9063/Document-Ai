import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Sun, Moon, User, Menu, ArrowRight } from 'lucide-react';
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
  '/settings':   { title: 'Settings',    sub: 'Configure system preferences' },
};

// ── Dark mode helpers ─────────────────────────────
function getInitialTheme() {
  try {
    const stored = localStorage.getItem('idp-theme');
    if (stored) return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('idp-theme', theme); } catch {}
}

export function TopBar({ onMobileMenuToggle }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { reviewDocs } = useApp();
  const { loading } = useDocumentList();

  const meta = PAGE_META[pathname] || { title: 'IDP Platform', sub: '' };

  // ── Dark mode state ──
  const [theme, setTheme] = useState(getInitialTheme);
  useEffect(() => { applyTheme(theme); }, [theme]);
  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
  }, []);

  // ── Notification dropdown ──
  const [notifOpen, setNotifOpen] = useState(false);
  const notifRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const hasNotifs = reviewDocs.length > 0;

  return (
    <div className="topbar">
      <div className="topbar-left">
        {/* Hamburger — mobile only */}
        <button
          className="topbar-hamburger"
          onClick={onMobileMenuToggle}
          aria-label="Open navigation menu"
        >
          <Menu size={16} />
        </button>

        <div className="topbar-breadcrumb">
          <div className="topbar-title">{meta.title}</div>
          {meta.sub && <div className="topbar-sub">{meta.sub}</div>}
        </div>
      </div>

      <div className="topbar-right">
        {/* Loading indicator — only show when actually syncing */}
        {loading && (
          <span style={{
            fontSize: 'var(--text-sm)', color: 'var(--muted)',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span className="spin" style={{
              display: 'inline-block', width: 12, height: 12,
              border: '1.5px solid var(--border)', borderTopColor: 'var(--accent)',
              borderRadius: '50%',
            }} />
            Syncing
          </span>
        )}

        {/* Dark / Light toggle */}
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          id="topbar-theme-toggle"
        >
          {theme === 'dark'
            ? <Sun size={15} strokeWidth={1.75} />
            : <Moon size={15} strokeWidth={1.75} />
          }
        </button>

        {/* Notification bell */}
        <div className="notif-wrapper" ref={notifRef}>
          <button
            className="theme-toggle"
            style={{ position: 'relative' }}
            onClick={() => setNotifOpen((o) => !o)}
            id="topbar-notifications-btn"
            aria-label={`Notifications${hasNotifs ? ` — ${reviewDocs.length} pending` : ''}`}
            title={hasNotifs ? `${reviewDocs.length} document${reviewDocs.length > 1 ? 's' : ''} awaiting review` : 'No notifications'}
          >
            <Bell size={15} strokeWidth={1.75} />
            {hasNotifs && (
              <span style={{
                position: 'absolute', top: 6, right: 6,
                width: 7, height: 7, borderRadius: '50%',
                background: 'var(--warn)',
                boxShadow: '0 0 6px rgba(245,158,11,0.5)',
                border: '1.5px solid var(--surface)',
              }} />
            )}
          </button>

          {/* Dropdown */}
          {notifOpen && (
            <div className="notif-dropdown">
              <div className="notif-header">
                <span>Notifications</span>
                {hasNotifs && (
                  <span className="badge badge-yellow">{reviewDocs.length} pending</span>
                )}
              </div>
              {!hasNotifs ? (
                <div className="notif-empty">
                  <Bell size={20} style={{ opacity: 0.3, marginBottom: 6 }} />
                  <div>All clear — no pending reviews</div>
                </div>
              ) : (
                reviewDocs.slice(0, 5).map((doc) => (
                  <div
                    key={doc.id}
                    className="notif-item"
                    onClick={() => { navigate('/validation'); setNotifOpen(false); }}
                  >
                    <div className="notif-dot" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 'var(--text-md)', fontWeight: 500,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {doc.filename}
                      </div>
                      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginTop: 2 }}>
                        Awaiting review
                      </div>
                    </div>
                    <ArrowRight size={12} style={{ color: 'var(--muted)', flexShrink: 0 }} />
                  </div>
                ))
              )}
              {reviewDocs.length > 5 && (
                <div
                  style={{
                    padding: '8px 16px', fontSize: 'var(--text-sm)',
                    color: 'var(--accent)', textAlign: 'center', cursor: 'pointer',
                    borderTop: '1px solid var(--border)',
                  }}
                  onClick={() => { navigate('/validation'); setNotifOpen(false); }}
                >
                  View all {reviewDocs.length} →
                </div>
              )}
            </div>
          )}
        </div>

        {/* User avatar */}
        <div
          id="topbar-user-avatar"
          style={{
            width: 34, height: 34, borderRadius: '50%',
            background: 'var(--grad-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 14px rgba(79,110,247,0.25)',
            border: '2px solid rgba(79,110,247,0.20)',
            cursor: 'pointer',
            flexShrink: 0,
          }}
          title="User settings"
          aria-label="User menu"
        >
          <User size={16} color="white" strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

// Export theme initializer so it can be called on app load
export { applyTheme, getInitialTheme };
