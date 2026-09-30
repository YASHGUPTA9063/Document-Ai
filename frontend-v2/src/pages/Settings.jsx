import { useState, useEffect } from 'react';
import { useApp } from '../store/AppStore';
import { getNormConfig, saveNormConfig, getClassificationConfig, saveClassificationConfig, getVllmSettings, saveVllmSettings, getSplitSettings, saveSplitSettings, getChecklistSettings, saveChecklistSettings } from '../api/client';
import {
  Settings as SettingsIcon, SlidersHorizontal, BarChart3,
  CheckCircle2, Circle, ChevronRight, Zap, Eye, ShieldCheck,
  Palette, Info, RotateCcw, Save, Tag, Trash2, Plus, Bot, ToggleLeft, ToggleRight, Scissors, ListChecks,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────────
   Sidebar nav items
───────────────────────────────────────────────────────────── */
const NAV = [
  { id: 'confidence',  label: 'Confidence Scores',  icon: BarChart3,        desc: 'Granularity & display mode' },
  { id: 'thresholds',  label: 'Thresholds',         icon: SlidersHorizontal, desc: 'Highlight & approval limits' },
  { id: 'normalization', label: 'Normalization Format', icon: Palette,      desc: 'Date, number & name rules' },
  { id: 'classification', label: 'Classification Types', icon: Tag,          desc: 'Supported document types' },
  { id: 'splitting',      label: 'Document Splitting',   icon: Scissors,     desc: 'Multi-document packet handling' },
  { id: 'checklist',      label: 'Document Checklist',   icon: ListChecks,   desc: 'Types that skip the checklist' },
  // { id: 'vllm',           label: 'vLLM Fallback',        icon: Bot,          desc: 'Re-extract low-confidence fields' },
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
   CLASSIFICATION DOCUMENT TYPES SECTION
   ───────────────────────────────────────────────────────────── */
function ClassificationSection({ toast }) {
  const [docTypes, setDocTypes] = useState([]);
  const [newType, setNewType] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getClassificationConfig();
        if (active) {
          setDocTypes(data);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          toast(err.message || 'Failed to load classification settings', 'error');
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
      await saveClassificationConfig(docTypes);
      toast('Classification document types saved successfully ✓', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleAddType = () => {
    const trimmed = newType.trim().toLowerCase().replace(/\s+/g, '_');
    if (!trimmed) return;
    if (docTypes.includes(trimmed)) {
      toast('This document type already exists', 'warning');
      return;
    }
    setDocTypes(prev => [...prev, trimmed]);
    setNewType('');
  };

  const handleRemoveType = (typeToRemove) => {
    setDocTypes(prev => prev.filter(t => t !== typeToRemove));
  };

  const handleReset = () => {
    setDocTypes([
      "invoice", "pan_card", "claim_form", "policy_document", 
      "id_proof", "medical_report", "lab_reports", 
      "prescription_records", "bills_invoices", 
      "disability_certificate", "legal_letter"
    ]);
    toast('Reset to default classification types (remember to save) ✓', 'info');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: 'var(--muted)' }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Loading classification settings...</div>
      </div>
    );
  }

  return (
    <div>
      <SectionHeader icon={Tag} label="Classification Document Types" desc="Configure which document types the AI classifier should recognize" />

      <InfoCallout>
        Adding a document type enables the Classifier Agent to identify it. 
        Note that you will also need to configure corresponding extraction rules on the Templates page.
      </InfoCallout>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 10 }}>
        
        {/* Add new type form */}
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            type="text"
            placeholder="e.g. utility_bill, driver_license"
            value={newType}
            onChange={(e) => setNewType(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddType(); }}
            style={{
              flex: 1,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '10px 14px',
              fontSize: 13,
              color: 'var(--text)',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
          <button
            onClick={handleAddType}
            style={{
              all: 'unset', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '10px 18px', borderRadius: 8,
              background: 'var(--accent)',
              fontSize: 12.5, fontWeight: 600, color: 'white',
              transition: 'all 0.15s ease',
              boxShadow: '0 2px 6px rgba(79,110,247,0.2)'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 90%, black)'}
            onMouseLeave={e => e.currentTarget.style.background = 'var(--accent)'}
          >
            <Plus size={14} />
            Add Type
          </button>
        </div>

        {/* Current list of types */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Currently Supported Types ({docTypes.length})
          </label>
          {docTypes.length === 0 ? (
            <div style={{ padding: '24px 18px', border: '1px dashed var(--border)', borderRadius: 10, textAlign: 'center', color: 'var(--muted)', fontSize: 12.5 }}>
              No document types configured. The classifier will fail unless you add at least one type.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {docTypes.map((type) => {
                // Generate a pretty display name
                const displayName = type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                return (
                  <div
                    key={type}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 14px', borderRadius: 8,
                      background: 'var(--card-alt)', border: '1px solid var(--border)',
                    }}
                  >
                    <div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{displayName}</span>
                      <span style={{ fontSize: 10.5, color: 'var(--muted)', marginLeft: 10, fontFamily: 'monospace', background: 'var(--surface)', padding: '2px 6px', borderRadius: 4 }}>
                        {type}
                      </span>
                    </div>
                    <button
                      onClick={() => handleRemoveType(type)}
                      style={{
                        all: 'unset', cursor: 'pointer',
                        width: 28, height: 28, borderRadius: 6,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'var(--muted)',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'color-mix(in srgb, var(--danger) 10%, transparent)'; e.currentTarget.style.color = 'var(--danger)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--muted)'; }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          borderTop: '1px solid var(--border)', paddingTop: 20, marginTop: 10
        }}>
          <button
            onClick={handleReset}
            style={{
              all: 'unset', cursor: 'pointer',
              fontSize: 11.5, fontWeight: 600, color: 'var(--text-dim)',
              padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)',
              background: 'transparent',
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
   VLLM FALLBACK SECTION
───────────────────────────────────────────────────────────── */
function SplitToggle({ config, setConfig, field, title, on, off }) {
  const active = config[field];
  return (
    <div
      onClick={() => setConfig((prev) => ({ ...prev, [field]: !prev[field] }))}
      style={{
        background: 'var(--card-alt)', borderRadius: 10,
        border: `1.5px solid ${active ? '#d97706' : 'var(--border)'}`,
        padding: '14px 16px', marginBottom: 12,
        display: 'flex', alignItems: 'center', gap: 14, cursor: 'pointer',
        transition: 'all 0.18s ease',
      }}
    >
      <div style={{
        width: 34, height: 34, borderRadius: 8, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: active ? 'rgba(217,119,6,0.12)' : 'var(--surface)',
        border: `1px solid ${active ? 'rgba(217,119,6,0.25)' : 'var(--border)'}`,
        color: active ? '#d97706' : 'var(--muted)',
      }}>
        {active ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
      </div>
      <div style={{ flex: 1, textAlign: 'left' }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: active ? '#d97706' : 'var(--text)', marginBottom: 3 }}>
          {title}
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.55 }}>
          {active ? on : off}
        </div>
      </div>
      {active ? <CheckCircle2 size={17} color="#d97706" /> : <Circle size={17} color="var(--muted)" />}
    </div>
  );
}


function SplitNumberField({ config, setConfig, field, label, hint, min, max, step = 1 }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>{label}</div>
      <input
        type="number"
        min={min} max={max} step={step}
        value={config[field]}
        onChange={(e) => setConfig((prev) => ({ ...prev, [field]: Number(e.target.value) }))}
        style={{
          width: 120, padding: '7px 10px', borderRadius: 8,
          border: '1px solid var(--border)', background: 'var(--card)',
          color: 'var(--text)', fontSize: 13,
        }}
      />
      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, lineHeight: 1.5 }}>{hint}</div>
    </div>
  );
}


function SplittingSection({ toast }) {
  // No `enabled` key: splitting is switched on and off by ENABLE_DOC_SPLITTING
  // in the environment, the same as the Step 3.2 checklist. This section only
  // exists when the stage is already on, so everything here is a tuning knob.
  const [config, setConfig] = useState({
    confidence_threshold: 0.75, page_batch_size: 8,
    max_pages: 50, require_review: true, merge_orphans: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getSplitSettings();
        // `enabled` comes back for reference and is read-only — drop it so it
        // is not round-tripped on save.
        if (active) {
          const { enabled: _envFlag, ...tunables } = data;
          setConfig(tunables);
          setLoading(false);
        }
      } catch (err) {
        if (active) { toast(err.message || 'Failed to load splitting settings', 'error'); setLoading(false); }
      }
    })();
    return () => { active = false; };
  }, [toast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { enabled: _envFlag, ...tunables } = await saveSplitSettings(config);
      setConfig(tunables);
      toast('Document splitting settings saved ✓', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save splitting settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: 'var(--muted)' }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Loading splitting settings...</div>
      </div>
    );
  }

  return (
    <div>
      <SectionHeader
        icon={Scissors}
        label="Document Splitting"
        desc="Detect uploads that contain several documents and process each one separately"
        color="#d97706"
      />

      <InfoCallout>
        When a single upload holds several stitched-together documents, each page is
        classified and the file is cut into one document per boundary — before any of
        them is quality-checked or extracted. Each piece then runs the full pipeline on
        its own, <strong>reusing the classification the split already produced</strong>,
        so no document is classified twice. Files that hold one document are untouched.
        <br /><br />
        The stage itself is switched on and off by <strong>ENABLE_DOC_SPLITTING</strong> in
        the backend environment — with it off, splitting never runs and this section, the
        pipeline step and the splitter agent all disappear. The settings below tune how it
        behaves while it is on.
      </InfoCallout>

      <div>
        <SplitToggle
          config={config} setConfig={setConfig}
          field="require_review"
          title="Confirm uncertain boundaries"
          on="A person confirms the boundaries whenever any page is below the confidence threshold"
          off="Detected boundaries are applied automatically, however uncertain"
        />
        <SplitToggle
          config={config} setConfig={setConfig}
          field="merge_orphans"
          title="Absorb stray pages"
          on="A low-confidence page sitting between two pages of one document is kept with it"
          off="Every detected boundary is honoured, including single-page outliers"
        />

        <SplitNumberField
          config={config} setConfig={setConfig}
          field="confidence_threshold"
          label="Confidence threshold"
          min={0} max={1} step={0.05}
          hint="0-1. Below this a page boundary is sent for review, and its document type is re-checked by the classifier instead of being reused."
        />
        <SplitNumberField
          config={config} setConfig={setConfig}
          field="page_batch_size"
          label="Pages per classification call"
          min={1} max={25}
          hint="How many pages are classified in one request. Higher is cheaper and faster; lower gives the model more room per page."
        />
        <SplitNumberField
          config={config} setConfig={setConfig}
          field="max_pages"
          label="Maximum packet length"
          min={2} max={500}
          hint="Files longer than this are processed whole rather than split."
        />
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="btn btn-primary"
        style={{ marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 6 }}
      >
        <Save size={13} />
        {saving ? 'Saving...' : 'Save Configuration'}
      </button>
    </div>
  );
}


/* ─────────────────────────────────────────────────────────────
   DOCUMENT CHECKLIST SECTION
───────────────────────────────────────────────────────────── */
function ChecklistSection({ toast }) {
  const [skipTypes, setSkipTypes] = useState([]);
  const [docTypes, setDocTypes] = useState([]);
  const [newType, setNewType] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [checklist, classification] = await Promise.all([
          getChecklistSettings(), getClassificationConfig(),
        ]);
        if (active) {
          setSkipTypes(checklist.skip_types || []);
          setDocTypes(classification.map((t) => t.trim().toLowerCase().replace(/\s+/g, '_')));
          setLoading(false);
        }
      } catch (err) {
        if (active) { toast(err.message || 'Failed to load checklist settings', 'error'); setLoading(false); }
      }
    })();
    return () => { active = false; };
  }, [toast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const saved = await saveChecklistSettings({ skip_types: skipTypes });
      setSkipTypes(saved.skip_types || []);
      const released = saved.released_batches?.length || 0;
      toast(
        released
          ? `Document checklist settings saved ✓ — ${released} held upload(s) released`
          : 'Document checklist settings saved ✓',
        'success',
      );
    } catch (err) {
      toast(err.message || 'Failed to save checklist settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const addType = (raw) => {
    const key = raw.trim().toLowerCase().replace(/\s+/g, '_');
    if (!key) return;
    if (skipTypes.includes(key)) {
      toast('This document type already skips the checklist', 'warning');
      return;
    }
    setSkipTypes((prev) => [...prev, key]);
    setNewType('');
  };

  const removeType = (key) => setSkipTypes((prev) => prev.filter((t) => t !== key));

  const pretty = (key) => key.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: 'var(--muted)' }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Loading checklist settings...</div>
      </div>
    );
  }

  // Classification types not yet on the skip list, offered as one-click adds.
  const suggestions = docTypes.filter((t) => t !== 'others' && !skipTypes.includes(t));

  return (
    <div>
      <SectionHeader
        icon={ListChecks}
        label="Document Checklist"
        desc="Choose which document types skip the batch checklist"
        color="#0d9488"
      />

      <InfoCallout>
        After classification, every upload batch is checked against the configured
        classification types and held for review when one is missing. A document type
        listed here is still classified and processed as usual, but is <strong>never
        required</strong> — a batch is not held waiting for it, and an upload containing
        only these types goes straight through.
      </InfoCallout>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 10 }}>

        {/* Add a type */}
        <div>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              type="text"
              placeholder="e.g. kyc_form, cover_letter"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') addType(newType); }}
              style={{
                flex: 1,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 13,
                color: 'var(--text)',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
            <button
              onClick={() => addType(newType)}
              style={{
                all: 'unset', cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '10px 18px', borderRadius: 8,
                background: 'var(--accent)',
                fontSize: 12.5, fontWeight: 600, color: 'white',
                transition: 'all 0.15s ease',
                boxShadow: '0 2px 6px rgba(79,110,247,0.2)'
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 90%, black)'}
              onMouseLeave={e => e.currentTarget.style.background = 'var(--accent)'}
            >
              <Plus size={14} />
              Add Type
            </button>
          </div>

          {suggestions.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 }}>
              <span style={{ fontSize: 10, color: 'var(--muted)', alignSelf: 'center', marginRight: 2 }}>Classification types:</span>
              {suggestions.map((type) => (
                <button
                  key={type}
                  onClick={() => addType(type)}
                  style={{
                    all: 'unset', cursor: 'pointer',
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    fontSize: 10.5, fontWeight: 600, padding: '3px 9px',
                    borderRadius: 99,
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    color: 'var(--text-dim)',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = '#0d9488'; e.currentTarget.style.color = '#0d9488'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-dim)'; }}
                >
                  <Plus size={10} />
                  {pretty(type)}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Current skip list */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', display: 'block', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Types That Skip The Checklist ({skipTypes.length})
          </label>
          {skipTypes.length === 0 ? (
            <div style={{ padding: '24px 18px', border: '1px dashed var(--border)', borderRadius: 10, textAlign: 'center', color: 'var(--muted)', fontSize: 12.5 }}>
              No document types skip the checklist. Every classification type is required in each upload batch.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {skipTypes.map((type) => (
                <div
                  key={type}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', borderRadius: 8,
                    background: 'var(--card-alt)', border: '1px solid var(--border)',
                  }}
                >
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{pretty(type)}</span>
                    <span style={{ fontSize: 10.5, color: 'var(--muted)', marginLeft: 10, fontFamily: 'monospace', background: 'var(--surface)', padding: '2px 6px', borderRadius: 4 }}>
                      {type}
                    </span>
                  </div>
                  <button
                    onClick={() => removeType(type)}
                    style={{
                      all: 'unset', cursor: 'pointer',
                      width: 28, height: 28, borderRadius: 6,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'var(--muted)',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'color-mix(in srgb, var(--danger) 10%, transparent)'; e.currentTarget.style.color = 'var(--danger)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--muted)'; }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{
          display: 'flex', justifyContent: 'flex-end',
          borderTop: '1px solid var(--border)', paddingTop: 20, marginTop: 10
        }}>
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


function VllmSection({ toast }) {
  const [config, setConfig] = useState({ enabled: true, confidence_threshold: 75, trigger_on_missing: true, trigger_on_low_confidence: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getVllmSettings();
        if (active) { setConfig(data); setLoading(false); }
      } catch (err) {
        if (active) { toast(err.message || 'Failed to load vLLM settings', 'error'); setLoading(false); }
      }
    }
    load();
    return () => { active = false; };
  }, [toast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveVllmSettings(config);
      toast('vLLM fallback settings saved ✓', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save vLLM settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300, color: 'var(--muted)' }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Loading vLLM settings...</div>
      </div>
    );
  }

  return (
    <div>
      <SectionHeader icon={Bot} label="vLLM Fallback Re-extraction" desc="Automatically re-extract required fields that have low confidence or are missing" color="#8b5cf6" />

      <InfoCallout>
        When enabled, after initial OCR extraction, any template field marked as <strong>required</strong> that is either missing or has a confidence score below the threshold will be automatically re-extracted using Mistral's Vision LLM. Both the original and vLLM values are shown side-by-side for human review.
      </InfoCallout>

      {/* Enable/Disable Toggle */}
      <div style={{
        background: 'var(--card-alt)', borderRadius: 10,
        border: `1.5px solid ${config.enabled ? '#8b5cf6' : 'var(--border)'}`,
        padding: '16px 18px', marginBottom: 16,
        display: 'flex', alignItems: 'center', gap: 14,
        cursor: 'pointer',
        transition: 'all 0.18s ease',
      }}
        onClick={() => setConfig(prev => ({ ...prev, enabled: !prev.enabled }))}
      >
        <div style={{
          width: 36, height: 36, borderRadius: 8, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: config.enabled ? 'rgba(139, 92, 246, 0.12)' : 'var(--surface)',
          border: `1px solid ${config.enabled ? 'rgba(139, 92, 246, 0.25)' : 'var(--border)'}`,
          color: config.enabled ? '#8b5cf6' : 'var(--muted)',
          transition: 'all 0.18s ease',
        }}>
          {config.enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
        </div>
        <div style={{ flex: 1, textAlign: 'left' }}>
          <div style={{
            fontWeight: 600, fontSize: 13,
            color: config.enabled ? '#8b5cf6' : 'var(--text)',
            marginBottom: 3, transition: 'color 0.18s ease',
          }}>
            {config.enabled ? 'vLLM Fallback Enabled' : 'vLLM Fallback Disabled'}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.55 }}>
            {config.enabled
              ? 'Required fields below the confidence threshold will be re-extracted via Vision LLM'
              : 'Extraction uses only the primary OCR pipeline — no fallback re-extraction'}
          </div>
        </div>
        <div style={{ marginTop: 2, flexShrink: 0 }}>
          {config.enabled
            ? <CheckCircle2 size={17} color="#8b5cf6" />
            : <Circle size={17} color="var(--muted)" />}
        </div>
      </div>

      {/* Trigger Mode Toggles — only active when enabled */}
      <div style={{ opacity: config.enabled ? 1 : 0.45, pointerEvents: config.enabled ? 'auto' : 'none', transition: 'opacity 0.2s ease' }}>
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
          color: 'var(--muted)', marginBottom: 10, marginTop: 4,
        }}>
          Trigger Conditions
        </div>

        {/* Trigger on Missing */}
        <div style={{
          background: 'var(--card-alt)', borderRadius: 10,
          border: `1.5px solid ${config.trigger_on_missing ? '#8b5cf6' : 'var(--border)'}`,
          padding: '13px 16px', marginBottom: 10,
          display: 'flex', alignItems: 'center', gap: 12,
          cursor: 'pointer',
          transition: 'all 0.18s ease',
        }}
          onClick={() => setConfig(prev => ({ ...prev, trigger_on_missing: !prev.trigger_on_missing }))}
        >
          <div style={{
            width: 32, height: 32, borderRadius: 7, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: config.trigger_on_missing ? 'rgba(139, 92, 246, 0.12)' : 'var(--surface)',
            border: `1px solid ${config.trigger_on_missing ? 'rgba(139, 92, 246, 0.25)' : 'var(--border)'}`,
            color: config.trigger_on_missing ? '#8b5cf6' : 'var(--muted)',
            transition: 'all 0.18s ease',
          }}>
            {config.trigger_on_missing ? <CheckCircle2 size={15} /> : <Circle size={15} />}
          </div>
          <div style={{ flex: 1, textAlign: 'left' }}>
            <div style={{
              fontWeight: 600, fontSize: 12.5,
              color: config.trigger_on_missing ? '#8b5cf6' : 'var(--text)',
              marginBottom: 2, transition: 'color 0.18s ease',
            }}>
              Trigger on Missing Fields
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>
              Re-extract when a required field value is empty, null, or not found
            </div>
          </div>
        </div>

        {/* Trigger on Low Confidence */}
        <div style={{
          background: 'var(--card-alt)', borderRadius: 10,
          border: `1.5px solid ${config.trigger_on_low_confidence ? '#8b5cf6' : 'var(--border)'}`,
          padding: '13px 16px', marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 12,
          cursor: 'pointer',
          transition: 'all 0.18s ease',
        }}
          onClick={() => setConfig(prev => ({ ...prev, trigger_on_low_confidence: !prev.trigger_on_low_confidence }))}
        >
          <div style={{
            width: 32, height: 32, borderRadius: 7, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: config.trigger_on_low_confidence ? 'rgba(139, 92, 246, 0.12)' : 'var(--surface)',
            border: `1px solid ${config.trigger_on_low_confidence ? 'rgba(139, 92, 246, 0.25)' : 'var(--border)'}`,
            color: config.trigger_on_low_confidence ? '#8b5cf6' : 'var(--muted)',
            transition: 'all 0.18s ease',
          }}>
            {config.trigger_on_low_confidence ? <CheckCircle2 size={15} /> : <Circle size={15} />}
          </div>
          <div style={{ flex: 1, textAlign: 'left' }}>
            <div style={{
              fontWeight: 600, fontSize: 12.5,
              color: config.trigger_on_low_confidence ? '#8b5cf6' : 'var(--text)',
              marginBottom: 2, transition: 'color 0.18s ease',
            }}>
              Trigger on Low Confidence
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>
              Re-extract when a required field's confidence score is below the threshold
            </div>
          </div>
        </div>
      </div>

      {/* Threshold Slider — only active when enabled AND trigger_on_low_confidence is on */}
      <div style={{ opacity: config.enabled && config.trigger_on_low_confidence ? 1 : 0.45, pointerEvents: config.enabled && config.trigger_on_low_confidence ? 'auto' : 'none', transition: 'opacity 0.2s ease' }}>
        <ThresholdControl
          label="vLLM Confidence Threshold"
          description="Required fields with OCR confidence below this value will be re-extracted via Vision LLM."
          value={config.confidence_threshold}
          onChange={(v) => setConfig(prev => ({ ...prev, confidence_threshold: v }))}
          min={50}
          max={100}
          accentColor="#8b5cf6"
          icon={Bot}
          presets={[60, 70, 75, 80, 85, 90]}
        />
      </div>

      {/* How it works */}
      <div style={{
        marginTop: 20, padding: '14px 16px', borderRadius: 10,
        background: 'var(--surface)', border: '1px solid var(--border)',
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 10 }}>
          How it works
        </div>
        {[
          { step: '1', text: 'Initial extraction runs using the primary OCR + LLM pipeline' },
          { step: '2', text: 'For each required template field, check trigger conditions: missing value, low confidence, or both (based on your settings above)' },
          { step: '3', text: 'Send the document image to Mistral VLM with a targeted prompt for only those fields' },
          { step: '4', text: 'Both the original OCR value and vLLM suggestion are shown side-by-side on the Extraction page' },
        ].map(({ step, text }) => (
          <div key={step} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 8 }}>
            <div style={{
              width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
              background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: 700, color: '#8b5cf6',
            }}>{step}</div>
            <span style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5 }}>{text}</span>
          </div>
        ))}
      </div>


      {/* Save Button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            all: 'unset', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '8px 18px', borderRadius: 8,
            background: '#8b5cf6',
            fontSize: 12.5, fontWeight: 600, color: 'white',
            opacity: saving ? 0.7 : 1,
            transition: 'all 0.15s ease',
            boxShadow: '0 2px 6px rgba(139,92,246,0.25)',
          }}
          onMouseEnter={e => { if (!saving) e.currentTarget.style.background = '#7c3aed'; }}
          onMouseLeave={e => { if (!saving) e.currentTarget.style.background = '#8b5cf6'; }}
        >
          <Save size={14} />
          {saving ? 'Saving...' : 'Save vLLM Settings'}
        </button>
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
    toast, features,
  } = useApp();

  // ENABLE_DOC_SPLITTING is a deploy-level kill switch: with it off the runtime
  // toggles below cannot turn splitting back on, so the whole section is hidden
  // rather than shown as controls that do nothing.
  const nav = NAV.filter((n) => (
    (n.id !== 'splitting' || features.doc_splitting) &&
    (n.id !== 'checklist' || features.doc_checklist)
  ));

  // Derived rather than stored: the flags arrive after the first render, so a
  // section can vanish while it is the one being viewed. Falling back here shows
  // the first available section without a second render pass.
  const activeSection = nav.some((n) => n.id === activeNav) ? activeNav : nav[0].id;

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
          {nav.map(({ id, label, icon: Icon, desc }) => {
            const active = activeSection === id;
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
          {activeSection === 'confidence' && (
            <ConfidenceSection
              confidenceMode={confidenceMode}
              setConfidenceMode={setConfidenceMode}
              toast={toast}
            />
          )}
          {activeSection === 'thresholds' && (
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
          {activeSection === 'normalization' && (
            <NormalizationSection
              toast={toast}
            />
          )}
          {activeSection === 'splitting' && (
            <SplittingSection toast={toast} />
          )}

          {activeSection === 'checklist' && (
            <ChecklistSection toast={toast} />
          )}

          {activeSection === 'classification' && (
            <ClassificationSection
              toast={toast}
            />
          )}
          {/* {activeSection === 'vllm' && (
            <VllmSection
              toast={toast}
            />
          )} */}
        </div>
      </div>
    </div>
  );
}
