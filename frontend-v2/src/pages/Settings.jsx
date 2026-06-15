import { useState } from 'react';
import { useApp } from '../store/AppStore';
import {
  Settings as SettingsIcon, SlidersHorizontal, BarChart3,
  CheckCircle2, Circle, ChevronRight, Zap, Eye, ShieldCheck,
  Palette, Info, RotateCcw, Save,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────────
   Sidebar nav items
───────────────────────────────────────────────────────────── */
const NAV = [
  { id: 'confidence',  label: 'Confidence Scores',  icon: BarChart3,        desc: 'Granularity & display mode' },
  { id: 'thresholds',  label: 'Thresholds',         icon: SlidersHorizontal, desc: 'Highlight & approval limits' },
];

/* ─────────────────────────────────────────────────────────────
   Tiny helper: section header
───────────────────────────────────────────────────────────── */
function SectionHeader({ icon: Icon, label, desc, color = 'var(--accent)' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 28 }}>
      <div style={{
        width: 42, height: 42, borderRadius: 10, flexShrink: 0,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 22%, transparent)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color,
      }}>
        <Icon size={18} />
      </div>
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.2px' }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{desc}</div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Confidence mode toggle card
───────────────────────────────────────────────────────────── */
function ModeCard({ active, icon: Icon, title, subtitle, onClick, accentColor = 'var(--accent)' }) {
  return (
    <button
      onClick={onClick}
      style={{
        all: 'unset', width: '100%', cursor: 'pointer',
        display: 'flex', alignItems: 'flex-start', gap: 14,
        padding: '16px 18px', borderRadius: 10,
        border: active ? `1.5px solid ${accentColor}` : '1.5px solid var(--border)',
        background: active ? `color-mix(in srgb, ${accentColor} 7%, var(--card-alt))` : 'var(--card-alt)',
        transition: 'all 0.18s ease',
        boxSizing: 'border-box',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {active && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: `linear-gradient(90deg, ${accentColor}, color-mix(in srgb, ${accentColor} 40%, transparent))`,
        }} />
      )}
      <div style={{
        width: 36, height: 36, borderRadius: 8, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: active ? `color-mix(in srgb, ${accentColor} 14%, transparent)` : 'var(--surface)',
        border: `1px solid ${active ? `color-mix(in srgb, ${accentColor} 25%, transparent)` : 'var(--border)'}`,
        color: active ? accentColor : 'var(--muted)',
        transition: 'all 0.18s ease',
      }}>
        <Icon size={16} />
      </div>
      <div style={{ flex: 1, textAlign: 'left' }}>
        <div style={{
          fontWeight: 600, fontSize: 13,
          color: active ? accentColor : 'var(--text)',
          marginBottom: 4, transition: 'color 0.18s ease',
        }}>{title}</div>
        <div style={{ fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.55 }}>{subtitle}</div>
      </div>
      <div style={{ marginTop: 2, flexShrink: 0 }}>
        {active
          ? <CheckCircle2 size={17} color={accentColor} />
          : <Circle size={17} color="var(--muted)" />}
      </div>
    </button>
  );
}

/* ─────────────────────────────────────────────────────────────
   Professional threshold slider
───────────────────────────────────────────────────────────── */
function ThresholdControl({ label, description, value, onChange, min = 50, max = 100, accentColor, icon: Icon, presets }) {
  const pct = ((value - min) / (max - min)) * 100;
  const ac = accentColor || 'var(--accent)';

  return (
    <div style={{
      background: 'var(--card-alt)', borderRadius: 10,
      border: '1px solid var(--border)', overflow: 'hidden',
    }}>
      {/* Header row */}
      <div style={{ padding: '14px 18px 12px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
        {Icon && (
          <div style={{
            width: 28, height: 28, borderRadius: 6, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: `color-mix(in srgb, ${ac} 12%, transparent)`,
            color: ac,
          }}>
            <Icon size={13} />
          </div>
        )}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{label}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1, lineHeight: 1.4 }}>{description}</div>
        </div>
        {/* Live value badge */}
        <div style={{
          fontSize: 18, fontWeight: 800, letterSpacing: '-0.5px',
          color: ac, minWidth: 48, textAlign: 'right',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {value}<span style={{ fontSize: 11, fontWeight: 600, opacity: 0.7 }}>%</span>
        </div>
      </div>

      {/* Slider body */}
      <div style={{ padding: '14px 18px 16px' }}>
        {/* Custom slider track */}
        <div style={{ position: 'relative', height: 8, borderRadius: 99, background: 'var(--border)', marginBottom: 10 }}>
          {/* Fill */}
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0,
            width: `${pct}%`, borderRadius: 99,
            background: `linear-gradient(90deg, color-mix(in srgb, ${ac} 60%, var(--border)), ${ac})`,
            transition: 'width 0.05s',
          }} />
          {/* Invisible native input on top */}
          <input
            type="range"
            min={min}
            max={max}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            style={{
              position: 'absolute', inset: '-6px 0',
              width: '100%', height: 'calc(100% + 12px)',
              opacity: 0, cursor: 'pointer', margin: 0,
              WebkitAppearance: 'none',
            }}
          />
          {/* Thumb indicator */}
          <div style={{
            position: 'absolute', top: '50%',
            left: `calc(${pct}% - 9px)`,
            transform: 'translateY(-50%)',
            width: 18, height: 18, borderRadius: '50%',
            background: ac, border: '2.5px solid var(--card)',
            boxShadow: `0 0 0 3px color-mix(in srgb, ${ac} 25%, transparent), 0 2px 6px rgba(0,0,0,0.15)`,
            pointerEvents: 'none',
            transition: 'left 0.05s',
          }} />
        </div>

        {/* Min / Max labels */}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: presets ? 12 : 0 }}>
          <span>{min}%</span>
          <span>{max}%</span>
        </div>

        {/* Preset chips */}
        {presets && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, color: 'var(--muted)', alignSelf: 'center', marginRight: 2 }}>Quick:</span>
            {presets.map((p) => (
              <button
                key={p}
                onClick={() => onChange(p)}
                style={{
                  all: 'unset', cursor: 'pointer',
                  fontSize: 10, fontWeight: 600, padding: '2px 9px',
                  borderRadius: 99,
                  background: value === p ? `color-mix(in srgb, ${ac} 15%, transparent)` : 'var(--surface)',
                  border: `1px solid ${value === p ? ac : 'var(--border)'}`,
                  color: value === p ? ac : 'var(--text-dim)',
                  transition: 'all 0.15s ease',
                }}
              >
                {p}%
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Info callout
───────────────────────────────────────────────────────────── */
function InfoCallout({ children }) {
  return (
    <div style={{
      display: 'flex', gap: 10, alignItems: 'flex-start',
      background: 'color-mix(in srgb, var(--accent) 6%, var(--card-alt))',
      border: '1px solid color-mix(in srgb, var(--accent) 15%, transparent)',
      borderRadius: 8, padding: '10px 14px', marginBottom: 20,
    }}>
      <Info size={13} color="var(--accent)" style={{ marginTop: 1, flexShrink: 0 }} />
      <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6, margin: 0 }}>{children}</p>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   CONFIDENCE SCORES SECTION
───────────────────────────────────────────────────────────── */
function ConfidenceSection({ confidenceMode, setConfidenceMode, toast }) {
  const isWord = confidenceMode === 'word' || confidenceMode === 'both';
  const isPage = confidenceMode === 'page' || confidenceMode === 'both';

  const toggleWord = () => {
    if (isWord && !isPage) { toast('At least one type must be active.', 'error'); return; }
    const next = isWord ? 'page' : 'both';
    setConfidenceMode(next);
    toast(`Granularity: ${next === 'both' ? 'Word + Page' : 'Page-wise'} ✓`, 'success');
  };

  const togglePage = () => {
    if (isPage && !isWord) { toast('At least one type must be active.', 'error'); return; }
    const next = isPage ? 'word' : 'both';
    setConfidenceMode(next);
    toast(`Granularity: ${next === 'both' ? 'Word + Page' : 'Word-wise'} ✓`, 'success');
  };

  return (
    <div>
      <SectionHeader icon={BarChart3} label="Confidence Score Granularity" desc="Choose how confidence is computed and displayed on the Extraction page" />

      <InfoCallout>
        You can enable one or both confidence modes simultaneously. Word-wise gives field-level detail; Page-wise shows the OCR structural accuracy from Mistral.
      </InfoCallout>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <ModeCard
          active={isWord}
          icon={Eye}
          title="Word-wise Confidence"
          subtitle="Field-level confidence scores per extracted value (e.g., Vendor Name, Total Amount). Overall score = average of all field confidences."
          onClick={toggleWord}
          accentColor="var(--accent)"
        />
        <ModeCard
          active={isPage}
          icon={BarChart3}
          title="Page-wise Confidence"
          subtitle="Average page-level OCR confidence from Mistral. Hides field variation badges — gives a clean structural accuracy view."
          onClick={togglePage}
          accentColor="var(--accent2)"
        />
      </div>

      {/* Active mode summary pill */}
      <div style={{
        marginTop: 16, display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderRadius: 8,
        background: 'var(--surface)', border: '1px solid var(--border)',
      }}>
        <Zap size={12} color="var(--accent)" />
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>Active mode:</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>
          {confidenceMode === 'both' ? 'Word-wise + Page-wise'
            : confidenceMode === 'word' ? 'Word-wise only'
            : 'Page-wise only'}
        </span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   THRESHOLDS SECTION
───────────────────────────────────────────────────────────── */
function ThresholdsSection({
  fieldHighlightThreshold, setFieldHighlightThreshold,
  autoApproveThreshold,    setAutoApproveThreshold,
  confHighThreshold,       setConfHighThreshold,
  confMedThreshold,        setConfMedThreshold,
  toast,
}) {
  const handleHigh = (v) => {
    if (v <= confMedThreshold) { toast('High threshold must exceed the Medium threshold.', 'error'); return; }
    setConfHighThreshold(v);
    toast(`High badge threshold → ${v}% ✓`, 'success');
  };
  const handleMed = (v) => {
    if (v >= confHighThreshold) { toast('Medium threshold must be below the High threshold.', 'error'); return; }
    setConfMedThreshold(v);
    toast(`Medium badge threshold → ${v}% ✓`, 'success');
  };

  return (
    <div>
      <SectionHeader icon={SlidersHorizontal} label="Confidence Thresholds" desc="Fine-tune when fields are flagged, highlighted, or auto-approved" />

      {/* Sub-group: Review & Highlighting */}
      <div style={{ marginBottom: 24 }}>
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color: 'var(--muted)', marginBottom: 12, paddingLeft: 2,
        }}>
          Review & Highlighting
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <ThresholdControl
            label="Auto-Approve Threshold"
            description="Documents at or above this confidence are automatically approved. Below this → human review queue."
            value={autoApproveThreshold}
            onChange={(v) => { setAutoApproveThreshold(v); toast(`Auto-approve → ${v}% ✓`, 'success'); }}
            min={50} max={100}
            accentColor="var(--success)"
            icon={ShieldCheck}
            presets={[70, 75, 80, 85, 90]}
          />
          <ThresholdControl
            label="Field Value Highlight"
            description="Fields whose word-level confidence falls below this are highlighted amber in the Extraction panel."
            value={fieldHighlightThreshold}
            onChange={(v) => { setFieldHighlightThreshold(v); toast(`Field highlight → ${v}% ✓`, 'success'); }}
            min={50} max={100}
            accentColor="var(--warn)"
            icon={Eye}
            presets={[80, 85, 90, 95, 100]}
          />
        </div>
      </div>

      {/* Sub-group: Badge Colors */}
      <div>
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color: 'var(--muted)', marginBottom: 12, paddingLeft: 2,
        }}>
          Field Badge Colors
        </div>

        {/* Color legend */}
        <div style={{
          display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap',
        }}>
          {[
            { label: 'High (green)', color: 'var(--success)', range: `≥ ${confHighThreshold}%` },
            { label: 'Medium (amber)', color: 'var(--warn)', range: `${confMedThreshold}%–${confHighThreshold - 1}%` },
            { label: 'Low (red)', color: 'var(--danger)', range: `< ${confMedThreshold}%` },
          ].map(({ label, color, range }) => (
            <div key={label} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 10px', borderRadius: 99,
              background: 'var(--card-alt)', border: '1px solid var(--border)',
              fontSize: 11, color: 'var(--text-dim)',
            }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block', boxShadow: `0 0 5px ${color}` }} />
              <span>{label}:</span>
              <span style={{ fontWeight: 600, color: 'var(--text)' }}>{range}</span>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <ThresholdControl
            label="High Confidence (Green) Threshold"
            description={`Fields at or above this value display a green badge. Must stay above Medium (${confMedThreshold}%).`}
            value={confHighThreshold}
            onChange={handleHigh}
            min={Math.min(confMedThreshold + 1, 99)} max={100}
            accentColor="var(--success)"
            icon={CheckCircle2}
            presets={[85, 90, 95]}
          />
          <ThresholdControl
            label="Medium Confidence (Amber) Threshold"
            description={`Fields between this and High (${confHighThreshold}%) show amber. Below this → red badge.`}
            value={confMedThreshold}
            onChange={handleMed}
            min={50} max={Math.max(confHighThreshold - 1, 51)}
            accentColor="var(--warn)"
            icon={Palette}
            presets={[60, 65, 70, 75]}
          />
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   MAIN SETTINGS COMPONENT
───────────────────────────────────────────────────────────── */
export function Settings() {
  const [activeNav, setActiveNav] = useState('confidence');

  const {
    confidenceMode, setConfidenceMode,
    fieldHighlightThreshold, setFieldHighlightThreshold,
    autoApproveThreshold,    setAutoApproveThreshold,
    confHighThreshold,       setConfHighThreshold,
    confMedThreshold,        setConfMedThreshold,
    toast,
  } = useApp();

  const DEFAULTS = {
    confidenceMode: 'word',
    fieldHighlightThreshold: 95,
    autoApproveThreshold: 80,
    confHighThreshold: 90,
    confMedThreshold: 70,
  };

  const handleReset = () => {
    setConfidenceMode(DEFAULTS.confidenceMode);
    setFieldHighlightThreshold(DEFAULTS.fieldHighlightThreshold);
    setAutoApproveThreshold(DEFAULTS.autoApproveThreshold);
    setConfHighThreshold(DEFAULTS.confHighThreshold);
    setConfMedThreshold(DEFAULTS.confMedThreshold);
    toast('All settings reset to defaults ✓', 'success');
  };

  return (
    <div className="page" style={{ maxWidth: 900, margin: '0 auto' }}>

      {/* ── Page Header ───────────────────────────────── */}
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <div style={{
              width: 34, height: 34, borderRadius: 9,
              background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)',
            }}>
              <SettingsIcon size={16} />
            </div>
            <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.5px', color: 'var(--text)' }}>
              Settings
            </h1>
          </div>
          <p style={{ fontSize: 13, color: 'var(--muted)', marginLeft: 44 }}>
            Configure extraction behaviour, confidence display, and approval thresholds.
          </p>
        </div>
        <button
          onClick={handleReset}
          title="Reset all to defaults"
          style={{
            all: 'unset', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--card-alt)',
            fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--danger-border)'; e.currentTarget.style.color = 'var(--danger)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-dim)'; }}
        >
          <RotateCcw size={12} />
          Reset defaults
        </button>
      </div>

      {/* ── Layout: sidebar + content ─────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '210px 1fr', gap: 16, alignItems: 'start' }}>

        {/* ── Left sidebar nav ───────────────────────── */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 12, padding: 8, boxShadow: 'var(--shadow-card)',
          position: 'sticky', top: 16,
        }}>
          <div style={{ padding: '8px 10px 10px', borderBottom: '1px solid var(--border)', marginBottom: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--muted)' }}>
              Preferences
            </span>
          </div>
          {NAV.map(({ id, label, icon: Icon, desc }) => {
            const active = activeNav === id;
            return (
              <button
                key={id}
                onClick={() => setActiveNav(id)}
                style={{
                  all: 'unset', cursor: 'pointer', width: '100%', boxSizing: 'border-box',
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 10px', borderRadius: 8, marginBottom: 2,
                  background: active ? 'var(--accent-dim)' : 'transparent',
                  border: `1px solid ${active ? 'rgba(79,110,247,0.2)' : 'transparent'}`,
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--card-alt)'; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{
                  width: 28, height: 28, borderRadius: 6, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: active ? 'var(--accent)' : 'var(--surface)',
                  border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                  color: active ? 'white' : 'var(--muted)',
                  transition: 'all 0.15s ease',
                }}>
                  <Icon size={13} />
                </div>
                <div style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: active ? 'var(--accent)' : 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {desc}
                  </div>
                </div>
                {active && <ChevronRight size={11} color="var(--accent)" style={{ flexShrink: 0 }} />}
              </button>
            );
          })}
        </div>

        {/* ── Right content panel ─────────────────────── */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 12, padding: 28, boxShadow: 'var(--shadow-card)',
          minHeight: 420,
        }}>
          {activeNav === 'confidence' && (
            <ConfidenceSection
              confidenceMode={confidenceMode}
              setConfidenceMode={setConfidenceMode}
              toast={toast}
            />
          )}
          {activeNav === 'thresholds' && (
            <ThresholdsSection
              fieldHighlightThreshold={fieldHighlightThreshold}
              setFieldHighlightThreshold={setFieldHighlightThreshold}
              autoApproveThreshold={autoApproveThreshold}
              setAutoApproveThreshold={setAutoApproveThreshold}
              confHighThreshold={confHighThreshold}
              setConfHighThreshold={setConfHighThreshold}
              confMedThreshold={confMedThreshold}
              setConfMedThreshold={setConfMedThreshold}
              toast={toast}
            />
          )}
        </div>
      </div>
    </div>
  );
}
