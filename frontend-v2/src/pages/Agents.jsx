const AGENTS = [
  {
    name: 'Intake Agent',
    emoji: '📥',
    color: 'rgba(6,182,212,0.15)',
    border: '#06b6d4',
    role: 'Entry point for all document processing',
    desc: 'Validates file format, detects duplicates via SHA-256 hash, and initializes the workflow run.',
    tools: ['File Validator', 'Duplicate Checker', 'DB Writer'],
  },
  {
    name: 'Classifier Agent',
    emoji: '🏷️',
    color: 'rgba(139,92,246,0.15)',
    border: '#8b5cf6',
    role: 'Document type identification',
    desc: 'Uses Mistral multimodal inference to classify documents into types: Invoice, Contract, Medical, Financial, Legal.',
    tools: ['Mistral OCR', 'Type Classifier', 'Confidence Scorer'],
  },
  {
    name: 'Extractor Agent',
    emoji: '🔍',
    color: 'rgba(16,185,129,0.15)',
    border: '#10b981',
    role: 'Structured field extraction',
    desc: 'Extracts structured fields from documents using Mistral OCR and structured output. Handles invoices, contracts, medical records, and more.',
    tools: ['Mistral OCR', 'Field Parser', 'Table Extractor'],
  },
  {
    name: 'Validator Agent',
    emoji: '✅',
    color: 'rgba(245,158,11,0.15)',
    border: '#f59e0b',
    role: 'Data quality assurance',
    desc: 'Cross-validates extracted fields: math checks on financials, date logic, schema conformity, and confidence scoring.',
    tools: ['Math Validator', 'Date Checker', 'Schema Validator'],
  },
  {
    name: 'Reviewer Agent',
    emoji: '👤',
    color: 'rgba(239,68,68,0.15)',
    border: '#ef4444',
    role: 'Human-in-the-loop review',
    desc: 'Auto-approves documents with confidence ≥ 80%. Low-confidence documents are paused for human review via the Validation page.',
    tools: ['Auto-Approver', 'Human Signal Listener', 'Review Logger'],
  },
  {
    name: 'Output Agent',
    emoji: '📤',
    color: 'rgba(99,102,241,0.15)',
    border: '#6366f1',
    role: 'Result persistence and export',
    desc: 'Stores validated extracted data and reviewer corrections to the database. Marks the document as completed.',
    tools: ['DB Writer', 'JSON Formatter', 'Webhook Notifier'],
  },
];

export function Agents() {
  return (
    <div className="page">
      <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 20, lineHeight: 1.7, maxWidth: 680 }}>
        DocuMind AI uses a <strong style={{ color: 'var(--text)' }}>multi-agent pipeline</strong> powered by
        the Mistral Workflow SDK. Specialized agents collaborate in sequence — each with defined roles, tools,
        and decision authority — to process documents from intake to structured output.
      </div>

      {/* Agent Cards */}
      <div className="agents-grid">
        {AGENTS.map((agent) => (
          <div
            key={agent.name}
            className="card agent-card"
            style={{ borderColor: agent.border, background: agent.color }}
          >
            <div className="agent-avatar" style={{ background: agent.color, border: `1px solid ${agent.border}` }}>
              {agent.emoji}
            </div>
            <div className="agent-name">{agent.name}</div>
            <div className="agent-role">{agent.role}</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 10, lineHeight: 1.5 }}>
              {agent.desc}
            </div>
            <div className="agent-tools">
              {agent.tools.map((t) => (
                <span key={t} className="agent-tool">{t}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Collaboration Graph */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">🔀 Agent Collaboration Graph</div>
            <div className="card-sub">Sequential pipeline with human-in-the-loop pauses</div>
          </div>
        </div>
        <svg width="100%" height="180" viewBox="0 0 700 180" style={{ overflow: 'visible' }}>
          {/* Pipeline flow line */}
          <line x1="60" y1="90" x2="640" y2="90" stroke="var(--border-hi)" strokeWidth="2" strokeDasharray="4,4" />

          {[
            { x: 60,  emoji: '📥', label: 'Intake',     color: '#06b6d4' },
            { x: 175, emoji: '🏷️', label: 'Classify',   color: '#8b5cf6' },
            { x: 290, emoji: '🔍', label: 'Extract',    color: '#10b981' },
            { x: 405, emoji: '✅', label: 'Validate',   color: '#f59e0b' },
            { x: 520, emoji: '👤', label: 'Review',     color: '#ef4444' },
            { x: 635, emoji: '📤', label: 'Output',     color: '#6366f1' },
          ].map(({ x, emoji, label, color }, i) => (
            <g key={label} transform={`translate(${x}, 90)`}>
              <circle r="28" fill={`${color}22`} stroke={color} strokeWidth="2" />
              <text textAnchor="middle" dominantBaseline="middle" fontSize="17">{emoji}</text>
              <text y="42" textAnchor="middle" fill={color} fontSize="10" fontWeight="600">{label}</text>
              {/* Arrow to next */}
              {i < 5 && (
                <text x="75" dominantBaseline="middle" fill="var(--border-hi)" fontSize="16">→</text>
              )}
            </g>
          ))}

          {/* Human pause annotations */}
          <text x="280" y="148" textAnchor="middle" fill="var(--warn)" fontSize="10">⏸ Duplicate? (optional pause)</text>
          <text x="520" y="148" textAnchor="middle" fill="var(--warn)" fontSize="10">⏸ Low confidence? (human review)</text>
        </svg>
      </div>
    </div>
  );
}
