import { useEffect, useRef } from 'react';

const COLORS = ['#6366f1','#06b6d4','#10b981','#f59e0b','#8b5cf6','#ef4444','#3b82f6'];

export function DonutChart({ data = [] }) {
  const canvasRef = useRef(null);
  const total = data.reduce((s, d) => s + d.value, 0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !total) return;
    const ctx = canvas.getContext('2d');
    const cx = canvas.width / 2, cy = canvas.height / 2;
    const r = Math.min(cx, cy) - 6, hole = r * 0.58;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let start = -Math.PI / 2;

    data.forEach((d, i) => {
      const slice = (d.value / total) * 2 * Math.PI;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, start, start + slice);
      ctx.closePath();
      ctx.fillStyle = COLORS[i % COLORS.length];
      ctx.fill();
      start += slice;
    });

    // Cut hole
    ctx.beginPath();
    ctx.arc(cx, cy, hole, 0, 2 * Math.PI);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--card').trim() || '#151826';
    ctx.fill();

    // Center text
    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 16px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(total, cx, cy);
  }, [data, total]);

  if (!total) {
    return (
      <div className="empty-state" style={{ padding: '24px' }}>
        <div className="empty-icon">📊</div>
        <div className="empty-sub">No data yet</div>
      </div>
    );
  }

  return (
    <div className="donut-wrap">
      <canvas ref={canvasRef} width={120} height={120} />
      <div className="donut-legend">
        {data.map((d, i) => (
          <div key={d.label} className="legend-item">
            <div className="legend-dot" style={{ background: COLORS[i % COLORS.length] }} />
            <span style={{ color: 'var(--text-dim)' }}>{d.label}</span>
            <span style={{ color: 'var(--muted)', marginLeft: 'auto', marginRight: 0 }}>
              {Math.round((d.value / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
