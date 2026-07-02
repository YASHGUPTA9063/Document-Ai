import { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, ExternalLink, Cpu, Zap, AlertTriangle,
  Upload, Bot, FileSearch, CheckCircle, FileText, UserCheck, GitBranch, Shield
} from 'lucide-react';
import { getAgents } from '../api/client';

const AGENT_ICON_MAP = {
  intake: Upload,
  pre_validator: Shield,
  preprocessing: Cpu,
  classifier: Bot,
  extractor: FileSearch,
  invoice_extractor: FileSearch,
  contract_extractor: FileSearch,
  kyc_extractor: FileSearch,
  medical_extractor: FileSearch,
  bank_extractor: FileSearch,
  others_extractor: FileSearch,
  fraud_checker: Shield,
  validator: CheckCircle,
  auto_verifier: UserCheck,
  reviewer: UserCheck,
  output: FileText,
};

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
        style={{ background: agent.color, border: `1px solid ${agent.border}`, display: 'flex', alignItems: 'center', justify: 'center' }}
      >
        {(() => {
          const IconComponent = AGENT_ICON_MAP[agent.key] || Bot;
          return <IconComponent size={20} style={{ color: agent.border }} />;
        })()}
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

      {/* Tools / Internal Functions */}
      <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
          <Cpu size={10} style={{ color: agent.border }} /> Running Functions
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {(agent.tools || []).map((t) => (
            <div key={t} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--card-alt)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '4px 8px', fontSize: 11, fontFamily: 'monospace',
              color: 'var(--text-dim)', wordBreak: 'break-all'
            }}>
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>λ</span>
              <span>{t.includes('(') ? t : `${t}()`}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Pipeline Collaboration Graph ───────────────────────────────────────────
const StepArrow = () => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: 28, flexShrink: 0 }}>
    <div style={{ width: 1.5, flex: 1, background: 'var(--border)' }} />
    <svg width="9" height="5" viewBox="0 0 9 5" style={{ display: 'block' }}>
      <polygon points="0,0 9,0 4.5,5" fill="var(--border)" />
    </svg>
  </div>
);

function PipelineGraph({ agents }) {
  const intakeAgent = agents.find(a => a.key === 'intake');
  const preValidatorAgent = agents.find(a => a.key === 'pre_validator');
  const preprocessingAgent = agents.find(a => a.key === 'preprocessing');
  const classifierAgent = agents.find(a => a.key === 'classifier');
  const fraudCheckerAgent = agents.find(a => a.key === 'fraud_checker');
  const validatorAgent = agents.find(a => a.key === 'validator');
  const autoVerifierAgent = agents.find(a => a.key === 'auto_verifier');
  const reviewerAgent = agents.find(a => a.key === 'reviewer');
  const outputAgent = agents.find(a => a.key === 'output');
  const extractors = agents.filter(a => a.key.includes('extractor'));

  // Ordered pipeline: 10 steps sequentially mapping the backend-v4 architecture.
  const steps = [
    { type: 'node', agent: intakeAgent, step: 1 },
    { type: 'node', agent: preValidatorAgent, step: 2 },
    { type: 'node', agent: preprocessingAgent, step: 2.5, conditional: true, label: "Enabled in config" },
    { type: 'node', agent: classifierAgent, step: 3 },
    { type: 'node', agent: fraudCheckerAgent, step: 3.5, conditional: true, label: "KYC Only" },
    { type: 'extractors',                     step: 4 },
    { type: 'node', agent: validatorAgent, step: 5 },
    { type: 'node', agent: autoVerifierAgent, step: 5.5, conditional: true, label: "KYC Only" },
    { type: 'node', agent: reviewerAgent, step: 6 },
    { type: 'node', agent: outputAgent, step: 7 },
  ];

  // Filter steps to only include those where the agent data exists in backend response (robust fallback)
  const activeSteps = steps.filter(s => {
    if (s.type === 'extractors') return extractors.length > 0;
    if (s.type === 'node') return !!s.agent;
    return false;
  });

  return (
    <div style={{ padding: '20px 28px 28px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {activeSteps.map((s, i) => {
        const isLast = i === activeSteps.length - 1;

        const StepBadge = ({ n }) => (
          <span style={{
            fontSize: 10, fontWeight: 600, color: 'var(--muted)',
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 99, padding: '1px 8px', whiteSpace: 'nowrap', flexShrink: 0,
          }}>Step {n}</span>
        );

        return (
          <div key={i} style={{ width: '100%', maxWidth: 560, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>

            {/* ── Regular node card ── */}
            {s.type === 'node' && s.agent && (
              <div style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 12,
                padding: '11px 16px', borderRadius: 10,
                background: s.agent.color,
                border: `1.5px solid ${s.agent.border}`,
              }}>
                <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
                  {(() => {
                    const IconComponent = AGENT_ICON_MAP[s.agent.key] || Bot;
                    return <IconComponent size={20} style={{ color: s.agent.border }} />;
                  })()}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', lineHeight: 1.3 }}>
                    {s.agent.name.replace(' Agent', '')}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                    {s.agent.role}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                  {s.conditional && (
                    <span style={{
                      fontSize: 9, fontWeight: 600, color: 'var(--muted)',
                      background: 'var(--surface)', border: '1px solid var(--border)',
                      borderRadius: 4, padding: '2px 6px', whiteSpace: 'nowrap',
                    }}>{s.label}</span>
                  )}
                  {s.agent.key === 'reviewer' && (
                    <span style={{
                      fontSize: 10, fontWeight: 600, color: 'var(--warn)',
                      background: 'rgba(245,158,11,0.10)',
                      border: '1px solid rgba(245,158,11,0.35)',
                      borderRadius: 99, padding: '1px 8px', whiteSpace: 'nowrap',
                    }}>‖ Human Review</span>
                  )}
                  <StepBadge n={s.step} />
                </div>
              </div>
            )}

            {/* ── Extractor group card ── */}
            {s.type === 'extractors' && (
              <div style={{
                width: '100%', borderRadius: 10,
                border: '1.5px dashed var(--border)',
                background: 'rgba(79,110,247,0.03)',
                padding: '11px 16px',
              }}>
                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
                    <FileSearch size={20} style={{ color: 'var(--accent)' }} />
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)', lineHeight: 1.3 }}>Extractor</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                      Conditional — one activates per document type
                    </div>
                  </div>
                  <StepBadge n={s.step} />
                </div>
                {/* Type chips */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {extractors.map(e => (
                    <span key={e.key} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '4px 11px', borderRadius: 99,
                      background: e.color, border: `1px solid ${e.border}`,
                      fontSize: 11, fontWeight: 600, color: e.border,
                    }}>
                      {(() => {
                        const IconComponent = AGENT_ICON_MAP[e.key] || FileSearch;
                        return <IconComponent size={12} />;
                      })()}
                      {e.name.replace(' Agent', '').replace(' Extractor', '')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {!isLast && <StepArrow />}
          </div>
        );
      })}
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

      {/* ── Pipeline Graph ── */}
      {!loading && agents.length > 0 && (
        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <GitBranch size={16} style={{ color: 'var(--accent)' }} />
                Agent Collaboration Graph
              </div>
              <div className="card-sub">Vertical pipeline · conditional fan-out at extraction phase · human review gate</div>
            </div>
          </div>
          <PipelineGraph agents={agents} />
        </div>
      )}
    </div>
  );
}
