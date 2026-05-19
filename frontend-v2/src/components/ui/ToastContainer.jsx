import { useApp } from '../../store/AppStore';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

const ICONS = {
  success: <CheckCircle size={16} color="var(--success)" />,
  error:   <AlertCircle size={16} color="var(--danger)" />,
  info:    <Info        size={16} color="var(--accent)" />,
  warn:    <AlertTriangle size={16} color="var(--warn)" />,
};

export function ToastContainer() {
  const { toasts, dismissToast } = useApp();

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`}>
          <span className="toast-icon">{ICONS[t.type] || ICONS.info}</span>
          <span className="toast-msg">{t.msg}</span>
          <button className="toast-close" onClick={() => dismissToast(t.id)}>
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}
