export function Btn({ variant = 'primary', onClick, children, style, className = '' }) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      onClick={onClick}
      style={style}
    >
      {children}
    </button>
  );
}
