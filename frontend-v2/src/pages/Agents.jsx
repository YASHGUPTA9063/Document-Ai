import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, ExternalLink, Cpu, Zap, AlertTriangle } from 'lucide-react';
import { getAgents } from '../api/client';

// ─── Skeleton card shown while loading ───────────────────────────────────────
function AgentSkeleton() {
  return (
    <div className="card agent-card" style={{ border: '1px solid var(--border)' }}>
      <div className="skeleton" style={{ width: 44, height: 44, borderRadius: 8, marginBottom: 14 }} />
      <div className="skeleton" style={{ width: '60%', height: 14, marginBottom: 8 }} />
      <div className="skeleton" style={{ width: '40%', height: 11, marginBottom: 12 }} />
      <div className="skeleton" style={{ width: '100%', height: 11, marginBottom: 6 }} />
      <div className="skeleton" style={{ width: '80%', height: 11, marginBottom: 14 }} />
      <div style={{ display: 'flex', gap: 5 }}>
        <div className="skeleton" style={{ width: 60, height: 20, borderRadius: 99 }} />
        <div className="skeleton" style={{ width: 50, height: 20, borderRadius: 99 }} />
        <div className="skeleton" style={{ width: 70, height: 20, borderRadius: 99 }} />
      </div>
    </div>
  );
}

// ─── Source badge: indicates if agent is live from Mistral or a workflow activity ─
function SourceBadge({ source }) {
  if (source === 'mistral') {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 10, fontWeight: 600, padding: '2px 7px',
        borderRadius: 99, border: '1px solid rgba(79,110,247,0.35)',
        background: 'rgba(79,110,247,0.08)', color: 'var(--accent)',
        marginBottom: 8,
      }}>
        <Zap size={9} /> Mistral Agent
      </span>
    );
  }
  if (source === 'mistral_fallback') {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 10, fontWeight: 600, padding: '2px 7px',
        borderRadius: 99, border: '1px solid rgba(245,158,11,0.35)',
        background: 'rgba(245,158,11,0.08)', color: 'var(--warn)',
        marginBottom: 8,
      }}>
        <AlertTriangle size={9} /> Mistral Agent (offline)
      </span>
    );
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 10, fontWeight: 600, padding: '2px 7px',
      borderRadius: 99, border: '1px solid var(--border)',
      background: 'var(--surface)', color: 'var(--text-dim)',
      marginBottom: 8,
    }}>
      <Cpu size={9} /> Workflow Activity
    </span>
  );
}

// ─── Single Agent Card ────────────────────────────────────────────────────────
function AgentCard({ agent, index }) {
  // Determine card class based on agent source
  const sourceClass =
    agent.source === 'mistral'          ? 'mistral-live' :
    agent.source === 'mistral_fallback' ? 'mistral-offline' :
    'workflow-activity';

  return (
    <div
      className={`card agent-card ${sourceClass} anim-slide-in`}
      style={{
        borderColor: agent.border,
        animationDelay: `${index * 60}ms`,
      }}
    >
      {/* Step badge */}
      <div style={{
        position: 'absolute', top: 12, right: 12,
        fontSize: 10, fontWeight: 700, color: 'var(--muted)',
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 99, padding: '2px 7px',
      }}>
        Step {agent.step}
      </div>

      {/* Avatar */}
      <div
        className="agent-avatar"
        style={{ background: agent.color, border: `1px solid ${agent.border}` }}
      >
        {agent.emoji}
      </div>

      {/* Source badge */}
      <SourceBadge source={agent.source} />

      {/* Name & role */}
      <div className="agent-name">{agent.name}</div>
      <div className="agent-role">{agent.role}</div>

      {/* Description */}
      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 10, lineHeight: 1.6 }}>
        {agent.description}
      </div>

      {/* Model chip */}
      {agent.model && (
        <div style={{
          fontSize: 10, color: 'var(--muted)',
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '3px 8px', marginBottom: 10,
          display: 'inline-block', fontFamily: 'monospace',
        }}>
          {agent.model}
        </div>
      )}

      {/* Agent ID with external link */}
      {agent.agent_id && (
        <div style={{
          fontSize: 10, color: 'var(--muted)', marginBottom: 10,
          display: 'flex', alignItems: 'center', gap: 5,
        }}>
          <span style={{ fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>
            {agent.agent_id}
          </span>
          <a
            href={`https://console.mistral.ai/agents/${agent.agent_id}`}
            target="_blank"
            rel="noopener noreferrer"
            title="Open in Mistral Studio"
            style={{ color: 'var(--accent)', flexShrink: 0 }}
          >
            <ExternalLink size={10} />
          </a>
        </div>
      )}

      {/* Tools */}
      <div className="agent-tools">
        {(agent.tools || []).map((t) => (
          <span key={t} className="agent-tool">{t}</span>
        ))}
      </div>
    </div>
  );
}

// ─── Main Agents Page ─────────────────────────────────────────────────────────
export function Agents() {
  const [agents, setAgents]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [lastFetched, setLastFetched] = useState(null);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAgents();
      setAgents(data);
      setLastFetched(new Date());
    } catch (err) {
      setError(err.message || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  // Counts
  const mistralCount  = agents.filter((a) => a.source === 'mistral').length;
  const workflowCount = agents.filter((a) => a.source === 'workflow').length;
  const offlineCount  = agents.filter((a) => a.source === 'mistral_fallback').length;

  return (
    <div className="page">

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7, maxWidth: 620, margin: 0 }}>
            This IDP platform uses a <strong style={{ color: 'var(--text)' }}>multi-agent pipeline</strong> powered by
            the Mistral Workflow SDK. Specialized agents collaborate in sequence — each with defined roles, tools,
            and decision authority — to process documents from intake to structured output.
          </p>

          {/* Live counts */}
          {!loading && agents.length > 0 && (
            <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--accent)', background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.2)', borderRadius: 99, padding: '3px 10px' }}>
                <Zap size={10} /> {mistralCount} Mistral Agent{mistralCount !== 1 ? 's' : ''}
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-dim)', background: 'var(--card-alt)', border: '1px solid var(--border)', borderRadius: 99, padding: '3px 10px' }}>
                <Cpu size={10} /> {workflowCount} Workflow Activit{workflowCount !== 1 ? 'ies' : 'y'}
              </span>
              {offlineCount > 0 && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--warn)', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 99, padding: '3px 10px' }}>
                  <AlertTriangle size={10} /> {offlineCount} Offline
                </span>
              )}
              {lastFetched && (
                <span style={{ fontSize: 10, color: 'var(--muted)', alignSelf: 'center' }}>
                  Updated {lastFetched.toLocaleTimeString()}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Refresh button */}
        <button
          className="btn btn-ghost btn-sm"
          onClick={fetchAgents}
          disabled={loading}
          id="agents-refresh-btn"
        >
          <RefreshCw size={12} className={loading ? 'spin' : ''} />
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div style={{
          background: 'var(--danger-dim)', border: '1px solid rgba(240,64,96,0.3)',
          borderRadius: 'var(--radius)', padding: '12px 16px', marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 13,
        }}>
          <AlertTriangle size={15} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <div>
            <strong style={{ color: 'var(--danger)' }}>Failed to load agents from backend</strong>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{error}</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={fetchAgents} style={{ marginLeft: 'auto' }}>
            Retry
          </button>
        </div>
      )}

      {/* ── Agent Cards Grid ── */}
      <div className="agents-grid">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => <AgentSkeleton key={i} />)
          : agents.map((agent, i) => (
              <AgentCard key={agent.key} agent={agent} index={i} />
            ))
        }
      </div>

      {/* ── Collaboration Graph ── */}
      {!loading && agents.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🔀 Agent Collaboration Graph</div>
              <div className="card-sub">Sequential pipeline with human-in-the-loop pauses</div>
            </div>
          </div>
          <svg
            width="100%"
            height="180"
            viewBox={`0 0 ${Math.max(700, agents.length * 116 + 60)} 180`}
            preserveAspectRatio="xMidYMid meet"
            style={{ overflow: 'visible' }}
          >
            <style>{`
              .pipeline-flow-line {
                stroke-dasharray: 6, 6;
                animation: pipeline-flow 20s linear infinite;
              }
              @keyframes pipeline-flow {
                to {
                  stroke-dashoffset: -500;
                }
              }
              .pipeline-node {
                cursor: pointer;
              }
              .pipeline-node circle {
                transition: r 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), stroke-width 0.25s ease, fill-opacity 0.25s ease;
              }
              .pipeline-node:hover circle {
                r: 32;
                stroke-width: 3px;
              }
              .node-emoji {
                transform-box: fill-box;
                transform-origin: center;
                transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
              }
              .pipeline-node:hover .node-emoji {
                transform: scale(1.2);
              }
              .node-label {
                transform-box: fill-box;
                transform-origin: center;
                transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), font-weight 0.25s ease;
              }
              .pipeline-node:hover .node-label {
                transform: translateY(2px);
                font-weight: 700;
              }
              .pipeline-arrow {
                transform-box: fill-box;
                transform-origin: center;
                animation: arrow-pulse 2s ease-in-out infinite alternate;
              }
              @keyframes arrow-pulse {
                0% { transform: translateX(-3px); opacity: 0.4; }
                100% { transform: translateX(3px); opacity: 0.8; }
              }
              .pause-label {
                animation: pause-pulse 2s ease-in-out infinite alternate;
              }
              @keyframes pause-pulse {
                0% { opacity: 0.75; }
                100% { opacity: 1; }
              }
            `}</style>

            {/* Pipeline flow line */}
            <line x1="60" y1="90" x2="640" y2="90" className="pipeline-flow-line" stroke="var(--border-hi)" strokeWidth="2" />

            {agents.map(({ key, emoji, border, name }, i) => {
              const x = 60 + i * 116;
              return (
                <g key={key} className="pipeline-node" transform={`translate(${x}, 90)`}>
                  <circle r="28" fill={`${border}15`} stroke={border} strokeWidth="2" />
                  <text className="node-emoji" textAnchor="middle" dominantBaseline="middle" fontSize="17">{emoji}</text>
                  <text y="42" className="node-label" textAnchor="middle" fill={border} fontSize="10" fontWeight="600">
                    {name.replace(' Agent', '')}
                  </text>
                  {i < agents.length - 1 && (
                    <text x="75" className="pipeline-arrow" dominantBaseline="middle" fill="var(--border-hi)" fontSize="16">→</text>
                  )}
                </g>
              );
            })}

            {/* Human pause annotations */}
            <text x="290" y="148" className="pause-label" textAnchor="middle" fill="var(--warn)" fontSize="10">
              <tspan fontWeight="bold" letterSpacing="1px">||</tspan> Duplicate? (optional pause)
            </text>
            <text x="520" y="148" className="pause-label" textAnchor="middle" fill="var(--warn)" fontSize="10">
              <tspan fontWeight="bold" letterSpacing="1px">||</tspan> Low confidence? (human review)
            </text>
          </svg>
        </div>
      )}
    </div>
  );
}
