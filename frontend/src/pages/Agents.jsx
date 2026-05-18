import { AgentCard } from '../components/ui/AgentCard';
import { Card, CardHeader } from '../components/ui/Card';
import { agents } from '../data/mockData';

export function Agents() {
  return (
    <div className="page page-enter">
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 16, lineHeight: 1.6 }}>
          DocuMind AI uses a multi-agent system where specialized AI agents collaborate to process documents.
          Each agent has a defined role, tools, and decision authority within the pipeline.
        </div>
      </div>

      {/* Agent Cards Grid */}
      <div className="agents-grid">
        {agents.map((agent) => (
          <AgentCard key={agent.name} agent={agent} />
        ))}
      </div>

      {/* Collaboration Graph */}
      <Card>
        <CardHeader
          title="🔀 Agent Collaboration Graph"
          subtitle="How agents communicate and hand off tasks"
        />
        <svg width="100%" height="200" viewBox="0 0 700 200" style={{ overflow: 'visible' }}>
          {/* Orchestrator */}
          <g transform="translate(350,100)">
            <circle r="30" fill="rgba(99,102,241,0.3)" stroke="#6366f1" strokeWidth="2" />
            <text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="18">🎭</text>
            <text y="44" textAnchor="middle" fill="#a5b4fc" fontSize="11">Orchestrator</text>
          </g>
          {/* Child agents */}
          <g transform="translate(80,50)">
            <circle r="22" fill="rgba(6,182,212,0.2)" stroke="#06b6d4" strokeWidth="1.5" />
            <text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="14">📥</text>
            <text y="34" textAnchor="middle" fill="#67e8f9" fontSize="10">Intake</text>
          </g>
          <g transform="translate(180,140)">
            <circle r="22" fill="rgba(139,92,246,0.2)" stroke="#8b5cf6" strokeWidth="1.5" />
            <text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="14">🏷️</text>
            <text y="34" textAnchor="middle" fill="#c4b5fd" fontSize="10">Classifier</text>
          </g>
          <g transform="translate(250,40)">
            <circle r="22" fill="rgba(16,185,129,0.2)" stroke="#10b981" strokeWidth="1.5" />
            <text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="14">🔍</text>
            <text y="34" textAnchor="middle" fill="#6ee7b7" fontSize="10">Extractor</text>
          </g>
          <g transform="translate(450,40)">
            <circle r="22" fill="rgba(245,158,11,0.2)" stroke="#f59e0b" strokeWidth="1.5" />
            <text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="14">✅</text>
            <text y="34" textAnchor="middle" fill="#fcd34d" fontSize="10">Validator</text>
          </g>
          <g transform="translate(520,140)">
            <circle r="22" fill="rgba(239,68,68,0.2)" stroke="#ef4444" strokeWidth="1.5" />
            <text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="14">🔄</text>
            <text y="34" textAnchor="middle" fill="#fca5a5" fontSize="10">Enricher</text>
          </g>
          <g transform="translate(620,80)">
            <circle r="22" fill="rgba(99,102,241,0.15)" stroke="#6366f1" strokeWidth="1.5" />
            <text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="14">📤</text>
            <text y="34" textAnchor="middle" fill="#a5b4fc" fontSize="10">Output</text>
          </g>
          {/* Edges */}
          <line x1="100" y1="55" x2="320" y2="90" stroke="#6366f1" strokeWidth="1" strokeDasharray="4,3" opacity="0.5" />
          <line x1="202" y1="133" x2="320" y2="105" stroke="#8b5cf6" strokeWidth="1" strokeDasharray="4,3" opacity="0.5" />
          <line x1="272" y1="50" x2="320" y2="85" stroke="#10b981" strokeWidth="1" strokeDasharray="4,3" opacity="0.5" />
          <line x1="380" y1="85" x2="428" y2="52" stroke="#f59e0b" strokeWidth="1" strokeDasharray="4,3" opacity="0.5" />
          <line x1="380" y1="108" x2="498" y2="135" stroke="#ef4444" strokeWidth="1" strokeDasharray="4,3" opacity="0.5" />
          <line x1="380" y1="90" x2="598" y2="82" stroke="#6366f1" strokeWidth="1" strokeDasharray="4,3" opacity="0.5" />
        </svg>
      </Card>
    </div>
  );
}
