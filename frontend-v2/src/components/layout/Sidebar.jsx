import { useState, useEffect, useCallback } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Upload, Cpu, FileSearch,
  CheckCircle, FileText, Bot, BarChart2,
  ChevronLeft, ChevronRight, Settings, FileCode,
  ClipboardList, Shield
} from 'lucide-react';
import { useApp } from '../../store/AppStore';

const navSections = [
  {
    label: 'Main',
    items: [
      { label: 'Dashboard', icon: LayoutDashboard, to: '/' },
      { label: 'Upload', icon: Upload, to: '/upload' },
      { label: 'Processing', icon: Cpu, to: '/processing' },
    ],
  },
  {
    label: 'Data',
    items: [
      { label: 'Extraction', icon: FileSearch, to: '/extraction' },
      { label: 'Validation', icon: CheckCircle, to: '/validation' },
      { label: 'Documents', icon: FileText, to: '/documents' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { label: 'Agents', icon: Bot, to: '/agents' },
      { label: 'Analytics', icon: BarChart2, to: '/analytics' },
      { label: 'Templates', icon: FileCode, to: '/templates' },
    ],
  },
  {
    label: 'Claims',
    items: [
      { label: 'Claim Process', icon: ClipboardList, to: '/claim-process' },
    ],
  },
  {
    label: 'KYC',
    items: [
      { label: 'KYC Process', icon: Shield, to: '/kyc-process' },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'Settings', icon: Settings, to: '/settings' },
    ],
  },
];

export function Sidebar({ mobileOpen, onMobileClose }) {
  const { reviewDocs, pendingDocs } = useApp();
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebar-collapsed') === 'true'; }
    catch { return false; }
  });

  const toggleCollapse = useCallback(() => {
    setCollapsed((v) => {
      const next = !v;
      try { localStorage.setItem('sidebar-collapsed', String(next)); } catch { }
      return next;
    });
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    if (mobileOpen && onMobileClose) onMobileClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sidebarClass = [
    'sidebar',
    collapsed ? 'collapsed' : '',
    mobileOpen ? 'mobile-open' : '',
  ].filter(Boolean).join(' ');

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={onMobileClose} />
      )}

      <aside className={sidebarClass}>
        <div className="sidebar-content">
          {/* ── Logo ── */}
          <div className="logo">
            <div className="logo-mark">
              <div className="logo-icon">
                <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
                  <rect x="3" y="1" width="12" height="16" rx="2" fill="white" fillOpacity="0.15" />
                  <rect x="3" y="1" width="12" height="16" rx="2" stroke="white" strokeOpacity="0.5" strokeWidth="1" />
                  <line x1="5.5" y1="5" x2="12.5" y2="5" stroke="white" strokeOpacity="0.7" strokeWidth="1" strokeLinecap="round" />
                  <line x1="5.5" y1="8" x2="12.5" y2="8" stroke="white" strokeOpacity="0.7" strokeWidth="1" strokeLinecap="round" />
                  <line x1="5.5" y1="11" x2="10" y2="11" stroke="white" strokeOpacity="0.5" strokeWidth="1" strokeLinecap="round" />
                  <circle cx="16" cy="16" r="5" fill="var(--accent3)" fillOpacity="0.9" />
                  <path d="M13.5 16L15.2 17.7L18.5 14" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div className="logo-text-wrap">
                <div className="logo-text">Intelligent Document</div>
                <div className="logo-text" style={{ marginTop: 1 }}>Processing</div>
                <div className="logo-sub">IDP Platform · v2.0</div>
              </div>
            </div>
          </div>

          {/* ── Navigation ── */}
          {navSections.map((section) => (
            <div key={section.label} className="nav-section">
              <div className="nav-label">{section.label}</div>
              {section.items.map(({ label, icon: Icon, to }) => {
                const badge =
                  label === 'Validation' && reviewDocs.length > 0
                    ? reviewDocs.length
                    : label === 'Processing' && pendingDocs.length > 0
                      ? pendingDocs.length
                      : null;

                return (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    title={collapsed ? label : undefined}
                    className={({ isActive }) =>
                      `nav-item${isActive ? ' active' : ''}`
                    }
                    onClick={onMobileClose}
                  >
                    <Icon size={16} className="nav-icon" strokeWidth={1.75} />
                    <span className="nav-item-label">{label}</span>
                    {badge && <span className="nav-badge">{badge}</span>}
                  </NavLink>
                );
              })}
            </div>
          ))}

          {/* ── Footer ── */}
          <div className="sidebar-footer">
            <div className="agent-status">
              <div className="pulse-dot" />
              <div className="agent-status-text">
                <div style={{ fontSize: 'var(--text-md)', color: 'var(--text)', fontWeight: 600 }}>
                  10 Agents Active
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', marginTop: 1 }}>
                  All systems nominal
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Collapse toggle */}
        <button
          className="sidebar-collapse-btn"
          onClick={toggleCollapse}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed
            ? <ChevronRight size={12} />
            : <ChevronLeft size={12} />
          }
        </button>
      </aside>
    </>
  );
}
