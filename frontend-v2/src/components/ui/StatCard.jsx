import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const DELTA_ICONS = {
  up:      <TrendingUp  size={11} />,
  down:    <TrendingDown size={11} />,
  warn:    <TrendingDown size={11} />,
  neutral: <Minus       size={11} />,
};

/**
 * StatCard — premium metric card with Lucide icon support
 *
 * @param {ReactNode} icon        — Lucide icon component (e.g. <FileText size={18} />)
 * @param {string}    iconVariant — 'accent' | 'success' | 'warn' | 'danger' | 'info'
 * @param {string}    label       — metric label
 * @param {any}       value       — primary metric value
 * @param {string}    unit        — optional unit suffix (e.g. '%')
 * @param {string}    delta       — secondary descriptive text
 * @param {string}    deltaType   — 'up' | 'down' | 'warn' | 'neutral'
 */
export function StatCard({
  icon,
  iconVariant = 'accent',
  label,
  value,
  unit = '',
  delta,
  deltaType = 'neutral',
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${iconVariant}`}>
        {icon}
      </div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {delta && (
        <div className={`stat-delta ${deltaType}`}>
          {DELTA_ICONS[deltaType]}
          {delta}
        </div>
      )}
    </div>
  );
}
