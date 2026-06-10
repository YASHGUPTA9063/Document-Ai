import {
  Upload, Bot, FileSearch, CheckCircle, AlertTriangle, Check, X, AlertCircle
} from 'lucide-react';

const STATUS_MAP = {
  pending:          { label: 'Pending',        cls: 'badge-gray',   icon: null },
  processing:       { label: 'Intake',         cls: 'badge-blue',   icon: Upload },
  classifying:      { label: 'Classifying',    cls: 'badge-blue',   icon: Bot },
  extracting:       { label: 'Extracting',     cls: 'badge-blue',   icon: FileSearch },
  validating:       { label: 'Validating',     cls: 'badge-blue',   icon: CheckCircle },
  awaiting_review:  { label: 'Needs Review',   cls: 'badge-yellow', icon: AlertTriangle },
  completed:        { label: 'Completed',      cls: 'badge-green',  icon: Check },
  rejected:         { label: 'Rejected',       cls: 'badge-red',    icon: X },
  error:            { label: 'Error',          cls: 'badge-red',    icon: AlertCircle },
  deleted:          { label: 'Deleted',        cls: 'badge-gray',   icon: null },
};

export function StatusBadge({ status }) {
  const s = STATUS_MAP[status] || { label: status, cls: 'badge-gray', icon: null };
  const Icon = s.icon;
  return (
    <span className={`badge ${s.cls}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {Icon && <Icon size={11} strokeWidth={2.5} />}
      {s.label}
    </span>
  );
}
