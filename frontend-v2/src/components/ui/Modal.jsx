import { X } from 'lucide-react';

export function Modal({ title, subtitle, onClose, children, footer, wide }) {
  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal${wide ? ' modal-wide' : ''}`}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div className="modal-title">{title}</div>
            {subtitle && <div className="modal-sub">{subtitle}</div>}
          </div>
          {onClose && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={onClose}
              style={{ padding: '4px 8px' }}
            >
              <X size={14} />
            </button>
          )}
        </div>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          {children}
        </div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
