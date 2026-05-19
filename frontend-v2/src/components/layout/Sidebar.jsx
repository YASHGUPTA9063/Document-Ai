import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Upload, Cpu, FileSearch,
  CheckCircle, FileText, Bot, BarChart2
} from 'lucide-react';
import { useApp } from '../../store/AppStore';

const navSections = [
  {
    label: 'Main',
    items: [
      { label: 'Dashboard',   icon: LayoutDashboard, to: '/'           },
      { label: 'Upload',      icon: Upload,          to: '/upload'      },
      { label: 'Processing',  icon: Cpu,             to: '/processing'  },
    ],
  },
  {
    label: 'Data',
    items: [
      { label: 'Extraction',  icon: FileSearch,      to: '/extraction'  },
      { label: 'Validation',  icon: CheckCircle,     to: '/validation'  },
      { label: 'Documents',   icon: FileText,        to: '/documents'   },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { label: 'Agents',      icon: Bot,             to: '/agents'      },
      { label: 'Analytics',   icon: BarChart2,       to: '/analytics'   },
    ],
  },
];

export function Sidebar() {
  const { reviewDocs, pendingDocs } = useApp();

  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-mark">
          <div className="logo-icon">🧠</div>
          <div>
            <div className="logo-text">DocuMind AI</div>
            <div className="logo-sub">IDP PLATFORM v2.0</div>
          </div>
        </div>
      </div>

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
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <Icon size={15} className="nav-icon" />
                {label}
                {badge && <span className="nav-badge">{badge}</span>}
              </NavLink>
            );
          })}
        </div>
      ))}

      <div className="sidebar-footer">
        <div className="agent-status">
          <div className="pulse-dot" />
          <div>
            <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>
              6 Agents Active
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted)' }}>All systems nominal</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
