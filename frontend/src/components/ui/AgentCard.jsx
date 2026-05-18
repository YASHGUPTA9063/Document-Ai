const statusMap = { idle: 'status-idle', running: 'status-running', done: 'status-done', waiting: 'status-waiting' };
const statusLabel = { idle: 'Idle', running: '⚡ Running', done: '✓ Ready', waiting: '⏳ Waiting' };

export function AgentCard({ agent }) {
  const { icon, color, border, name, role, status, desc, docs, accuracy, latency } = agent;
  return (
    <div className={`agent-card ${status === 'running' ? 'active-agent' : ''}`}>
      <div className="agent-head">
        <div className="agent-avatar" style={{ background: color, border: `1px solid ${border}` }}>
          {icon}
        </div>
        <div>
          <div className="agent-name">{name}</div>
          <div className="agent-role">{role}</div>
        </div>
        <span className={`agent-status-badge ${statusMap[status]}`}>{statusLabel[status]}</span>
      </div>
      <div className="agent-desc">{desc}</div>
      <div className="agent-metrics">
        <div className="metric">
          <div className="metric-val">{docs.toLocaleString()}</div>
          <div className="metric-label">Processed</div>
        </div>
        <div className="metric">
          <div className="metric-val" style={{ color: 'var(--success)' }}>{accuracy}</div>
          <div className="metric-label">Accuracy</div>
        </div>
        <div className="metric">
          <div className="metric-val">{latency}</div>
          <div className="metric-label">Avg Latency</div>
        </div>
      </div>
    </div>
  );
}
