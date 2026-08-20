import {
  Upload, Bot, FileSearch, CheckCircle, AlertTriangle, Check, X, AlertCircle, Shield, Wand2, Scissors,
  ListChecks
} from 'lucide-react';

const STATUS_MAP = {
  pending:          { label: 'Pending',          cls: 'badge-gray',   icon: null },
  pre_validating:   { label: 'Quality Check',    cls: 'badge-cyan',   icon: Shield },
  preprocessing:    { label: 'Pre Processing',   cls: 'badge-purple', icon: Wand2 },
  processing:       { label: 'Ingestion',        cls: 'badge-blue',   icon: Upload },
  splitting:        { label: 'Splitting',        cls: 'badge-blue',   icon: Scissors },
  split:            { label: 'Split Packet',     cls: 'badge-purple', icon: Scissors },
  awaiting_split_review: { label: 'Confirm Split', cls: 'badge-yellow', icon: AlertTriangle },
  classifying:      { label: 'Classification',   cls: 'badge-blue',   icon: Bot },
  checklist:        { label: 'Checklist',        cls: 'badge-blue',   icon: ListChecks },
  awaiting_checklist_review: { label: 'Missing Documents', cls: 'badge-yellow', icon: ListChecks },
  fraud_checking:   { label: 'Fraud Checking',   cls: 'badge-blue',   icon: Shield },
  extracting:       { label: 'Extraction',       cls: 'badge-blue',   icon: FileSearch },

  validating:       { label: 'Validation',       cls: 'badge-blue',   icon: CheckCircle },
  awaiting_review:  { label: 'Human Review',     cls: 'badge-yellow', icon: AlertTriangle },
  duplicate:        { label: 'Duplicate',        cls: 'badge-yellow', icon: AlertTriangle },
  completed:        { label: 'Completed',        cls: 'badge-green',  icon: Check },
  rejected:         { label: 'Rejected',         cls: 'badge-red',    icon: X },
  failed:           { label: 'Failed',           cls: 'badge-red',    icon: AlertCircle },
  error:            { label: 'Error',            cls: 'badge-red',    icon: AlertCircle },
  deleted:          { label: 'Deleted',          cls: 'badge-gray',   icon: null },
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
