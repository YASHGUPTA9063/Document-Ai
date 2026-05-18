import { useEffect } from 'react';
import { Card, CardHeader } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Pipeline } from '../components/ui/Pipeline';
import { LogContainer } from '../components/ui/LogContainer';
import { useLogStream } from '../hooks/useLogStream';
import { extractionProgress } from '../data/mockData';

const liveStates = ['done', 'done', 'done', 'running', '', '', ''];

export function Processing() {
  const { logs, start } = useLogStream();

  useEffect(() => {
    start(400);
  }, [start]);

  return (
    <div className="page page-enter">
      {/* Live Pipeline */}
      <Card style={{ marginBottom: 20 }}>
        <CardHeader
          title="🔄 Live Processing Pipeline"
          subtitle="Agentic workflow orchestration — real-time view"
          action={
            <div className="chip">
              Processing: <strong style={{ color: 'var(--accent)', marginLeft: 4 }}>invoice_Q2_2024.pdf</strong>
            </div>
          }
        />
        <Pipeline states={liveStates} />
      </Card>

      {/* Reasoning Log + Extraction Progress */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        <Card>
          <CardHeader title="🤖 Agent Reasoning Trace" />
          <LogContainer logs={logs} maxHeight={320} />
        </Card>
        <Card>
          <CardHeader title="📊 Extraction Progress" />
          <div>
            {extractionProgress.map((p) => (
              <div key={p.label} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                  <span>{p.label}</span>
                  <span style={{ color: p.pct === 100 ? 'var(--success)' : 'var(--accent)' }}>{p.pct}%</span>
                </div>
                <div className="progress-bar">
                  <div className={`progress-fill ${p.pct === 100 ? 'green' : ''}`} style={{ width: p.pct + '%' }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Processing Queue Table */}
      <Card>
        <CardHeader title="📋 Processing Queue" />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th><th>Type</th><th>Stage</th><th>Progress</th><th>Agent</th><th>ETA</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><span className="doc-icon">📄</span>invoice_Q2_2024.pdf</td>
                <td><Badge variant="blue">Invoice</Badge></td>
                <td><Badge variant="blue">Extracting</Badge></td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="progress-bar" style={{ width: 80 }}><div className="progress-fill" style={{ width: '72%' }} /></div>
                    <span style={{ fontSize: 11 }}>72%</span>
                  </div>
                </td>
                <td><Badge variant="blue">Extractor</Badge></td>
                <td style={{ color: 'var(--muted)' }}>~1.2s</td>
              </tr>
              <tr>
                <td><span className="doc-icon">📋</span>contract_NDA_Acme.pdf</td>
                <td><Badge variant="cyan">Contract</Badge></td>
                <td><Badge variant="yellow">Validating</Badge></td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="progress-bar" style={{ width: 80 }}><div className="progress-fill" style={{ width: '91%' }} /></div>
                    <span style={{ fontSize: 11 }}>91%</span>
                  </div>
                </td>
                <td><Badge variant="yellow">Validator</Badge></td>
                <td style={{ color: 'var(--muted)' }}>~0.4s</td>
              </tr>
              <tr>
                <td><span className="doc-icon">🏥</span>medical_record_0041.pdf</td>
                <td><Badge variant="yellow">Medical</Badge></td>
                <td><Badge variant="gray">Queued</Badge></td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="progress-bar" style={{ width: 80 }}><div className="progress-fill" style={{ width: '0%' }} /></div>
                    <span style={{ fontSize: 11 }}>0%</span>
                  </div>
                </td>
                <td><Badge variant="gray">—</Badge></td>
                <td style={{ color: 'var(--muted)' }}>~5s</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
