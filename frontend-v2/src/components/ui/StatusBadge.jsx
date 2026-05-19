const STATUS_MAP = {
  pending:          { label: 'Pending',        cls: 'badge-gray'   },
  processing:       { label: '📦 Intake',      cls: 'badge-blue'   },
  classifying:      { label: '🏷️ Classifying', cls: 'badge-blue'   },
  extracting:       { label: '🔍 Extracting',  cls: 'badge-blue'   },
  validating:       { label: '✅ Validating',  cls: 'badge-blue'   },
  awaiting_review:  { label: '⏳ Needs Review', cls: 'badge-yellow' },
  completed:        { label: '✓ Completed',    cls: 'badge-green'  },
  rejected:         { label: '✕ Rejected',     cls: 'badge-red'    },
  error:            { label: '⚠ Error',         cls: 'badge-red'    },
  deleted:          { label: 'Deleted',         cls: 'badge-gray'   },
};

export function StatusBadge({ status }) {
  const s = STATUS_MAP[status] || { label: status, cls: 'badge-gray' };
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}
