import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield, ShieldCheck, ShieldAlert, ShieldX,
  GitCompare, CheckCircle, XCircle, AlertTriangle, Clock,
  Fingerprint, Camera, Loader2, RefreshCw, ArrowLeft,
  ChevronDown, ChevronUp, FileText, Sparkles
} from 'lucide-react';
import { getKycVerdict } from '../api/client';
import { useApp } from '../store/AppStore';

// ── Shared result chips ────────────────────────────────────────────────────────

function ResultChip({ result, score }) {
  const cfg = {
    MATCH:     { color: 'var(--success)',  bg: 'var(--success-dim)',  border: 'var(--success-border)',  icon: '✓' },
    MISMATCH:  { color: 'var(--danger)',   bg: 'var(--danger-dim)',   border: 'var(--danger-border)',   icon: '✗' },
    NOT_FOUND: { color: 'var(--muted)',    bg: 'var(--surface)',      border: 'var(--border)',           icon: '?' },
  }[result] || { color: 'var(--muted)', bg: 'var(--surface)', border: 'var(--border)', icon: '?' };

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700,
      color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`,
    }}>
      {cfg.icon} {result}
      {score != null && (
        <span style={{ fontWeight: 400, opacity: 0.85, marginLeft: 3 }}>
          {Math.round(score * 100)}%
        </span>
      )}
    </span>
  );
}

function FieldRow({ label, val1, val2, check, col1Label, col2Label }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr 1fr auto', gap: 8, alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      <span style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'monospace', wordBreak: 'break-all' }}>{val1 || <em style={{ color: 'var(--muted)' }}>—</em>}</span>
      <span style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'monospace', wordBreak: 'break-all' }}>{val2 || <em style={{ color: 'var(--muted)' }}>—</em>}</span>
      <ResultChip result={check?.result || 'NOT_FOUND'} score={check?.score ?? null} />
    </div>
  );
}

// ── Overall badge for cross-validation ──────────────────────────────────────────

function OverallBadge({ overall }) {
  const cfg = {
    PASS:       { color: 'var(--success)', bg: 'var(--success-dim)',      border: 'var(--success-border)', label: '✓ PASS', icon: CheckCircle },
    FAIL:       { color: 'var(--danger)',  bg: 'var(--danger-dim)',       border: 'var(--danger-border)',  label: '✗ FAIL', icon: XCircle },
    INCOMPLETE: { color: 'var(--warn)',    bg: 'rgba(245,158,11,0.07)',   border: 'rgba(245,158,11,0.25)', label: '⚠ INCOMPLETE', icon: AlertTriangle },
  }[overall] || { color: 'var(--muted)', bg: 'var(--surface)', border: 'var(--border)', label: '? UNKNOWN', icon: Clock };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 14px', borderRadius: 8,
      background: cfg.bg, border: `1px solid ${cfg.border}`,
    }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: cfg.color, display: 'flex', alignItems: 'center', gap: 6 }}>
        <cfg.icon size={14} /> {cfg.label}
      </span>
    </div>
  );
}

// ── Cross-validation card ───────────────────────────────────────────────────────

function CrossValidationCard({ title, icon, result, fields, doc1Label, doc2Label, doc1Info, doc2Info }) {
  const [expanded, setExpanded] = useState(true);

  if (!result) return null;

  return (
    <div className="card" style={{ flex: 1, minWidth: 320 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <GitCompare size={16} style={{ color: 'var(--accent)' }} />
          <div className="card-title" style={{ margin: 0 }}>{title}</div>
        </div>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setExpanded(e => !e)}
          title={expanded ? 'Collapse' : 'Expand'}
          style={{ padding: 4 }}
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      <OverallBadge overall={result.overall} />

      {result.overall === 'INCOMPLETE' && result.missing?.length > 0 && (
        <div style={{ fontSize: 12, color: 'var(--warn)', background: 'rgba(245,158,11,0.06)', padding: '8px 12px', borderRadius: 6, border: '1px solid rgba(245,158,11,0.2)', marginTop: 10 }}>
          <AlertTriangle size={12} style={{ display: 'inline', marginRight: 5 }} />
          Missing: {result.missing.map(m => <strong key={m} style={{ marginLeft: 4 }}>{m.replace('_', ' ').toUpperCase()}</strong>)}
        </div>
      )}

      {expanded && doc1Info && doc2Info && (
        <div style={{ background: 'var(--surface)', borderRadius: 8, padding: '10px 12px', marginTop: 10 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr 1fr auto', gap: 8, marginBottom: 6 }}>
            <span />
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{doc1Label}</div>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 1 }}>{doc1Info.filename}</div>
            </div>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{doc2Label}</div>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 1 }}>{doc2Info.filename}</div>
            </div>
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Result</span>
          </div>
          {fields.map(f => (
            <FieldRow key={f.label} label={f.label} val1={f.val1} val2={f.val2} check={f.check} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Biometric verification card ─────────────────────────────────────────────────

function BiometricCard({ title, icon: Icon, verification, type }) {
  if (!verification) {
    return (
      <div className="card" style={{ flex: 1, minWidth: 280 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Icon size={16} style={{ color: 'var(--muted)' }} />
          <div className="card-title" style={{ margin: 0 }}>{title}</div>
        </div>
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
          padding: '24px 16px', borderRadius: 8, border: '1.5px dashed var(--border)',
          background: 'var(--surface-sunken)', textAlign: 'center',
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: '50%',
            background: 'rgba(107,114,128,0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon size={22} style={{ color: 'var(--muted)', opacity: 0.5 }} />
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>Not Performed</div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            Go to the Extraction page and verify the {type} on a KYC document first.
          </div>
        </div>
      </div>
    );
  }

  const verdict = (verification.verdict || 'unknown').toLowerCase();
  const isGenuine = verdict === 'genuine' || verdict === 'same_person';
  const isForged = verdict === 'forged' || verdict === 'different_person';
  const isUncertain = !isGenuine && !isForged;

  const verdictCfg = isGenuine
    ? { color: 'var(--success)', bg: 'var(--success-dim)', border: 'var(--success-border)', label: type === 'photo' ? 'SAME PERSON' : 'GENUINE', icon: CheckCircle }
    : isForged
    ? { color: 'var(--danger)', bg: 'var(--danger-dim)', border: 'var(--danger-border)', label: type === 'photo' ? 'DIFFERENT PERSON' : 'FORGED', icon: XCircle }
    : { color: 'var(--warn)', bg: 'rgba(245,158,11,0.07)', border: 'rgba(245,158,11,0.25)', label: 'UNCERTAIN', icon: AlertTriangle };

  const confidence = type === 'photo'
    ? (verification.output_code ? `${verification.output_code}/5` : 'N/A')
    : (verification.judge?.confidence ?? verification.confidence ?? 'N/A') + '%';

  return (
    <div className="card" style={{ flex: 1, minWidth: 280 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Icon size={16} style={{ color: verdictCfg.color }} />
        <div className="card-title" style={{ margin: 0 }}>{title}</div>
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px', borderRadius: 8,
        background: verdictCfg.bg, border: `1px solid ${verdictCfg.border}`,
        marginBottom: 10,
      }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: verdictCfg.color, display: 'flex', alignItems: 'center', gap: 6 }}>
          <verdictCfg.icon size={14} /> {verification.verdict_label || verdictCfg.label}
        </span>
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>Confidence: <strong>{confidence}</strong></span>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 11, color: 'var(--text-dim)' }}>
        <FileText size={11} />
        <span>Source: <strong style={{ color: 'var(--text)' }}>{verification.filename}</strong></span>
        <span className="badge badge-cyan" style={{ fontSize: 9 }}>{(verification.doc_type || '').replace(/_/g, ' ')}</span>
      </div>
    </div>
  );
}

// ── Final verdict display ───────────────────────────────────────────────────────

function FinalVerdict({ data, onApprove, onReject }) {
  if (!data) return null;

  const verdict = (data.verdict || 'NEEDS_REVIEW').toUpperCase();
  const verdictCfg = {
    APPROVED: {
      color: '#10b981', bg: 'linear-gradient(135deg, rgba(16,185,129,0.12) 0%, rgba(16,185,129,0.04) 100%)',
      border: 'rgba(16,185,129,0.35)', icon: ShieldCheck, glow: 'rgba(16,185,129,0.25)',
    },
    REJECTED: {
      color: '#ef4444', bg: 'linear-gradient(135deg, rgba(239,68,68,0.12) 0%, rgba(239,68,68,0.04) 100%)',
      border: 'rgba(239,68,68,0.35)', icon: ShieldX, glow: 'rgba(239,68,68,0.25)',
    },
    NEEDS_REVIEW: {
      color: '#f59e0b', bg: 'linear-gradient(135deg, rgba(245,158,11,0.12) 0%, rgba(245,158,11,0.04) 100%)',
      border: 'rgba(245,158,11,0.35)', icon: ShieldAlert, glow: 'rgba(245,158,11,0.25)',
    },
  }[verdict] || {
    color: '#f59e0b', bg: 'linear-gradient(135deg, rgba(245,158,11,0.12) 0%, rgba(245,158,11,0.04) 100%)',
    border: 'rgba(245,158,11,0.35)', icon: ShieldAlert, glow: 'rgba(245,158,11,0.25)',
  };

  const VerdictIcon = verdictCfg.icon;

  return (
    <div className="kyc-verdict-reveal" style={{
      background: verdictCfg.bg,
      border: `1.5px solid ${verdictCfg.border}`,
      borderRadius: 16,
      padding: '28px 32px',
      boxShadow: `0 0 40px ${verdictCfg.glow}, 0 8px 32px rgba(0,0,0,0.12)`,
      animation: 'verdictReveal 0.5s ease-out',
    }}>
      {/* Verdict header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%',
          background: `${verdictCfg.color}15`,
          border: `2px solid ${verdictCfg.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          animation: 'verdictPulse 2s ease-in-out infinite',
        }}>
          <VerdictIcon size={28} style={{ color: verdictCfg.color }} />
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, color: verdictCfg.color, letterSpacing: '0.04em' }}>
            {verdict.replace('_', ' ')}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 2 }}>
            KYC Confidence: <strong style={{ color: 'var(--text)' }}>{data.confidence}%</strong>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div style={{
        fontSize: 14, fontWeight: 600, color: 'var(--text)',
        marginBottom: 12, lineHeight: 1.5,
      }}>
        {data.summary}
      </div>

      {/* Reasoning */}
      <div style={{
        fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7,
        padding: '12px 16px', borderRadius: 10,
        background: 'rgba(0,0,0,0.08)', border: '1px solid rgba(255,255,255,0.05)',
        marginBottom: 14,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          <Sparkles size={11} /> AI Analysis
        </div>
        {data.reasoning}
      </div>

      {/* Risk flags */}
      {data.risk_flags && data.risk_flags.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--warn)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
            <AlertTriangle size={11} /> Risk Flags
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {data.risk_flags.map((flag, i) => (
              <span key={i} style={{
                fontSize: 11, padding: '3px 10px', borderRadius: 99,
                background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)',
                color: 'var(--warn)',
              }}>
                {flag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Checklist summary */}
      <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
          Checks Summary
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <CheckSummaryRow
            label="Passport ↔ Driving License"
            status={data.checks?.passport_dl?.overall}
          />
          <CheckSummaryRow
            label="Utility Bill ↔ Bank Statement"
            status={data.checks?.address?.overall}
          />
          <CheckSummaryRow
            label="Signature Verification"
            status={data.checks?.signature ? getBiometricStatus(data.checks.signature) : 'NOT_DONE'}
          />
          <CheckSummaryRow
            label="Photo / Face Verification"
            status={data.checks?.photo ? getBiometricStatus(data.checks.photo) : 'NOT_DONE'}
          />
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
        <button
          className="btn btn-primary"
          onClick={onApprove}
          style={{
            flex: 1, padding: '12px 0', fontSize: 13, fontWeight: 700,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            borderRadius: 8,
            background: 'linear-gradient(135deg, var(--success) 0%, #059669 100%)',
            boxShadow: '0 4px 14px rgba(16,185,129,0.25)',
            border: 'none',
            color: '#fff',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={e => { e.target.style.transform = 'translateY(-1px)'; e.target.style.boxShadow = '0 6px 20px rgba(16,185,129,0.3)'; }}
          onMouseLeave={e => { e.target.style.transform = 'translateY(0)'; e.target.style.boxShadow = '0 4px 14px rgba(16,185,129,0.25)'; }}
        >
          <CheckCircle size={16} />
          Approve KYC
        </button>
        <button
          className="btn btn-outline"
          onClick={onReject}
          style={{
            flex: 1, padding: '12px 0', fontSize: 13, fontWeight: 700,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            borderRadius: 8,
            borderColor: 'var(--danger-border)',
            color: 'var(--danger)',
            background: 'var(--danger-dim)',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={e => { e.target.style.background = 'rgba(239,68,68,0.15)'; }}
          onMouseLeave={e => { e.target.style.background = 'var(--danger-dim)'; }}
        >
          <XCircle size={16} />
          Reject KYC
        </button>
      </div>
    </div>
  );
}

function getBiometricStatus(v) {
  if (!v) return 'NOT_DONE';
  const verdict = (v.verdict || '').toLowerCase();
  if (verdict === 'genuine' || verdict === 'same_person') return 'PASS';
  if (verdict === 'forged' || verdict === 'different_person') return 'FAIL';
  return 'INCOMPLETE';
}

function CheckSummaryRow({ label, status }) {
  const cfg = {
    PASS:     { color: 'var(--success)', icon: <CheckCircle size={12} />, text: 'Pass' },
    FAIL:     { color: 'var(--danger)',  icon: <XCircle size={12} />,     text: 'Fail' },
    INCOMPLETE: { color: 'var(--warn)',  icon: <AlertTriangle size={12} />, text: 'Incomplete' },
    NOT_DONE: { color: 'var(--muted)',   icon: <Clock size={12} />,       text: 'Not Done' },
  }[status] || { color: 'var(--muted)', icon: <Clock size={12} />, text: status || 'Unknown' };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '6px 10px', borderRadius: 6, background: 'rgba(0,0,0,0.06)',
    }}>
      <span style={{ fontSize: 12, color: 'var(--text)' }}>{label}</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 600, color: cfg.color }}>
        {cfg.icon} {cfg.text}
      </span>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────────

export function KycVerdict() {
  const navigate = useNavigate();
  const { toast } = useApp();
  const [loading, setLoading] = useState(false);
  const [verdictData, setVerdictData] = useState(null);
  const [showVerdict, setShowVerdict] = useState(false);
  const [error, setError] = useState(null);

  const loadVerdict = async () => {
    setLoading(true);
    setError(null);
    setShowVerdict(false);
    try {
      const data = await getKycVerdict();
      setVerdictData(data);
      
      // Auto-show if all checks are completed
      const isPassportDLDone = data.checks?.passport_dl?.overall && data.checks?.passport_dl?.overall !== 'INCOMPLETE';
      const isAddressDone = data.checks?.address?.overall && data.checks?.address?.overall !== 'INCOMPLETE';
      const isSigDone = !!data.checks?.signature;
      const isPhotoDone = !!data.checks?.photo;
      
      if (isPassportDLDone && isAddressDone && isSigDone && isPhotoDone) {
        setShowVerdict(true);
      }
    } catch (e) {
      setError(e.message);
      toast('Failed to load KYC verdict: ' + e.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadVerdict(); }, []);

  const handleSeeResult = () => {
    setShowVerdict(true);
  };

  const handleApprove = () => {
    toast('KYC Approved Successfully!', 'success');
    navigate('/validation');
  };

  const handleReject = () => {
    toast('KYC Rejected!', 'warn');
    navigate('/validation');
  };

  // Extract cross-validation data from the response
  const passportDL = verdictData?.checks?.passport_dl;
  const address = verdictData?.checks?.address;
  const sigVerification = verdictData?.checks?.signature;
  const photoVerification = verdictData?.checks?.photo;

  // Build field arrays for cross-validation cards
  const passportDLFields = passportDL?.passport && passportDL?.dl ? [
    { label: 'Name', val1: passportDL.passport.name, val2: passportDL.dl.name, check: passportDL.checks?.name },
    { label: 'DOB', val1: passportDL.passport.dob, val2: passportDL.dl.dob, check: passportDL.checks?.dob },
  ] : [];

  const addressFields = address?.utility && address?.bank ? [
    { label: 'Address', val1: address.utility.address, val2: address.bank.address, check: address.checks?.address },
  ] : [];

  return (
    <div className="page">
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/validation')} title="Back to Validation" style={{ padding: 6 }}>
            <ArrowLeft size={16} />
          </button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Shield size={20} style={{ color: 'var(--accent)' }} />
              <h1 style={{ fontSize: 20, fontWeight: 800, margin: 0, color: 'var(--text)' }}>
                Final KYC Decision
              </h1>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 3, marginLeft: 28 }}>
              Consolidated cross-document validation & biometric verification results
            </div>
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={loadVerdict} disabled={loading} title="Refresh">
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {/* Loading state */}
      {loading && !verdictData && (
        <div className="card" style={{ textAlign: 'center', padding: '40px 20px' }}>
          <Loader2 size={32} className="spin" style={{ color: 'var(--accent)', margin: '0 auto 12px' }} />
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>Analyzing KYC documents…</div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>Running cross-validations, checking biometric verifications, and computing AI verdict</div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="card" style={{ borderColor: 'var(--danger-border)', background: 'var(--danger-dim)', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--danger)', fontSize: 13 }}>
            <XCircle size={16} />
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {verdictData && (
        <>
          {/* Cross-Validations Section */}
          <div style={{ marginBottom: 20 }}>
            <div style={{
              fontSize: 11, fontWeight: 700, color: 'var(--muted)',
              textTransform: 'uppercase', letterSpacing: '0.08em',
              marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <GitCompare size={13} /> Cross-Document Validations
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <CrossValidationCard
                title="Passport ↔ Driving License"
                result={passportDL}
                fields={passportDLFields}
                doc1Label="Passport"
                doc2Label="Driving License"
                doc1Info={passportDL?.passport}
                doc2Info={passportDL?.dl}
              />
              <CrossValidationCard
                title="Utility Bill ↔ Bank Statement"
                result={address}
                fields={addressFields}
                doc1Label="Utility Bill"
                doc2Label="Bank Statement"
                doc1Info={address?.utility}
                doc2Info={address?.bank}
              />
            </div>
          </div>

          {/* Biometric Verification Section */}
          <div style={{ marginBottom: 24 }}>
            <div style={{
              fontSize: 11, fontWeight: 700, color: 'var(--muted)',
              textTransform: 'uppercase', letterSpacing: '0.08em',
              marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <Fingerprint size={13} /> Biometric Verification
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <BiometricCard
                title="Signature Verification"
                icon={Fingerprint}
                verification={sigVerification}
                type="signature"
              />
              <BiometricCard
                title="Photo / Face Verification"
                icon={Camera}
                verification={photoVerification}
                type="photo"
              />
            </div>
          </div>

          {/* See Result Button */}
          {!showVerdict && (
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
              <button
                className="btn btn-primary"
                onClick={handleSeeResult}
                disabled={loading}
                style={{
                  padding: '14px 40px',
                  fontSize: 15,
                  fontWeight: 700,
                  borderRadius: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%)',
                  boxShadow: '0 4px 20px rgba(79,110,247,0.35)',
                  transition: 'all 0.3s ease',
                  letterSpacing: '0.02em',
                }}
                onMouseEnter={e => { e.target.style.transform = 'translateY(-2px)'; e.target.style.boxShadow = '0 8px 30px rgba(79,110,247,0.45)'; }}
                onMouseLeave={e => { e.target.style.transform = 'translateY(0)'; e.target.style.boxShadow = '0 4px 20px rgba(79,110,247,0.35)'; }}
              >
                <Shield size={18} />
                See KYC Result
              </button>
            </div>
          )}

          {/* Final Verdict */}
          {showVerdict && (
            <FinalVerdict 
              data={verdictData} 
              onApprove={handleApprove} 
              onReject={handleReject} 
            />
          )}
        </>
      )}

      {/* Style injection for animations */}
      <style>{`
        @keyframes verdictReveal {
          0% { opacity: 0; transform: translateY(20px) scale(0.97); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes verdictPulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(79,110,247,0.2); }
          50% { box-shadow: 0 0 0 8px rgba(79,110,247,0); }
        }
      `}</style>
    </div>
  );
}
