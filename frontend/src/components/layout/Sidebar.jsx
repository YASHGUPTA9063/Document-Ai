import { useApp } from '../../context/AppContext';
import { navSections } from '../../data/mockData';

export function Sidebar() {
  const { activePage, navigate } = useApp();

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="logo">
        <div className="logo-mark">
          <div className="logo-icon">🧠</div>
          <div>
            <div className="logo-text">DocuMind AI</div>
            <div className="logo-sub">IDP PLATFORM v2.4</div>
          </div>
        </div>
      </div>

      {/* Nav Sections */}
      {navSections.map((section) => (
        <div key={section.label} className="nav-section" style={{ marginTop: 8 }}>
          <div className="nav-label">{section.label}</div>
          {section.items.map((item) => (
            <div
              key={item.label}
              className={`nav-item ${activePage === item.page ? 'active' : ''}`}
              onClick={() => navigate(item.page)}
            >
              <span className="icon">{item.icon}</span>
              {item.label}
              {item.badge && <span className="nav-badge">{item.badge}</span>}
            </div>
          ))}
        </div>
      ))}

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="agent-status">
          <div className="agent-dot" />
          <div>
            <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>6 Agents Active</div>
            <div style={{ fontSize: 10, color: 'var(--muted)' }}>All systems nominal</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
