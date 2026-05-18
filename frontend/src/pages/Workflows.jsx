import { Badge } from '../components/ui/Badge';
import { useApp } from '../context/AppContext';

const workflows = [
  {
    emoji: '📄➡🤖➡📊',
    title: 'Invoice Processing',
    desc: 'Automated AP/AR workflow with 3-way match validation against PO and receipt data.',
    status: 'green', statusLabel: 'Active',
    agents: 8, runs: '1,240 runs/day',
    page: 'processing',
  },
  {
    emoji: '📋➡🔍➡✅',
    title: 'Contract Analysis',
    desc: 'Extracts key clauses, obligations, expiry dates, and risk flags from legal agreements.',
    status: 'green', statusLabel: 'Active',
    agents: 6, runs: '380 runs/day',
    page: null,
  },
  {
    emoji: '🏥➡🔐➡💊',
    title: 'Medical Records',
    desc: 'HIPAA-compliant extraction of patient data, diagnoses, medications from clinical documents.',
    status: 'yellow', statusLabel: 'Review',
    agents: 9, runs: '620 runs/day',
    page: null,
  },
  {
    emoji: '💰➡📊➡🏦',
    title: 'Bank Statements',
    desc: 'Parses transactions, balances, and account info from bank statements across 200+ formats.',
    status: 'green', statusLabel: 'Active',
    agents: 5, runs: '2,100 runs/day',
    page: null,
  },
  {
    emoji: '🆔➡🔒➡✔️',
    title: 'KYC / ID Verification',
    desc: "Extracts and validates identity documents — passports, driver's licenses, utility bills.",
    status: 'green', statusLabel: 'Active',
    agents: 7, runs: '890 runs/day',
    page: null,
  },
];

export function Workflows() {
  const { navigate } = useApp();

  return (
    <div className="page page-enter">
      <div className="grid-3">
        {workflows.map((w) => (
          <div
            key={w.title}
            className="card"
            style={{ cursor: 'pointer' }}
            onClick={() => w.page && navigate(w.page)}
          >
            <div style={{ fontSize: 28, marginBottom: 12 }}>{w.emoji}</div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>{w.title}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>{w.desc}</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Badge variant={w.status}>{w.statusLabel}</Badge>
              <span className="chip">{w.agents} agents</span>
              <span className="chip">{w.runs}</span>
            </div>
          </div>
        ))}

        {/* Create Custom Workflow */}
        <div
          className="card"
          style={{ cursor: 'pointer', borderStyle: 'dashed', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 160 }}
        >
          <div style={{ fontSize: 36, marginBottom: 10, opacity: 0.4 }}>+</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--muted)' }}>Create Custom Workflow</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>Use the visual builder</div>
        </div>
      </div>
    </div>
  );
}
