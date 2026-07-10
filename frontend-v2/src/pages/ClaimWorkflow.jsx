import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, CheckCircle, ChevronDown, Download, Loader2, RotateCcw,
  Circle, AlertTriangle, X as XIcon, Brain, Copy, FileOutput, Sparkles,
  ThumbsUp, ThumbsDown, ShieldCheck, Scale, Gavel, FileText, FileCode,
} from 'lucide-react';
import { INITIAL_STEPS, stepDuration, PROS, CONS } from './claimData';

/* ─── JSON syntax highlighter ─── */
function highlightJson(json) {
  return json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/(".*?")(\s*:)/g, '<span class="json-key">$1</span>$2')
    .replace(/:\s*(".*?")/g, ': <span class="json-string">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span class="json-bool">$1</span>')
    .replace(/:\s*(-?\d+(?:\.\d+)?)/g, ': <span class="json-number">$1</span>');
}

/* ─── State icon helper ─── */
function StateIcon({ state, size = 14 }) {
  if (state === 'running')   return <Loader2 size={size} className="spin" />;
  if (state === 'completed') return <CheckCircle size={size} />;
  if (state === 'warning')   return <AlertTriangle size={size} />;
  if (state === 'failed')    return <XIcon size={size} />;
  return <Circle size={size} />;
}

export function ClaimWorkflow() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const docCount = Number(searchParams.get('docCount')) || 0;

  const [steps, setSteps]     = useState(() => INITIAL_STEPS.map(s => ({ ...s, state: 'waiting', duration: undefined, confidence: undefined })));
  const [running, setRunning] = useState(false);
  const [done, setDone]       = useState(false);
  const [active, setActive]   = useState(null);
  const [openSteps, setOpen]  = useState({});
  const [tab, setTab]         = useState('thought');
  const startedRef            = useRef(false);

  /* Auto-start workflow */
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    setRunning(true); setDone(false);
    setSteps(INITIAL_STEPS.map(s => ({ ...s, state: 'waiting', duration: undefined, confidence: undefined })));

    let i = 0;
    const tick = () => {
      const current = INITIAL_STEPS[i];
      if (!current) { setRunning(false); setDone(true); setActive(INITIAL_STEPS[INITIAL_STEPS.length - 1].id); return; }
      setActive(current.id);
      setSteps(prev => prev.map(s => s.id === current.id ? { ...s, state: 'running' } : s));
      const d = stepDuration(current.id);
      setTimeout(() => {
        setSteps(prev => prev.map(s =>
          s.id === current.id ? { ...s, state: 'completed', duration: d, confidence: 0.9 + Math.random() * 0.09 } : s
        ));
        i += 1;
        tick();
      }, d);
    };
    setTimeout(tick, 350);
  }, []);

  /* Auto-scroll to summary on done */
  useEffect(() => {
    if (!done) return;
    const timer = setTimeout(() => {
      document.getElementById('completion-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
    return () => clearTimeout(timer);
  }, [done]);

  const restart = useCallback(() => navigate('/claim-process'), [navigate]);

  const completedCount  = steps.filter(s => s.state === 'completed').length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);

  /* Active step for inspector */
  const currentStep = steps.find(s => s.id === active) || steps.find(s => s.state === 'running') || steps[0];
  const isJson      = currentStep.outputKind === 'json';
  const jsonContent = currentStep.state === 'waiting' ? '// Waiting…' : isJson ? JSON.stringify(currentStep.output, null, 2) : String(currentStep.output ?? '');
  const thoughtText = currentStep.agentThought ?? '';

  /* Completion stats */
  const totalMs = steps.reduce((a, s) => a + (s.duration ?? 0), 0);
  const avgConf = steps.filter(s => s.confidence != null).reduce((a, s) => a + (s.confidence ?? 0), 0) /
    Math.max(1, steps.filter(s => s.confidence != null).length);

  return (
    <div className="claim-page">
      {/* Status bar */}
      <div className={`wf-status-bar${done ? ' done' : ''}`} style={{ marginBottom: 20 }}>
        <div className="wf-status-left">
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/claim-process')}>
            <ArrowLeft size={14} /> Back
          </button>
          <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
          <div>
            <div className="wf-status-info-title">
              {running ? <><Loader2 size={14} className="spin" style={{ color: 'var(--info)' }} /> Claim analysis in progress…</> :
               done    ? <><CheckCircle size={14} style={{ color: 'var(--success)' }} /> <span style={{ color: 'var(--success)' }}>Claim analysis completed</span></> :
                         'Initializing workflow…'}
            </div>
            <div className="wf-status-info-sub">
              {completedCount}/{steps.length} agents complete · atlas-claims-4o · autonomous execution
            </div>
          </div>
        </div>
        <div className="wf-status-right">
          <div className="wf-progress-bar">
            <div className={`wf-progress-fill${done ? ' done' : ''}`} style={{ width: `${progressPercent}%` }} />
          </div>
          <span className={`wf-progress-pct${done ? ' done' : ''}`}>{progressPercent}%</span>
          {done && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 8 }}>
              <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
              <button className="btn btn-ghost btn-sm" onClick={() => document.getElementById('completion-summary')?.scrollIntoView({ behavior: 'smooth' })}>
                <ChevronDown size={14} /> View results
              </button>
              <button className="btn btn-ghost btn-sm" onClick={restart}>
                <RotateCcw size={14} /> Restart
              </button>
              <button className="btn btn-primary btn-sm">
                <Download size={14} /> Report
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 3-column layout */}
      <div className="wf-columns" style={{ marginBottom: 20 }}>
        {/* ── Timeline ── */}
        <div className="wf-timeline">
          <div className="wf-timeline-header">
            <div>
              <div className="wf-timeline-title">AI execution timeline</div>
              <div className="wf-timeline-sub">Human-readable trace of every step</div>
            </div>
            <span className="wf-timeline-tag">run-8f2c</span>
          </div>
          <div className="wf-timeline-list">
            <div className="wf-timeline-line" />
            {steps.map(s => {
              const isOpen   = openSteps[s.id] ?? s.state === 'running';
              const isActive = active === s.id;
              return (
                <div key={s.id}>
                  <button
                    className={`wf-step-btn${isActive ? ' active' : ''}`}
                    onClick={() => { setActive(s.id); setOpen(o => ({ ...o, [s.id]: !isOpen })); }}
                  >
                    <div className={`wf-step-circle ${s.state}`}><StateIcon state={s.state} size={14} /></div>
                    <div className="wf-step-content">
                      <div className="wf-step-top">
                        <div className="wf-step-label">{s.label}</div>
                        <div className="wf-step-metrics">
                          {typeof s.confidence === 'number' && s.state === 'completed' && (
                            <span className="wf-step-conf">{Math.round(s.confidence * 100)}%</span>
                          )}
                          {typeof s.duration === 'number' && <span className="wf-step-dur">{s.duration}ms</span>}
                          <ChevronDown size={12} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }} />
                        </div>
                      </div>
                      <div className="wf-step-summary">{s.summary}</div>
                    </div>
                  </button>
                  {isOpen && s.state !== 'waiting' && (
                    <div className="wf-step-thought">
                      {s.state === 'running' ? (
                        <div className="wf-step-reasoning"><Loader2 size={12} className="spin" /> Agent is reasoning through {s.label.toLowerCase()}…</div>
                      ) : (
                        <>
                          <div className="wf-step-thought-label"><Brain size={12} /> Agent Thought</div>
                          <div className="wf-step-thought-text">{s.agentThought ?? s.summary}</div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Pipeline Graph (2-col grid with SVG edges, matching AI Hub) ── */}
        <div className="wf-pipeline">
          <div className="wf-pipeline-header">
            <div>
              <div className="wf-pipeline-title">Workflow graph</div>
              <div className="wf-pipeline-sub">Live execution across {steps.length} nodes</div>
            </div>
            <div className="wf-pipeline-legend">
              {['running', 'completed', 'waiting'].map(s => (
                <span key={s} className="wf-legend-item">
                  <span className={`wf-legend-dot ${s}`} /> {s.charAt(0).toUpperCase() + s.slice(1)}
                </span>
              ))}
            </div>
          </div>
          <div className="wf-graph-canvas">
            {/* Dot pattern background */}
            <svg className="wf-graph-dots" width="100%" height="100%">
              <defs>
                <pattern id="dotPattern" x="0" y="0" width="18" height="18" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="1" fill="var(--border)" opacity="0.4" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#dotPattern)" />
            </svg>

            {/* Grid wrapper: edges SVG + nodes grid share exact same bounds */}
            <div className="wf-graph-grid-wrap">
              {/* SVG edges layer — percentage-based coords aligned to grid */}
              <svg className="wf-graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none">
                {steps.slice(0, -1).map((s, i) => {
                  const next = steps[i + 1];
                  const cols = 2;
                  const rows = Math.ceil(steps.length / cols);
                  const cx = (col) => col === 0 ? 25 : 75;
                  const rowH = 100 / rows;
                  const cy = (row) => row * rowH + rowH / 2;
                  const sCol = i % cols, sRow = Math.floor(i / cols);
                  const tCol = (i + 1) % cols, tRow = Math.floor((i + 1) / cols);
                  const sx = cx(sCol), sy = cy(sRow) + rowH * 0.35;
                  const tx = cx(tCol), ty = cy(tRow) - rowH * 0.35;

                  const isActive = s.state === 'completed' && (next.state === 'running' || next.state === 'completed');
                  const isDone   = s.state === 'completed' && next.state !== 'running';

                  const midY = (sy + ty) / 2;
                  const d = `M ${sx} ${sy} C ${sx} ${midY}, ${tx} ${midY}, ${tx} ${ty}`;

                  return (
                    <path
                      key={`${s.id}->${next.id}`}
                      d={d}
                      fill="none"
                      stroke={isActive ? 'var(--accent)' : isDone ? 'var(--success)' : 'var(--border)'}
                      strokeWidth={isActive ? 2 : 1.25}
                      vectorEffect="non-scaling-stroke"
                      className={isActive ? 'wf-edge-animated' : ''}
                    />
                  );
                })}
              </svg>

              {/* Node grid (2 columns × 3 rows) */}
              <div className="wf-graph-grid">
                {steps.map((s, i) => {
                  const isActive = active === s.id;
                  return (
                    <div
                      key={s.id}
                      className={`wf-graph-node ${s.state}${isActive ? ' active' : ''}`}
                      onClick={() => setActive(s.id)}
                    >
                      <div className="wf-graph-node-head">
                        <div className={`wf-graph-node-icon ${s.state}`}><StateIcon state={s.state} size={12} /></div>
                        <div className="wf-graph-node-label">{s.label}</div>
                      </div>
                      <div className="wf-graph-node-foot">
                        <span className={`wf-graph-node-state ${s.state}`}>
                          {s.state === 'waiting' ? 'Waiting' : s.state === 'running' ? 'Running' : 'Completed'}
                        </span>
                        <span className="wf-graph-node-dur">{typeof s.duration === 'number' ? `${s.duration}ms` : '—'}</span>
                      </div>
                      {s.state === 'running' && (
                        <div className="wf-pipe-node-shimmer"><div className="wf-pipe-node-shimmer-bar" /></div>
                      )}
                      {/* Hover tooltip */}
                      <div className="wf-graph-tooltip">
                        <div style={{ fontWeight: 600, fontSize: 'var(--text-md)', marginBottom: 4 }}>{s.label}</div>
                        <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)', lineHeight: 1.5, marginBottom: 8 }}>{s.summary}</div>
                        <div className="wf-graph-tooltip-grid">
                          <div><div style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)' }}>Status</div><div className={`wf-graph-node-state ${s.state}`} style={{ fontSize: 'var(--text-sm)' }}>{s.state}</div></div>
                          <div><div style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)' }}>Duration</div><div style={{ fontFamily: 'monospace', fontSize: 'var(--text-sm)' }}>{s.duration ? `${s.duration}ms` : '—'}</div></div>
                          <div><div style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)' }}>Confidence</div><div style={{ fontFamily: 'monospace', fontSize: 'var(--text-sm)' }}>{typeof s.confidence === 'number' ? `${Math.round(s.confidence * 100)}%` : '—'}</div></div>
                          <div><div style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)' }}>State</div><div style={{ fontSize: 'var(--text-sm)' }}>{s.state}</div></div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* ── Agent Inspector ── */}
        <div className="wf-inspector">
          <div className="wf-inspector-header">
            <div style={{ minWidth: 0 }}>
              <div className="wf-inspector-title">Agent Inspector</div>
              <div className="wf-inspector-sub">{currentStep.label} · {currentStep.state === 'running' ? 'reasoning…' : currentStep.state}</div>
            </div>
            <select className="styled-select" value={currentStep.id} onChange={e => setActive(e.target.value)} style={{ width: 170, fontSize: 'var(--text-sm)', padding: '5px 8px' }}>
              {steps.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>

          {/* Tab bar */}
          <div className="wf-inspector-tabs">
            {[
              { key: 'thought', icon: <Brain size={12} />, label: 'Agent Thought' },
              { key: 'output',  icon: <FileOutput size={12} />, label: 'Output' },
              { key: 'meta',    icon: <Sparkles size={12} />, label: 'Metadata' },
            ].map(t => (
              <button
                key={t.key}
                className={`wf-inspector-tab${tab === t.key ? (t.key === 'thought' ? ' active' : ' active-output') : ''}`}
                onClick={() => setTab(t.key)}
              >
                {t.icon} {t.label}
              </button>
            ))}
            <div className="wf-inspector-actions">
              <button className="btn btn-ghost btn-icon btn-sm" title="Copy" onClick={() => navigator.clipboard?.writeText(tab === 'thought' ? thoughtText : jsonContent)}>
                <Copy size={14} />
              </button>
              <button className="btn btn-ghost btn-icon btn-sm" title="Download"><Download size={14} /></button>
            </div>
          </div>

          {/* Body */}
          <div className="wf-inspector-body">
            {tab === 'thought' && (
              currentStep.state === 'waiting' ? (
                <div className="wf-placeholder"><Brain size={16} /> Agent will begin reasoning when this step starts…</div>
              ) : currentStep.state === 'running' ? (
                <div>
                  <div className="wf-placeholder reasoning"><Loader2 size={16} className="spin" /> Agent is reasoning…</div>
                  <div className="wf-skeleton-bars" style={{ marginTop: 16, padding: 16, borderRadius: 'var(--radius)', border: '1px solid rgba(59,130,246,0.2)', background: 'rgba(59,130,246,0.05)' }}>
                    <div className="wf-skeleton-bar" style={{ width: '75%' }} />
                    <div className="wf-skeleton-bar" />
                    <div className="wf-skeleton-bar" />
                  </div>
                </div>
              ) : (
                <div>
                  <div className="wf-thought-chain-label"><Brain size={14} /> Agent Reasoning Chain</div>
                  <div className="wf-thought-chain-box">
                    <div className="wf-thought-chain-text">{thoughtText}</div>
                  </div>
                  {currentStep.confidence && (
                    <div className="wf-thought-conf">
                      <span className="wf-thought-conf-value">{Math.round(currentStep.confidence * 100)}%</span>
                      <span style={{ color: 'var(--muted)' }}>agent confidence</span>
                    </div>
                  )}
                </div>
              )
            )}
            {tab === 'output' && (
              currentStep.state === 'waiting' ? (
                <pre className="wf-output-json">{'// Waiting for this step to execute…'}</pre>
              ) : isJson ? (
                <pre className="wf-output-json" dangerouslySetInnerHTML={{ __html: highlightJson(jsonContent) }} />
              ) : (
                <pre className="wf-output-json">{jsonContent}</pre>
              )
            )}
            {tab === 'meta' && (
              <div className="wf-meta-grid">
                {[
                  ['Agent ID', currentStep.id],
                  ['State', currentStep.state],
                  ['Duration', currentStep.duration ? `${currentStep.duration} ms` : '—'],
                  ['Confidence', currentStep.confidence ? `${Math.round(currentStep.confidence * 100)}%` : '—'],
                  ['Model', 'atlas-claims-4o'],
                  ['Region', 'ap-south-1'],
                ].map(([k, v]) => (
                  <div key={k} className="wf-meta-item">
                    <div className="wf-meta-key">{k}</div>
                    <div className="wf-meta-val">{v}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Completion Summary ── */}
      {done && (
        <div id="completion-summary" className="wf-completion" style={{ marginBottom: 20 }}>
          {/* Header */}
          <div className="wf-completion-header">
            <div className="wf-completion-icon"><CheckCircle size={20} /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="wf-completion-title">Claim Analysis Complete</div>
              <div className="wf-completion-sub">Case CLM-2026-001 · All 6 validation agents completed successfully</div>
            </div>
            <div className="wf-completion-actions">
              <button className="btn btn-ghost btn-sm" onClick={restart}><RotateCcw size={14} /> Back to Claims</button>
              <button className="btn btn-primary btn-sm"><Download size={14} /> Download report</button>
            </div>
          </div>

          {/* Stats */}
          <div className="wf-completion-stats">
            {[
              { label: 'Documents', value: String(docCount), sub: 'validated & processed' },
              { label: 'Processing time', value: `${(totalMs / 1000).toFixed(2)}s`, sub: 'end-to-end' },
              { label: 'AI confidence', value: `${Math.round(avgConf * 100)}%`, sub: 'weighted average' },
              { label: 'Validation', value: 'Passed', sub: '6 agents · 0 failures' },
              { label: 'Decision', value: 'APPROVE', sub: 'autonomous · signed' },
            ].map((c, i) => (
              <div key={c.label} className="wf-completion-stat anim-slide-up" style={{ animationDelay: `${i * 60}ms` }}>
                <div className="wf-completion-stat-label">{c.label}</div>
                <div className="wf-completion-stat-value">{c.value}</div>
                <div className="wf-completion-stat-sub">{c.sub}</div>
              </div>
            ))}
          </div>

          {/* Pros & Cons */}
          <div className="wf-proscons">
            <div>
              <div className="wf-proscons-title pros"><ThumbsUp size={14} /> Factors Supporting Approval ({PROS.length})</div>
              <div className="wf-proscons-list">
                {PROS.map((pro, i) => (
                  <div key={i} className="wf-proscons-item pro anim-slide-right" style={{ animationDelay: `${i * 50}ms` }}>
                    <CheckCircle size={14} className="wf-proscons-icon" style={{ color: 'var(--success)' }} />
                    <span>{pro}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="wf-proscons-title cons"><ThumbsDown size={14} /> Risk Factors / Concerns ({CONS.length})</div>
              <div className="wf-proscons-list">
                {CONS.map((con, i) => (
                  <div key={i} className="wf-proscons-item con anim-slide-right" style={{ animationDelay: `${i * 50}ms` }}>
                    <AlertTriangle size={14} className="wf-proscons-icon" style={{ color: 'var(--warn)' }} />
                    <span>{con}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* AI Suggestion + Decision */}
          <div className="wf-decision-grid">
            <div>
              <div className="wf-suggestion-title"><Brain size={14} style={{ color: 'var(--accent)' }} /> AI Suggestion</div>
              <div className="wf-suggestion-box">
                <div className="wf-suggestion-rec"><Sparkles size={16} /> Recommendation: APPROVE</div>
                <p className="wf-suggestion-text">
                  Based on comprehensive analysis across all 6 validation agents, this claim demonstrates
                  strong legitimacy indicators. The claimant has a clean 6-year policyholder history with
                  zero prior claims. All submitted documents pass integrity checks with tamper scores below
                  0.03. The medical treatment (PCI with DES for Acute Coronary Syndrome) follows established
                  clinical guidelines and the billing is within standard benchmark rates. The 4 risk factors
                  identified are minor — consumable cost variance is within acceptable tolerance, and the
                  cardiac function concerns are expected post-procedure with favorable recovery prognosis.
                  No fraud indicators, no policy exclusion triggers, and full IRDAI compliance achieved.
                </p>
                <div className="wf-suggestion-metrics">
                  <div className="wf-suggestion-metric">
                    <div className="wf-suggestion-metric-label">Risk Level</div>
                    <div className="wf-suggestion-metric-value" style={{ color: 'var(--success)' }}>Low</div>
                  </div>
                  <div className="wf-suggestion-metric">
                    <div className="wf-suggestion-metric-label">Fraud Score</div>
                    <div className="wf-suggestion-metric-value" style={{ fontFamily: 'monospace', color: 'var(--success)' }}>0.02</div>
                  </div>
                  <div className="wf-suggestion-metric">
                    <div className="wf-suggestion-metric-label">Approval Rate</div>
                    <div className="wf-suggestion-metric-value">96%</div>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div className="wf-suggestion-title"><Gavel size={14} style={{ color: 'var(--success)' }} /> AI Final Decision</div>
              <div className="wf-final-decision">
                <div className="wf-final-icon-wrap">
                  <div className="wf-final-icon"><ShieldCheck size={40} /></div>
                  <div className="wf-final-checkmark"><CheckCircle size={14} /></div>
                </div>
                <div className="wf-final-verdict">APPROVED</div>
                <div className="wf-final-verdict-sub">Autonomous decision · Signed & sealed</div>
                <div className="wf-final-confidence">{Math.round(avgConf * 100)}% confidence</div>
                <div className="wf-final-details">
                  {[
                    ['Case ID', 'CLM-2026-001'],
                    ['Claim Amount', '₹2,45,000'],
                    ['Payout To', 'Priya S. Kapoor'],
                  ].map(([k, v]) => (
                    <div key={k} className="wf-final-detail-row">
                      <span className="wf-final-detail-key">{k}</span>
                      <span className="wf-final-detail-val">{v}</span>
                    </div>
                  ))}
                  <div className="wf-final-detail-row">
                    <span className="wf-final-detail-key">Routed To</span>
                    <span className="wf-final-detail-val success">Auto-settlement</span>
                  </div>
                </div>
                <div className="wf-final-exports">
                  <button className="btn btn-ghost btn-sm"><FileCode size={12} /> JSON</button>
                  <button className="btn btn-ghost btn-sm"><FileText size={12} /> PDF</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={{ textAlign: 'center', fontSize: 'var(--text-sm)', color: 'var(--muted)', padding: '32px 0 16px' }}>
        Atlas · Document Intelligence · v1.0 — design prototype
      </div>
    </div>
  );
}
