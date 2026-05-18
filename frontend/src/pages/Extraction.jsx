import { useState } from 'react';
import { Badge } from '../components/ui/Badge';
import { Btn } from '../components/ui/Btn';

const docTabs = [
  { label: '📄 invoice_Q2_2024.pdf', id: 0 },
  { label: '📋 contract_NDA.pdf', id: 1 },
  { label: '💰 bank_statement.pdf', id: 2 },
];

export function Extraction() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="page page-enter">
      {/* Tabs */}
      <div className="tabs">
        {docTabs.map((t) => (
          <div
            key={t.id}
            className={`tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </div>
        ))}
      </div>

      <div className="extraction-grid">
        {/* Document Preview */}
        <div>
          <div className="doc-preview">
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Page 1 of 2</span>
              <div style={{ display: 'flex', gap: 6 }}>
                <Btn variant="ghost" style={{ padding: '4px 8px', fontSize: 11 }}>← Prev</Btn>
                <Btn variant="ghost" style={{ padding: '4px 8px', fontSize: 11 }}>Next →</Btn>
              </div>
            </div>

            {/* Simulated Page */}
            <div className="doc-page">
              <div className="page-noise" />
              <div style={{ position: 'absolute', top: '8%', left: '8%', right: '8%', bottom: '8%', padding: 10 }}>
                <div style={{ background: '#f0f0f0', height: 6, borderRadius: 2, width: '60%', marginBottom: 8 }} />
                <div style={{ background: '#e0e0e0', height: 4, borderRadius: 2, width: '40%', marginBottom: 16 }} />
                {[90, 85, 92, 78].map((w, i) => (
                  <div key={i} style={{ background: '#f5f5f5', height: 3, borderRadius: 2, width: `${w}%`, marginBottom: 4 }} />
                ))}
                <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
                  {[1, 1, 1].map((_, i) => (
                    <div key={i} style={{ background: '#e8e8e8', height: 16, flex: 1, borderRadius: 2 }} />
                  ))}
                </div>
                {[88, 76, 82].map((w, i) => (
                  <div key={i} style={{ background: '#f5f5f5', height: 3, borderRadius: 2, width: `${w}%`, marginBottom: 4 }} />
                ))}
                <div style={{ background: '#eeeeee', height: 40, borderRadius: 3, marginBottom: 8 }} />
              </div>

              {/* Highlight Boxes */}
              <div className="highlight-box hl-name" style={{ top: '8%', left: '8%', width: '50%', height: '7%' }}>
                <span className="highlight-label" style={{ background: '#818cf8', color: 'white' }}>Vendor</span>
              </div>
              <div className="highlight-box hl-date" style={{ top: '8%', right: '8%', width: '28%', height: '7%' }}>
                <span className="highlight-label" style={{ background: '#34d399', color: '#0f1f16' }}>Date</span>
              </div>
              <div className="highlight-box hl-amount" style={{ bottom: '20%', right: '8%', width: '30%', height: '8%' }}>
                <span className="highlight-label" style={{ background: '#f59e0b', color: '#1a0f00' }}>Amount</span>
              </div>
              <div className="highlight-box hl-address" style={{ top: '38%', left: '8%', width: '44%', height: '12%' }}>
                <span className="highlight-label" style={{ background: '#06b6d4', color: 'white' }}>Address</span>
              </div>
            </div>

            {/* Legend */}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>Legend</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {[
                  { color: '#818cf8', label: '■ Vendor/Party' },
                  { color: '#34d399', label: '■ Dates' },
                  { color: '#f59e0b', label: '■ Amounts' },
                  { color: '#06b6d4', label: '■ Addresses' },
                ].map((l) => (
                  <span key={l.label} className="chip" style={{ borderColor: l.color, color: l.color }}>{l.label}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Extracted Fields */}
        <div className="fields-panel">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Extracted Data</div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                Confidence: <span style={{ color: 'var(--success)', fontWeight: 600 }}>99.2%</span> · 18 fields · 2 tables
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Btn variant="ghost" style={{ fontSize: 11, padding: '6px 12px' }}>📋 Copy JSON</Btn>
              <Btn variant="primary" style={{ fontSize: 11, padding: '6px 12px' }}>⬇ Export</Btn>
            </div>
          </div>

          {/* Header Info */}
          <FieldGroup title="Header Information">
            <FieldRow label="Document Type" value={<Badge variant="blue">Invoice</Badge>} conf="99.9%" confClass="conf-high" />
            <FieldRow label="Invoice Number" value="INV-2024-Q2-00847" conf="99.8%" confClass="conf-high" />
            <FieldRow label="Issue Date" value="June 30, 2024" conf="99.5%" confClass="conf-high" />
            <FieldRow label="Due Date" value="July 30, 2024" conf="99.5%" confClass="conf-high" />
          </FieldGroup>

          {/* Vendor Details */}
          <FieldGroup title="Vendor Details">
            <FieldRow label="Vendor Name" value="Acme Software Corp." conf="99.1%" confClass="conf-high" />
            <FieldRow label="Vendor Address" value="123 Tech Blvd, San Jose, CA 95110" conf="97.3%" confClass="conf-high" valueStyle={{ fontSize: 12 }} />
            <FieldRow label="Tax ID" value="XX-XXXXXXX" conf="88.2%" confClass="conf-med" confColor="var(--warn)" />
          </FieldGroup>

          {/* Financial Summary */}
          <FieldGroup title="Financial Summary">
            <FieldRow label="Subtotal" value="$48,200.00" conf="99.9%" confClass="conf-high" />
            <FieldRow label="Tax Amount" value="$4,337.40" conf="99.7%" confClass="conf-high" />
            <FieldRow label="Total Amount" value="$52,537.40" conf="99.9%" confClass="conf-high" valueStyle={{ fontSize: 15, fontWeight: 700, color: 'var(--success)' }} />
          </FieldGroup>

          {/* Validation Card */}
          <div className="card" style={{ borderColor: 'var(--success)', background: 'rgba(16,185,129,0.05)' }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10, color: 'var(--success)' }}>✅ Validation Passed</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: 'var(--success)' }}>✓</span> Math validation: Subtotal + Tax = Total ✓</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: 'var(--success)' }}>✓</span> Date logic: Issue Date &lt; Due Date ✓</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: 'var(--success)' }}>✓</span> Vendor lookup: Matched in database ✓</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: 'var(--warn)' }}>⚠</span> Tax ID format: Partially redacted in source</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FieldGroup({ title, children }) {
  return (
    <div className="field-group">
      <div className="field-group-title">{title}</div>
      {children}
    </div>
  );
}

function FieldRow({ label, value, conf, confClass = 'conf-high', confColor = 'var(--success)', valueStyle }) {
  return (
    <div className="field-row">
      <div className="field-key">{label}</div>
      <div className="field-val" style={valueStyle}>{value}</div>
      <div className="field-conf">
        <div className={`conf-dot ${confClass}`} />
        <span style={{ color: confColor }}>{conf}</span>
      </div>
    </div>
  );
}
