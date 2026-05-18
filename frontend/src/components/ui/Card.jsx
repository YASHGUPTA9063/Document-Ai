export function Card({ children, style, className = '' }) {
  return <div className={`card ${className}`} style={style}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="card-header">
      <div>
        <div className="card-title">{title}</div>
        {subtitle && <div className="card-sub">{subtitle}</div>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
