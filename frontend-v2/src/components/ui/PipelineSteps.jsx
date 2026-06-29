import { Check, Cpu, Tag, FileSearch, CheckCircle, UserCheck, Package, Shield, Wand2 } from 'lucide-react';

const STEPS = [
  { key: 'intake',      label: 'Intake',       icon: Package    },
  { key: 'pre_val',     label: 'Pre-Validate', icon: Shield     },
  { key: 'preprocess',  label: 'Preprocess',   icon: Wand2      },
  { key: 'classify',    label: 'Classify',     icon: Tag        },
  { key: 'extract',     label: 'Extract',      icon: FileSearch },
  { key: 'validate',    label: 'Validate',     icon: CheckCircle },
  { key: 'review',      label: 'Review',       icon: UserCheck  },
  { key: 'output',      label: 'Output',       icon: Cpu        },
];

/**
 * Maps backend status to which step is "running" and which are "done".
 */
function getStepState(status, idx) {
  const order = {
    pending:         -1,
    processing:       0,  // intake step
    pre_validating:   1,  // pre-validate step
    preprocessing:    2,  // preprocess step (NEW)
    classifying:      3,  // was 2
    fraud_checking:   3,  // same as classifying (runs in parallel context)
    extracting:       4,  // was 3
    validating:       5,  // was 4
    awaiting_review:  6,  // was 5
    completed:        8,  // all done (8 steps total)
    rejected:         -2,
    error:            -2,
  };

  const active = order[status] ?? -1;
  if (active === 7) return 'done';
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
