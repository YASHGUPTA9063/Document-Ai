import { StatCard } from '../components/ui/StatCard';
import { Card, CardHeader } from '../components/ui/Card';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';
import { accuracyData, agentPerfData } from '../data/mockData';

export function Analytics() {
  return (
    <div className="page page-enter">
      <div className="stats-row" style={{ marginBottom: 24 }}>
        <StatCard icon="⏱️" label="P95 Latency" value="3.8" unit="s" delta="↑ Better than SLA" deltaType="up" />
        <StatCard icon="💸" label="Cost / Document" value="$0.004" delta="↑ 62% reduction" deltaType="up" />
        <StatCard icon="🔄" label="Retry Rate" value="1.2" unit="%" delta="↑ Industry avg: 8%" deltaType="up" />
        <StatCard icon="👷" label="Human Reviews" value="0.8" unit="%" delta="↑ 95%+ automation" deltaType="up" />
      </div>

      <div className="grid-2">
        <Card>
          <CardHeader title="Accuracy by Document Type" />
          {accuracyData.map((d) => (
            <ConfidenceBar key={d.label} label={d.label} pct={d.pct} color={d.color} animate={false} />
          ))}
        </Card>
        <Card>
          <CardHeader title="Agent Performance Scores" />
          {agentPerfData.map((d) => (
            <ConfidenceBar key={d.label} label={d.label} pct={d.pct} color={d.color} animate={false} />
          ))}
        </Card>
      </div>
    </div>
  );
}
