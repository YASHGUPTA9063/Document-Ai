import { sparklineVals } from '../../data/mockData';

export function Sparkline() {
  const max = Math.max(...sparklineVals);
  return (
    <div className="sparkline">
      {sparklineVals.map((v, i) => (
        <div
          key={i}
          className="spark-bar"
          style={{ height: `${Math.max(4, (v / max) * 40)}px` }}
          data-tip={`${v} docs`}
        />
      ))}
    </div>
  );
}
