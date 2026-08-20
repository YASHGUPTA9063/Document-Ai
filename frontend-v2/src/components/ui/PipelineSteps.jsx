import { Check, Cpu, Tag, FileSearch, CheckCircle, UserCheck, Package, Shield, Wand2, Scissors, ListChecks } from 'lucide-react';

const STEPS = [
  { key: 'intake', label: 'Ingestion', icon: Package },
  { key: 'split', label: 'Packet Split', icon: Scissors },
  { key: 'pre_val', label: 'Quality Check', icon: Shield },
  { key: 'preprocess', label: 'Pre Processing', icon: Wand2 },
  { key: 'classify', label: 'Classification', icon: Tag },
  { key: 'checklist', label: 'Checklist', icon: ListChecks },
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
    split: 10,              // packet done — its children carry on separately
    pre_validating: 2,
    preprocessing: 3,
    classifying: 4,
    checklist: 5,                    // batch checklist (Step 3.2)
    checklist_hold: 5,               // parked behind the batch barrier
    awaiting_checklist_review: 5,    // parked at the checklist gate
    fraud_checking: 5,      // runs after classification, alongside the checklist
    extracting: 6,
    validating: 7,
    awaiting_review: 8,
    completed: 10,          // all done (10 steps total)
    rejected: -2,
    error: -2,
  };

  const active = order[status] ?? -1;
  if (active === 9) return 'done';
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
