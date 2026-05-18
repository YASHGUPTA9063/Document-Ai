import { useApp } from '../../context/AppContext';
import { pageTitles } from '../../data/mockData';
import { Btn } from '../ui/Btn';

export function TopBar() {
  const { activePage, navigate } = useApp();
  const [title, desc] = pageTitles[activePage] || [activePage, ''];

  return (
    <div className="topbar">
      <div style={{ flex: 1 }}>
        <div className="topbar-title">{title}</div>
        <div className="topbar-subtitle">{desc}</div>
      </div>

      <div className="search-bar">
        <span style={{ color: 'var(--muted)' }}>🔍</span>
        <input type="text" placeholder="Search documents, fields..." />
      </div>

      <button className="btn btn-ghost" style={{ fontSize: 12 }}>
        🔔 <span className="notif-badge">4</span>
      </button>

      <Btn variant="primary" onClick={() => navigate('upload')}>
        <span>+</span> New Document
      </Btn>
    </div>
  );
}
