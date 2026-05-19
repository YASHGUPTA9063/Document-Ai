export function ConfidenceBar({ label, value, color }) {
  const pct = Math.round((value || 0) * 100);
  const col =
    pct >= 90 ? 'var(--success)' :
    pct >= 70 ? 'var(--warn)' :
    'var(--danger)';
  const fillColor = color || col;

  return (
    <div className="conf-bar-row">
      <div className="conf-bar-label">
        <span>{label}</span>
        <span style={{ color: fillColor, fontWeight: 600 }}>{pct}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: pct + '%', background: fillColor }} />
      </div>
    </div>
  );
}
