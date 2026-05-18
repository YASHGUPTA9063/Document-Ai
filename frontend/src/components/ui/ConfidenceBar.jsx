import { useEffect, useRef } from 'react';

export function ConfidenceBar({ label, pct, color, animate = true }) {
  const fillRef = useRef(null);

  useEffect(() => {
    if (!animate) return;
    const timer = setTimeout(() => {
      if (fillRef.current) fillRef.current.style.width = pct + '%';
    }, 200);
    return () => clearTimeout(timer);
  }, [pct, animate]);

  return (
    <div className="confidence-bar">
      <div className="conf-label">{label}</div>
      <div className="conf-track">
        <div
          ref={fillRef}
          className="conf-fill"
          style={{ width: animate ? '0%' : pct + '%', background: color }}
        />
      </div>
      <div className="conf-pct" style={{ color }}>{pct}%</div>
    </div>
  );
}
