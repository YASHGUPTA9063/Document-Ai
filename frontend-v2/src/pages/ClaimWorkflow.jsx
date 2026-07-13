import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, CheckCircle, ChevronDown, Download, Loader2, RotateCcw,
  Circle, AlertTriangle, X as XIcon, Brain, Copy, FileOutput, Sparkles,
  ThumbsUp, ThumbsDown, ShieldCheck, ShieldOff, Scale, Gavel, FileText, FileCode, ClipboardList,
} from 'lucide-react';
import { INITIAL_STEPS, stepDuration } from './claimData';
import { runClaimWorkflow, getClaimStatus, getClaimReport, submitClaimDecision } from '../api/client';

/* ─── JSON syntax highlighter ─── */
function highlightJson(json) {
  return json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/(\".*?\")(\s*:)/g, '<span class="json-key">$1</span>$2')
    .replace(/:\s*(\".*?\")/g, ': <span class="json-string">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span class="json-bool">$1</span>')
    .replace(/:\s*(-?\d+(?:\.\d+)?)/g, ': <span class="json-number">$1</span>');
}

/* ─── State icon ─── */
function StateIcon({ state, size = 14 }) {
  if (state === 'running')   return <Loader2 size={size} className="spin" />;
  if (state === 'completed') return <CheckCircle size={size} />;
  if (state === 'warning')   return <AlertTriangle size={size} />;
  if (state === 'failed')    return <XIcon size={size} />;
  return <Circle size={size} />;
}

/* ─── Status label for overall_status ─── */
function OverallStatusBadge({ status }) {
  if (!status) return null;
  const s = status.toUpperCase();
  if (s === 'APPROVE') return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 14px', borderRadius: 8, background: 'var(--success-dim)', color: 'var(--success)', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
      <ShieldCheck size={14} /> APPROVE
    </div>
  );
  if (s === 'REJECT') return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 14px', borderRadius: 8, background: 'rgba(220,38,38,0.12)', color: '#dc2626', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
      <ShieldOff size={14} /> REJECT
    </div>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 14px', borderRadius: 8, background: 'var(--warn-dim)', color: 'var(--warn)', fontWeight: 700, fontSize: 'var(--text-sm)' }}>
      <Scale size={14} /> REVIEW BEFORE APPROVAL
    </div>
  );
}

/* ─── Agent result card ─── */
function AgentResultCard({ name, result }) {
  const [open, setOpen] = useState(false);
  const status = result?.status || 'UNKNOWN';
  const color = status === 'PASS' ? 'var(--success)' : status === 'FAIL' ? '#dc2626' : status === 'FLAG' ? 'var(--warn)' : 'var(--muted)';

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', marginBottom: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: 'var(--surface)', border: 'none', cursor: 'pointer', color: 'var(--text)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>{name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color, background: `${color}18`, padding: '2px 8px', borderRadius: 4 }}>{status}</span>
        </div>
        <ChevronDown size={14} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms', color: 'var(--muted)' }} />
      </button>
      {open && (
        <div style={{ padding: '12px 14px', background: 'var(--surface-2)', borderTop: '1px solid var(--border)' }}>
          {result?.overall_reason && (
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--muted)', marginBottom: 10 }}>{result.overall_reason}</div>
          )}
          {result?.checks?.map((check, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6 }}>
              <span style={{
                fontSize: 'var(--text-xs)', fontWeight: 700, flexShrink: 0, marginTop: 1,
                color: check.result === 'PASS' ? 'var(--success)' : check.result === 'FAIL' ? '#dc2626' : 'var(--warn)'
              }}>
                {check.result}
              </span>
              <div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>{check.name}</div>
                {check.explanation && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', marginTop: 2 }}>{check.explanation}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Structured output view for the Output tab ─── */
function AgentOutputView({ output, state }) {
  if (state === 'waiting') {
    return <div className="wf-placeholder"><FileOutput size={16} /> Output will appear when this step completes…</div>;
  }
  if (state === 'running') {
    return (
      <div>
        <div className="wf-placeholder reasoning"><Loader2 size={16} className="spin" /> Agent is running checks…</div>
        <div className="wf-skeleton-bars" style={{ marginTop: 16, padding: 16, borderRadius: 'var(--radius)', border: '1px solid rgba(59,130,246,0.2)', background: 'rgba(59,130,246,0.05)' }}>
          <div className="wf-skeleton-bar" style={{ width: '60%' }} />
          <div className="wf-skeleton-bar" />
          <div className="wf-skeleton-bar" style={{ width: '80%' }} />
        </div>
      </div>
    );
  }
  if (!output) return <div className="wf-placeholder">No output available.</div>;

  const status = output.status || 'UNKNOWN';
  const statusColor =
    status === 'PASS'  ? 'var(--success)' :
    status === 'FAIL'  ? '#dc2626' :
    status === 'FLAG'  ? 'var(--warn)' :
    status === 'ERROR' ? '#dc2626' : 'var(--muted)';
  const statusBg = `${statusColor}18`;

  const checkColor = r =>
    r === 'PASS'  ? 'var(--success)' :
    r === 'FAIL'  ? '#dc2626' :
    r === 'FLAG'  ? 'var(--warn)' : 'var(--muted)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Status banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 8, background: statusBg, border: `1px solid ${statusColor}30` }}>
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text)' }}>
          {output.agent || 'Agent'}
        </div>
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: statusColor, background: `${statusColor}22`, padding: '3px 10px', borderRadius: 6, letterSpacing: '0.04em' }}>
          {status}
        </span>
      </div>

      {/* Checks list */}
      {output.checks?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {output.checks.map((check, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '9px 12px', borderRadius: 8, background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
              <span style={{ flexShrink: 0, marginTop: 1, fontSize: 'var(--text-xs)', fontWeight: 700, color: checkColor(check.result), background: `${checkColor(check.result)}18`, padding: '2px 7px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                {check.result || '—'}
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text)', marginBottom: check.explanation ? 3 : 0 }}>{check.name}</div>
                {check.explanation && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', lineHeight: 1.5 }}>{check.explanation}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Overall reason */}
      {output.overall_reason && (
        <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 'var(--text-sm)', color: 'var(--muted)', lineHeight: 1.6 }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 6 }}>Overall Reason</div>
          {output.overall_reason}
        </div>
      )}
    </div>
  );
}

/* ─── The CLAIM STEP definitions (maps to 5 agents + generate step) ─── */
const CLAIM_STEPS = [
  {
    id: 'integrity', label: 'Claim Integrity',
    summary: 'Validates completeness, dates, policy, duplicates',
    description: 'Checking required fields, verifying date logic, confirming the policy was active on the incident date, and scanning for duplicate submissions.',
  },
  {
    id: 'medical', label: 'Medical Check',
    summary: 'Validates diagnosis, ICD code, provider, documentation',
    description: 'Validating the diagnosis description, verifying the ICD code format, confirming provider credentials, and checking for supporting medical documentation.',
  },
  {
    id: 'treatment', label: 'Treatment Review',
    summary: 'Validates treatment-diagnosis alignment and billing',
    description: 'Confirming treatment matches the diagnosed condition, reviewing procedure codes, and checking for billing anomalies or over-billing patterns.',
  },
  {
    id: 'disability', label: 'Disability Check',
    summary: 'Validates certificate, severity, limitations',
    description: 'Verifying the disability certificate is present and valid, assessing severity classification, and confirming reported functional limitations are consistent.',
  },
  {
    id: 'litigation', label: 'Litigation Scan',
    summary: 'Detects attorney involvement and fraud indicators',
    description: 'Scanning for attorney representation, cross-referencing prior claim history for fraud patterns, and flagging any legal hold indicators.',
  },
  {
    id: 'report', label: 'Report Generation',
    summary: 'Generates final suggestion and overall decision',
    description: 'Synthesising all agent results into a final recommendation and overall approval decision.',
  },
];

export function ClaimWorkflow() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const claimId    = searchParams.get('claim_id');
  const viewReport = searchParams.get('view_report') === '1';

  const [steps, setSteps]     = useState(() => CLAIM_STEPS.map(s => ({ ...s, state: 'waiting', duration: undefined })));
  const [running, setRunning] = useState(false);
  const [done, setDone]       = useState(false);
  const [active, setActive]   = useState(CLAIM_STEPS[0].id);
  const [openSteps, setOpen]  = useState({});
  const [tab, setTab]         = useState('thought');
  const [report, setReport]   = useState(null);
  const [claimStatus, setClaimStatus] = useState(null);
  const [error, setError]     = useState(null);
  const [decisionSent, setDecisionSent] = useState(false);
  const [decisionResult, setDecisionResult] = useState(null);
  const startedRef             = useRef(false);
  const pollRef                = useRef(null);      // holds setInterval id
  const pollFnRef              = useRef(null);      // stable ref to latest pollStatus

  /* ── Map backend claim status → step states ─── */
  const mapStatusToSteps = useCallback((status, agentResults) => {
    // Keys must match what the backend stores in agent_results
    const order = ['claim_integrity', 'medical', 'treatment', 'disability', 'litigation', 'report'];
    const processingSteps = ['checking_integrity', 'checking_medical', 'checking_treatment', 'checking_disability', 'checking_litigation', 'generating_report'];

    const isCompleted = status === 'completed' || status === 'approved' || status === 'rejected';
    const currentIdx = processingSteps.indexOf(status);

    setSteps(prev => prev.map((s, idx) => {
      const agentKey = order[idx];

      if (agentResults && agentResults[agentKey]) {
        // Agent completed — use real data
        const result = agentResults[agentKey];
        const agentStatus = result.status;
        return {
          ...s,
          state: agentStatus === 'ERROR' ? 'failed' : agentStatus === 'FAIL' ? 'warning' : 'completed',
          agentThought: result.overall_reason || '',
          output: result,
          outputKind: 'json',
          confidence: agentStatus === 'PASS' ? 0.97 : 0.7,
        };
      } else if (isCompleted) {
        // Workflow done but no agent result for this step (e.g. 'report' step) — mark completed
        return { ...s, state: 'completed' };
      } else if (currentIdx >= 0 && idx === currentIdx) {
        return { ...s, state: 'running' };
      } else if (currentIdx >= 0 && idx < currentIdx) {
        return { ...s, state: 'completed' };
      }
      return { ...s, state: 'waiting' };
    }));
  }, []);

  /* ── Poll claim status ─── */
  // Defined once; pollFnRef keeps the latest version stable so setInterval never goes stale.
  const pollStatus = useCallback(async () => {
    if (!claimId) return;
    try {
      const statusData = await getClaimStatus(claimId);
      setClaimStatus(statusData);

      const cs = statusData.claim_status;

      if (cs === 'completed' || cs === 'approved' || cs === 'rejected') {
        clearInterval(pollRef.current);
        setRunning(false);
        setDone(true);

        // Restore adjuster decision from DB status so refresh doesn't reset it
        if (cs === 'approved' || cs === 'rejected') {
          setDecisionResult(cs);
          setDecisionSent(true);
        }

        try {
          const reportData = await getClaimReport(claimId);
          setReport(reportData);
          setSteps(prev => prev.map(s => ({ ...s, state: 'completed' })));
          if (reportData.agent_results) {
            mapStatusToSteps('completed', reportData.agent_results);
          }
        } catch (e) {
          console.error('Failed to load report:', e);
        }
      } else if (cs === 'processing' || cs.startsWith('checking_') || cs === 'generating_report') {
        setRunning(true);
        mapStatusToSteps(cs, statusData.agent_results || null);
      } else if (cs === 'failed') {
        clearInterval(pollRef.current);
        setRunning(false);
        setError('Claim workflow failed. Please try again.');
      }
    } catch (e) {
      console.error('Poll error:', e);
    }
  }, [claimId, mapStatusToSteps]);

  // Keep the ref in sync so the interval always calls the latest closure.
  pollFnRef.current = pollStatus;

  const startPolling = useCallback(() => {
    clearInterval(pollRef.current);
    // Use ref so the interval callback is always fresh — avoids stale closure / self-cancel
    pollRef.current = setInterval(() => pollFnRef.current(), 4000);
    pollFnRef.current(); // immediate first tick
  }, []);

  /* ── On mount: check current status first, then start / resume / load ─── */
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    if (!claimId) {
      setError('No claim ID provided. Go back and select a claim.');
      return;
    }

    if (viewReport) {
      // Explicit report view — load report and status in parallel
      setDone(true);
      Promise.all([getClaimReport(claimId), getClaimStatus(claimId)])
        .then(([r, statusData]) => {
          setReport(r);
          // Restore adjuster decision so buttons don't reappear on refresh
          const cs = statusData.claim_status;
          if (cs === 'approved' || cs === 'rejected') {
            setDecisionResult(cs);
            setDecisionSent(true);
          }
          if (r.agent_results) {
            setSteps(prev => prev.map((s, idx) => {
              const key = ['integrity', 'medical', 'treatment', 'disability', 'litigation', 'report'][idx];
              const result = r.agent_results[key];
              if (!result) return { ...s, state: 'completed' };
              return {
                ...s,
                state: result.status === 'ERROR' ? 'failed' : result.status === 'FAIL' ? 'warning' : 'completed',
                agentThought: result.overall_reason || '',
                output: result,
                outputKind: 'json',
                confidence: 0.95,
              };
            }));
          }
        })
        .catch(e => setError(`Failed to load report: ${e.message}`));
      return;
    }

    // Always check current status first — handles refresh mid-flight cleanly
    getClaimStatus(claimId).then(statusData => {
      const cs = statusData.claim_status;

      if (cs === 'completed' || cs === 'approved' || cs === 'rejected') {
        // Restore adjuster decision immediately — don't wait for pollStatus chain
        if (cs === 'approved' || cs === 'rejected') {
          setDecisionResult(cs);
          setDecisionSent(true);
        }
        // Load report
        pollFnRef.current();
      } else if (cs === 'processing' || cs.startsWith('checking_') || cs === 'generating_report') {
        // Already running (e.g. after a refresh) — resume polling, don't re-POST /run
        setRunning(true);
        mapStatusToSteps(cs, null);
        startPolling();
      } else {
        // Not started yet — fire the workflow then poll
        setRunning(true);
        runClaimWorkflow(claimId)
          .catch(() => { /* 409 or other — still poll below */ })
          .finally(() => startPolling());
      }
    }).catch(() => {
      // Status fetch failed — fall back to starting workflow
      setRunning(true);
      runClaimWorkflow(claimId)
        .catch(() => {})
        .finally(() => startPolling());
    });

    return () => clearInterval(pollRef.current);
  }, [claimId, viewReport]); // pollStatus intentionally omitted — use pollFnRef to stay stable

  /* ── Auto-scroll on done ─── */
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => document.getElementById('completion-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 400);
    return () => clearTimeout(t);
  }, [done]);

  const restart = useCallback(() => navigate('/claim-process'), [navigate]);

  const handleDecision = useCallback(async (decision) => {
    if (!claimId || decisionSent) return;
    setDecisionSent(true);
    try {
      const result = await submitClaimDecision(claimId, decision);
      setDecisionResult(result.decision);
    } catch (e) {
      alert(`Failed to submit decision: ${e.message}`);
      setDecisionSent(false);
    }
  }, [claimId, decisionSent]);

  const completedCount  = steps.filter(s => s.state === 'completed').length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);
  const currentStep     = steps.find(s => s.id === active) || steps[0];
  const isJson          = currentStep.outputKind === 'json';
  const jsonContent     = currentStep.state === 'waiting' ? '// Waiting…' : isJson ? JSON.stringify(currentStep.output, null, 2) : String(currentStep.output ?? '');
  const thoughtText     = currentStep.agentThought ?? '';

  if (error) {
    return (
      <div className="claim-page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 16 }}>
        <AlertTriangle size={32} color="var(--warn)" />
        <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>Workflow Error</div>
        <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>{error}</div>
        <button className="btn btn-primary" onClick={restart}><ArrowLeft size={14} /> Back to Claims</button>
      </div>
    );
  }

  return (
    <div className="claim-page">
      {/* Status bar */}
      <div className={`wf-status-bar${done ? ' done' : ''}`} style={{ marginBottom: 20 }}>
        <div className="wf-status-left">
          <button className="btn btn-ghost btn-sm" onClick={restart}>
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
              {claimId} · {completedCount}/{steps.length} agents complete
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
                <RotateCcw size={14} /> Back
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Three panel layout */}
      <div style={{ display: 'flex', gap: 20, flex: 1, padding: 20, minHeight: 0 }}>
        {/* ── Left Sidebar: Stepper (HIDDEN) ── 
        <div className="wf-sidebar">
          <div className="wf-timeline-header">
            <div>
              <div className="wf-timeline-title">AI execution timeline</div>
              <div className="wf-timeline-sub">5 validation agents + report</div>
            </div>
            <span className="wf-timeline-tag">{claimId || 'claim'}</span>
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
                          {s.output?.status && s.state === 'completed' && (
                            <span className="wf-step-conf" style={{
                              color: s.output.status === 'PASS' ? 'var(--success)' : s.output.status === 'FAIL' ? '#dc2626' : 'var(--warn)'
                            }}>{s.output.status}</span>
                          )}
                          <ChevronDown size={12} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 150ms' }} />
                        </div>
                      </div>
                      <div className="wf-step-summary">{s.summary}</div>
                    </div>
                  </button>
                  {isOpen && s.state !== 'waiting' && (
                    <div className="wf-step-thought">
                      {s.state === 'running' ? (
                        <div className="wf-step-reasoning"><Loader2 size={12} className="spin" /> Agent is running checks…</div>
                      ) : (
                        <>
                          <div className="wf-step-thought-label"><Brain size={12} /> Agent Result</div>
                          <div className="wf-step-thought-text">{thoughtText || s.summary}</div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        */}

        {/* ── Pipeline Graph ── */}
        <div className="wf-pipeline" style={{ flex: 1 }}>
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
            <svg className="wf-graph-dots" width="100%" height="100%">
              <defs>
                <pattern id="dotPattern" x="0" y="0" width="18" height="18" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="1" fill="var(--border)" opacity="0.4" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#dotPattern)" />
            </svg>
            <div className="wf-graph-grid-wrap">
              <svg className="wf-graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none">
                {steps.slice(0, -1).map((s, i) => {
                  const next = steps[i + 1];
                  const cols = 2, rows = Math.ceil(steps.length / cols);
                  const cx = col => col === 0 ? 25 : 75;
                  const rowH = 100 / rows;
                  const cy = row => row * rowH + rowH / 2;
                  const sCol = i % cols, sRow = Math.floor(i / cols);
                  const tCol = (i + 1) % cols, tRow = Math.floor((i + 1) / cols);
                  let sx = cx(sCol);
                  let sy = cy(sRow);
                  let tx = cx(tCol);
                  let ty = cy(tRow);
                  
                  if (sRow === tRow) {
                    // Horizontal connection
                    sx += 14;
                    tx -= 14;
                  } else {
                    // Vertical/Diagonal connection
                    sy += 6;
                    ty -= 6;
                  }

                  const finished = ['completed', 'warning', 'failed'];
                  const isComplete = finished.includes(s.state) && finished.includes(next.state);
                  
                  let d = '';
                  if (sRow === tRow) {
                    d = `M ${sx} ${sy} L ${tx} ${ty}`;
                  } else {
                    const midY = (sy + ty) / 2;
                    d = `M ${sx} ${sy} C ${sx} ${midY}, ${tx} ${midY}, ${tx} ${ty}`;
                  }
                  return (
                    <path key={`${s.id}->${next.id}`} d={d} fill="none"
                      stroke={isComplete ? 'var(--success)' : 'var(--border)'}
                      strokeWidth={isComplete ? 2 : 1.25}
                      vectorEffect="non-scaling-stroke"
                    />
                  );
                })}
              </svg>
              <div className="wf-graph-grid">
                {steps.map(s => {
                  const isActive = active === s.id;
                  return (
                    <div key={s.id} className={`wf-graph-node ${s.state}${isActive ? ' active' : ''}`} onClick={() => setActive(s.id)}>
                      <div className="wf-graph-node-head">
                        <div className={`wf-graph-node-icon ${s.state}`}><StateIcon state={s.state} size={12} /></div>
                        <div className="wf-graph-node-label">{s.label}</div>
                      </div>
                      <div className="wf-graph-node-foot">
                        <span className={`wf-graph-node-state ${s.state}`}>
                          {s.state === 'waiting' ? 'Waiting' : s.state === 'running' ? 'Running' : s.output?.status || 'Done'}
                        </span>
                        <span className="wf-graph-node-dur">{s.output?.status || '—'}</span>
                      </div>
                      {s.state === 'running' && (
                        <div className="wf-pipe-node-shimmer"><div className="wf-pipe-node-shimmer-bar" /></div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* ── Agent Inspector ── */}
        <div className="wf-inspector" style={{ flex: 1 }}>
          <div className="wf-inspector-header">
            <div style={{ minWidth: 0 }}>
              <div className="wf-inspector-title">Agent Inspector</div>
              <div className="wf-inspector-sub">{currentStep.label} · {currentStep.state === 'running' ? 'running…' : currentStep.state}</div>
            </div>
            <select className="styled-select" value={currentStep.id} onChange={e => setActive(e.target.value)} style={{ width: 170, fontSize: 'var(--text-sm)', padding: '5px 8px' }}>
              {steps.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
          <div className="wf-inspector-tabs">
            {[
              { key: 'thought', icon: <Brain size={12} />, label: 'Agent Thought' },
              { key: 'output',  icon: <FileOutput size={12} />, label: 'Output' },
              { key: 'meta',    icon: <Sparkles size={12} />, label: 'Metadata' },
            ].map(t => (
              <button key={t.key} className={`wf-inspector-tab${tab === t.key ? (t.key === 'thought' ? ' active' : ' active-output') : ''}`} onClick={() => setTab(t.key)}>
                {t.icon} {t.label}
              </button>
            ))}
            <div className="wf-inspector-actions">
              <button className="btn btn-ghost btn-icon btn-sm" title="Copy" onClick={() => navigator.clipboard?.writeText(tab === 'thought' ? thoughtText : jsonContent)}>
                <Copy size={14} />
              </button>
            </div>
          </div>
          <div className="wf-inspector-body">
            {tab === 'thought' && (
              currentStep.state === 'waiting' ? (
                <div className="wf-placeholder"><Brain size={16} /> Agent will reason when this step starts…</div>
              ) : currentStep.state === 'running' ? (
                <div>
                  {/* Description of what this agent checks — shown while running */}
                  <div className="wf-thought-chain-label"><ClipboardList size={14} /> What this agent checks</div>
                  <div className="wf-thought-chain-box" style={{ marginBottom: 16 }}>
                    <div className="wf-thought-chain-text">{currentStep.description}</div>
                  </div>
                  <div className="wf-placeholder reasoning"><Loader2 size={16} className="spin" /> Agent is reasoning…</div>
                  <div className="wf-skeleton-bars" style={{ marginTop: 16, padding: 16, borderRadius: 'var(--radius)', border: '1px solid rgba(59,130,246,0.2)', background: 'rgba(59,130,246,0.05)' }}>
                    <div className="wf-skeleton-bar" style={{ width: '75%' }} />
                    <div className="wf-skeleton-bar" />
                    <div className="wf-skeleton-bar" />
                  </div>
                </div>
              ) : (
                <div>
                  {/* Agent reasoning on top */}
                  <div className="wf-thought-chain-label"><Brain size={14} /> Agent Reasoning</div>
                  <div className="wf-thought-chain-box" style={{ marginBottom: 16 }}>
                    <div className="wf-thought-chain-text">{thoughtText || 'No thought available.'}</div>
                  </div>
                  {/* Description of checks below, secondary */}
                  <div className="wf-thought-chain-label" style={{ color: 'var(--muted)' }}><ClipboardList size={14} /> Checks performed</div>
                  <div className="wf-thought-chain-box">
                    <div className="wf-thought-chain-text" style={{ color: 'var(--muted)' }}>{currentStep.description}</div>
                  </div>
                </div>
              )
            )}
            {tab === 'output' && (
              <AgentOutputView output={currentStep.output} state={currentStep.state} />
            )}
            {tab === 'meta' && (
              <div className="wf-meta-grid">
                {[
                  ['Agent', currentStep.label],
                  ['State', currentStep.state],
                  ['Status', currentStep.output?.status || '—'],
                  ['Claim ID', claimId || '—'],
                  ['Model', 'mistral-large-latest'],
                  ['Mode', 'autonomous'],
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

      {/* ── Completion Summary with real report ── */}
      {done && report && (
        <div id="completion-summary" className="wf-completion" style={{ marginBottom: 20 }}>
          {/* Header */}
          <div className="wf-completion-header">
            <div className="wf-completion-icon"><CheckCircle size={20} /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="wf-completion-title">Claim Analysis Complete</div>
              <div className="wf-completion-sub">
                {report.claim_id} · {report.claimant_name} · {report.processed_at ? new Date(report.processed_at).toLocaleString('en-IN') : ''}
              </div>
            </div>
            <div className="wf-completion-actions">
              <OverallStatusBadge status={report.overall_status} />
              <button className="btn btn-ghost btn-sm" onClick={restart}><RotateCcw size={14} /> Back to Claims</button>
            </div>
          </div>

          {/* Agent results accordion */}
          <div style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 12 }}>
              Agent Results
            </div>
            {Object.entries(report.agent_results || {}).map(([key, result]) => (
              <AgentResultCard key={key} name={key} result={result} />
            ))}
          </div>

          {/* AI Suggestion + Decision */}
          <div className="wf-decision-grid" style={{ padding: '0 20px 20px' }}>
            <div>
              <div className="wf-suggestion-title"><Brain size={14} style={{ color: 'var(--accent)' }} /> AI Suggestion</div>
              <div className="wf-suggestion-box">
                <div className="wf-suggestion-rec"><Sparkles size={16} /> Recommendation: {report.overall_status}</div>
                <p className="wf-suggestion-text">
                  {report.suggestion || 'No suggestion available.'}
                </p>
              </div>
            </div>

            <div>
              <div className="wf-suggestion-title"><Gavel size={14} style={{ color: 'var(--success)' }} /> Adjuster Decision</div>
              <div className="wf-final-decision">
                {decisionResult ? (
                  <>
                    <div className="wf-final-icon-wrap">
                      <div className="wf-final-icon" style={decisionResult === 'rejected' ? { background: 'rgba(220,38,38,0.12)', color: '#dc2626' } : {}}>
                        {decisionResult === 'approved' ? <ShieldCheck size={40} /> : <ShieldOff size={40} />}
                      </div>
                    </div>
                    <div className="wf-final-verdict" style={{ color: decisionResult === 'rejected' ? '#dc2626' : undefined }}>
                      {decisionResult.toUpperCase()}
                    </div>
                    <div className="wf-final-verdict-sub">Decision recorded successfully</div>
                  </>
                ) : (
                  <>
                    <div style={{ marginBottom: 16, color: 'var(--muted)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>
                      Review the AI suggestion and make your decision.
                    </div>
                    <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                      <button
                        className="btn btn-primary"
                        disabled={decisionSent}
                        onClick={() => handleDecision('approve')}
                        style={{ background: 'var(--success)', borderColor: 'var(--success)' }}
                      >
                        <ShieldCheck size={14} /> Accept Claim
                      </button>
                      <button
                        className="btn btn-ghost"
                        disabled={decisionSent}
                        onClick={() => handleDecision('reject')}
                        style={{ color: '#dc2626', borderColor: '#dc2626' }}
                      >
                        <ShieldOff size={14} /> Reject Claim
                      </button>
                    </div>
                    <div style={{ marginTop: 16, color: 'var(--muted)', fontSize: 'var(--text-xs)', textAlign: 'center' }}>
                      Claim: {report.claim_id} · {report.claimant_name}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading state before report */}
      {done && !report && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Loader2 size={24} className="spin" style={{ color: 'var(--accent)', margin: '0 auto 12px', display: 'block' }} />
          <div style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>Loading report…</div>
        </div>
      )}

      {/* Footer */}
      <div style={{ textAlign: 'center', fontSize: 'var(--text-sm)', color: 'var(--muted)', padding: '32px 0 16px' }}>
        Atlas · Document Intelligence · Claim Processing
      </div>
    </div>
  );
}
