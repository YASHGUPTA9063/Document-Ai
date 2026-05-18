import { useEffect, useRef } from 'react';
import { donutData, donutColors, donutLabels, donutPcts } from '../../data/mockData';

export function DonutChart() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = 120 * dpr;
    canvas.height = 120 * dpr;
    ctx.scale(dpr, dpr);

    const cx = 60, cy = 60, r = 44, innerR = 28;
    let start = -Math.PI / 2;

    donutData.forEach((v, i) => {
      const angle = (v / 100) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, start, start + angle);
      ctx.closePath();
      ctx.fillStyle = donutColors[i];
      ctx.fill();
      start += angle;
    });

    ctx.beginPath();
    ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
    ctx.fillStyle = '#1a1e30';
    ctx.fill();

    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 13px system-ui';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('5 Types', cx, cy);
  }, []);

  return (
    <div className="donut-wrap">
      <canvas ref={canvasRef} className="donut" />
      <div className="legend">
        {donutLabels.map((label, i) => (
          <div key={i} className="legend-item">
            <div className="legend-dot" style={{ background: donutColors[i] }} />
            <div className="legend-label">{label}</div>
            <div className="legend-val">{donutPcts[i]}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
