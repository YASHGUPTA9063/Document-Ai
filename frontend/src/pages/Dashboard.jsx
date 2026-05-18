import { useEffect } from 'react';
import { StatCard } from '../components/ui/StatCard';
import { Card, CardHeader } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Btn } from '../components/ui/Btn';
import { Pipeline } from '../components/ui/Pipeline';
import { LogContainer } from '../components/ui/LogContainer';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';
import { DonutChart } from '../components/ui/DonutChart';
import { Sparkline } from '../components/ui/Sparkline';
import { useLogStream } from '../hooks/useLogStream';
import { confBarsData, slaData } from '../data/mockData';
import { useApp } from '../context/AppContext';

const dashPipelineStates = ['done', 'done', 'done', 'done', 'done', 'running', ''];

export function Dashboard() {
  const { navigate } = useApp();
  const { logs, start } = useLogStream();

  useEffect(() => {
    start(600);
  }, [start]);

  return (
    <div className="page page-enter">
      {/* Stat Cards */}
      <div className="stats-row">
        <StatCard icon="📄" label="Documents Processed" value="14,832" delta="↑ 12.4% from last month" deltaType="up" />
        <StatCard icon="🎯" label="Extraction Accuracy" value="98.3" unit="%" delta="↑ 0.8% improvement" deltaType="up" />
        <StatCard icon="⚡" label="Avg. Process Time" value="2.1" unit="s" delta="↑ 34% faster than baseline" deltaType="up" />
        <StatCard icon="🤖" label="AI Agent Actions" value="89,241" delta="⚠ 3 pending reviews" deltaType="warn" />
      </div>

      {/* Grid: Recent Docs + Charts */}
      <div className="grid-2">
        {/* Recent Documents Table */}
        <Card>
          <CardHeader
            title="Recent Documents"
            subtitle="Latest processing queue"
            action={<Btn variant="ghost" style={{ fontSize: 11, padding: '5px 10px' }}>View All →</Btn>}
          />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ cursor: 'pointer' }} onClick={() => navigate('extraction')}>
                  <td><span className="doc-icon">📄</span>invoice_Q2_2024.pdf</td>
                  <td><Badge variant="blue">Invoice</Badge></td>
                  <td><Badge variant="green">✓ Done</Badge></td>
                  <td><span style={{ color: 'var(--success)' }}>99.2%</span></td>
                </tr>
                <tr>
                  <td><span className="doc-icon">📋</span>contract_NDA_Acme.pdf</td>
                  <td><Badge variant="cyan">Contract</Badge></td>
                  <td><Badge variant="green">✓ Done</Badge></td>
                  <td><span style={{ color: 'var(--success)' }}>97.8%</span></td>
                </tr>
                <tr>
                  <td><span className="doc-icon">🏥</span>medical_record_0041.pdf</td>
                  <td><Badge variant="yellow">Medical</Badge></td>
                  <td><Badge variant="yellow">⏳ Review</Badge></td>
                  <td><span style={{ color: 'var(--warn)' }}>82.1%</span></td>
                </tr>
                <tr>
                  <td><span className="doc-icon">🏛️</span>legal_brief_case_447.docx</td>
                  <td><Badge variant="cyan">Legal</Badge></td>
                  <td><Badge variant="blue">⚙ Processing</Badge></td>
                  <td><span style={{ color: 'var(--muted)' }}>—</span></td>
                </tr>
                <tr>
                  <td><span className="doc-icon">💰</span>bank_statement_Mar.pdf</td>
                  <td><Badge variant="blue">Financial</Badge></td>
                  <td><Badge variant="green">✓ Done</Badge></td>
                  <td><span style={{ color: 'var(--success)' }}>99.9%</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>

        {/* Charts Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card style={{ flex: 1 }}>
            <CardHeader title="Document Types" subtitle="Distribution this month" />
            <DonutChart />
          </Card>
          <Card>
            <CardHeader title="Daily Volume (Last 14 days)" />
            <Sparkline />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>
              <span>May 5</span><span>May 18</span>
            </div>
          </Card>
        </div>
      </div>

      {/* Active Agent Pipeline */}
      <Card style={{ marginBottom: 20 }}>
        <CardHeader
          title="🤖 Active Agent Pipeline"
          subtitle="Real-time orchestration status"
          action={
            <div className="chip">
              Live{' '}
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', display: 'inline-block', marginLeft: 4, animation: 'pulse 1.5s infinite' }} />
            </div>
          }
        />
        <Pipeline states={dashPipelineStates} />
        <LogContainer logs={logs} maxHeight={160} />
      </Card>

      {/* Confidence + SLA */}
      <div className="grid-2">
        <Card>
          <CardHeader title="Field Extraction Confidence" subtitle="Across all document types" />
          {confBarsData.map((d) => (
            <ConfidenceBar key={d.label} label={d.label} pct={d.pct} color={d.color} />
          ))}
        </Card>
        <Card>
          <CardHeader title="Processing SLA" subtitle="Performance targets" />
          {slaData.map((d) => (
            <ConfidenceBar key={d.label} label={d.label} pct={d.pct} color={d.color} />
          ))}
        </Card>
      </div>
    </div>
  );
}
