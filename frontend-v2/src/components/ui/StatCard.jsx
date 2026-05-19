export function StatCard({ icon, label, value, unit = '', delta, deltaType = 'up' }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span style={{ fontSize: 16, color: 'var(--muted)', marginLeft: 3 }}>{unit}</span>}
      </div>
      {delta && <div className={`stat-delta ${deltaType}`}>{delta}</div>}
    </div>
  );
}
