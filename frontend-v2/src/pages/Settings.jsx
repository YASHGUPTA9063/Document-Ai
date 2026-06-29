import { useState, useEffect } from 'react';
import { useApp } from '../store/AppStore';
import { getNormConfig, saveNormConfig } from '../api/client';
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
  { id: 'normalization', label: 'Normalization Format', icon: Palette,      desc: 'Date, number & name rules' },
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
   NORMALIZATION FORMAT SECTION
───────────────────────────────────────────────────────────── */
function NormalizationSection({ toast }) {
  const [config, setConfig] = useState({
    date_format: 'YYYY-MM-DD',
    number_format: 'float',
    name_casing: 'Title Case',
    name_sequence: 'Firstname Lastname',
    custom_rules: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getNormConfig();
        if (active) {
          setConfig(data);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          toast(err.message || 'Failed to load normalization settings', 'error');
          setLoading(false);
        }
      }
    }
    load();
    return () => { active = false; };
  }, [toast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveNormConfig(config);
      toast('Normalization settings saved successfully ✓', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setConfig({
      date_format: 'YYYY-MM-DD',
      number_format: 'float',
      name_casing: 'Title Case',
      name_sequence: 'Firstname Lastname',
      custom_rules: '',
    });
    toast('Form reset to default presets (remember to save) ✓', 'info');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: 'var(--muted)' }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Loading settings from backend...</div>
      </div>
    );
  }

  // Build the live preview content dynamically based on current UI state
  const datePreview = config.date_format === 'keep'
    ? "Keep the date in its original raw string format as extracted."
    : `Normalize to ${config.date_format} format (e.g. '25 June 2026' -> '${config.date_format === 'YYYY-MM-DD' ? '2026-06-25' : config.date_format === 'MM/DD/YYYY' ? '06/25/2026' : '25/06/2026'}'). If invalid or missing, keep empty.`;

  const numPreview = config.number_format === 'float'
    ? "Convert to float/integer numbers (e.g. '$1,250.50' -> 1250.5). Strip any currency symbols."
    : config.number_format === 'integer'
    ? "Convert to integer numbers (e.g. '$1,250.50' -> 1250). Strip decimals and currency symbols."
    : "Keep numbers as strings (e.g. '$1,250.50' -> '$1,250.50').";

  const casingPreview = config.name_casing === 'Title Case'
    ? "Normalize spelling and standardize to Title Case."
    : config.name_casing === 'UPPERCASE'
    ? "Normalize spelling and convert to UPPERCASE."
    : "Keep name/address casing exactly as it is written in the document.";

  const seqPreview = config.name_sequence === 'Firstname Lastname'
    ? "Format person names as 'Firstname Lastname' (e.g. 'John Doe')."
    : config.name_sequence === 'Firstname Middlename Lastname'
    ? "Format person names as 'Firstname Middlename Lastname' (e.g. 'John Albert Doe'). If no middle name exists, omit it."
    : config.name_sequence === 'Lastname Firstname'
    ? "Format person names as 'Lastname Firstname' (e.g. 'Doe John')."
    : config.name_sequence === 'Lastname, Firstname Middlename'
    ? "Format person names as 'Lastname, Firstname Middlename' (e.g. 'Doe, John Albert')."
    : config.name_sequence === 'Title Firstname Lastname'
    ? "Format person names as 'Title Firstname Lastname' (e.g. 'Mr. John Doe'). If no title is in the document, omit it."
    : config.name_sequence === 'Title Firstname Middlename Lastname'
    ? "Format person names as 'Title Firstname Middlename Lastname' (e.g. 'Mr. John Albert Doe'). If no title/middle name is in the document, omit them."
    : "Keep the original order of names exactly as written in the document.";

  const livePromptSnippet = 
    `Your final response MUST be a JSON object containing EXACTLY these two keys:\n` +
    `1. 'raw_extracted': A JSON object containing the raw field values exactly as returned by the OCR tool (without formatting/cleaning).\n` +
    `2. 'normalized_extracted': A JSON object containing the normalized/cleaned field values. Apply standard formatting rules:\n` +
    `   - Dates: ${datePreview}\n` +
    `   - Amounts/Numbers: ${numPreview}\n` +
    `   - Names & Addresses: ${casingPreview}\n` +
    `   - Name Structure: ${seqPreview}\n` +
    (config.custom_rules ? config.custom_rules.split('\n').map(l => `   ${l}`).join('\n') : '');

  return (
    <div>
      <SectionHeader icon={Palette} label="Normalization Format Settings" desc="Control how extracted values are cleaned, formatted, and standardized" />

      <InfoCallout>
        These rules tell the general extractor agent how to format normalized fields. Changes are applied at runtime.
      </InfoCallout>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        
        {/* Date Format Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Date Field Format
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            {[
              { id: 'YYYY-MM-DD', label: 'ISO Format (YYYY-MM-DD)', desc: 'e.g. 2026-06-25' },
              { id: 'MM/DD/YYYY', label: 'US Format (MM/DD/YYYY)', desc: 'e.g. 06/25/2026' },
              { id: 'DD/MM/YYYY', label: 'EU Format (DD/MM/YYYY)', desc: 'e.g. 25/06/2026' },
              { id: 'keep', label: 'Keep Raw Text', desc: 'As written in document' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, date_format: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.date_format === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.date_format === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.date_format === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Number/Amount Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Number/Amount Formatting
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            {[
              { id: 'float', label: 'Decimal (Float)', desc: '1250.50' },
              { id: 'integer', label: 'Integer', desc: '1250' },
              { id: 'string', label: 'Raw String', desc: '"$1,250.50"' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, number_format: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.number_format === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.number_format === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.number_format === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Name Casing Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Name & Address Casing
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            {[
              { id: 'Title Case', label: 'Title Case', desc: 'John Doe' },
              { id: 'UPPERCASE', label: 'UPPERCASE', desc: 'JOHN DOE' },
              { id: 'keep', label: 'Keep Raw', desc: 'As-is' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, name_casing: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.name_casing === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.name_casing === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.name_casing === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Name Sequence/Structure Option */}
        <div>
          <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', display: 'block', marginBottom: 8 }}>
            Name Formatting Structure
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            {[
              { id: 'Firstname Lastname', label: 'First Last', desc: 'e.g. John Doe' },
              { id: 'Firstname Middlename Lastname', label: 'First Middle Last', desc: 'e.g. John Albert Doe' },
              { id: 'Lastname Firstname', label: 'Last First', desc: 'e.g. Doe John' },
              { id: 'Lastname, Firstname Middlename', label: 'Last, First Middle', desc: 'e.g. Doe, John Albert' },
              { id: 'Title Firstname Lastname', label: 'Title First Last', desc: 'e.g. Mr. John Doe' },
              { id: 'Title Firstname Middlename Lastname', label: 'Title First Middle Last', desc: 'e.g. Mr. John Albert Doe' },
              { id: 'keep', label: 'Keep Raw Order', desc: 'Original sequence' },
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setConfig(prev => ({ ...prev, name_sequence: opt.id }))}
                style={{
                  all: 'unset', cursor: 'pointer', boxSizing: 'border-box',
                  padding: '12px 14px', borderRadius: 8,
                  border: config.name_sequence === opt.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: config.name_sequence === opt.id ? 'color-mix(in srgb, var(--accent) 8%, var(--card-alt))' : 'var(--card-alt)',
                  transition: 'all 0.15s ease',
                  textAlign: 'left'
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, color: config.name_sequence === opt.id ? 'var(--accent)' : 'var(--text)' }}>
                  {opt.label}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Normalization Rules Textarea */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
              Custom Formatting Rules
            </label>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Appended to extractor instructions</span>
          </div>
          <textarea
            value={config.custom_rules}
            onChange={(e) => setConfig(prev => ({ ...prev, custom_rules: e.target.value }))}
            placeholder="- Phone numbers: standard format as +XX XXXXX XXXXX&#10;- Convert all country names to ISO 3166-1 alpha-3 code (e.g. 'United States' -> 'USA')"
            style={{
              width: '100%', height: 100, boxSizing: 'border-box',
              background: 'var(--card-alt)', border: '1px solid var(--border)',
              borderRadius: 8, padding: '12px 14px', color: 'var(--text)',
              fontSize: 12.5, fontFamily: 'monospace', lineHeight: 1.5,
              resize: 'vertical', outline: 'none',
              transition: 'border-color 0.15s ease'
            }}
            onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
          />
        </div>

        {/* Live Prompt Preview */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 8, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Live Prompt Preview
          </label>
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 8, padding: 16, overflowX: 'auto',
            fontFamily: 'monospace', fontSize: 11, color: 'var(--text-dim)',
            lineHeight: 1.55, whiteSpace: 'pre-wrap'
          }}>
            {livePromptSnippet}
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 20 }}>
          <button
            onClick={handleReset}
            style={{
              all: 'unset', cursor: 'pointer',
              padding: '8px 16px', borderRadius: 8,
              border: '1px solid var(--border)',
              fontSize: 12.5, fontWeight: 600, color: 'var(--text-dim)',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--card-alt)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            Reset Presets
          </button>
          
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              all: 'unset', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '8px 18px', borderRadius: 8,
              background: 'var(--accent)',
              fontSize: 12.5, fontWeight: 600, color: 'white',
              opacity: saving ? 0.7 : 1,
              transition: 'all 0.15s ease',
              boxShadow: '0 2px 6px rgba(79,110,247,0.2)'
            }}
            onMouseEnter={e => { if(!saving) e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 90%, black)'; }}
            onMouseLeave={e => { if(!saving) e.currentTarget.style.background = 'var(--accent)'; }}
          >
            <Save size={14} />
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
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
          {activeNav === 'normalization' && (
            <NormalizationSection
              toast={toast}
            />
          )}
        </div>
      </div>
    </div>
  );
}
