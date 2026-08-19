import { Check, Cpu, Tag, FileSearch, CheckCircle, UserCheck, Package, Shield, Wand2, Scissors } from 'lucide-react';

const STEPS = [
  { key: 'intake', label: 'Ingestion', icon: Package },
  { key: 'split', label: 'Packet Split', icon: Scissors },
  { key: 'pre_val', label: 'Quality Check', icon: Shield },
  { key: 'preprocess', label: 'Pre Processing', icon: Wand2 },
  { key: 'classify', label: 'Classification', icon: Tag },
  { key: 'extract', label: 'Extraction', icon: FileSearch },
  { key: 'validate', label: 'Validation', icon: CheckCircle },
  { key: 'review', label: 'Human Review', icon: UserCheck },
  { key: 'output', label: 'Output', icon: Cpu },
];

/**
 * Maps backend status to which step is "running" and which are "done".
 */
function getStepState(status, idx) {
  const order = {
    pending: -1,
    processing: 0,          // intake
    splitting: 1,           // packet split detection
    awaiting_split_review: 1,
    split: 9,               // packet done — its children carry on separately
    pre_validating: 2,
    preprocessing: 3,
    classifying: 4,
    fraud_checking: 4,      // runs alongside classification
    extracting: 5,
    validating: 6,
    awaiting_review: 7,
    completed: 9,           // all done (9 steps total)
    rejected: -2,
    error: -2,
  };

  const active = order[status] ?? -1;
  if (active === 8) return 'done';
  if (idx < active) return 'done';
  if (idx === active) return 'running';
  return '';
}

export function PipelineSteps({ status }) {
  return (
    <div className="pipeline">
      {STEPS.map(({ key, label, icon: Icon }, idx) => {
        const state = getStepState(status, idx);
        return (
          <div key={key} className={`pipeline-step ${state}`}>
            <div className="step-circle">
              {state === 'done' ? (
                <Check size={15} />
              ) : (
                <Icon size={15} />
              )}
            </div>
            <div className="step-label">{label}</div>
          </div>
        );
      })}
    </div>
  );
}
