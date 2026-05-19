import { Check, Cpu, Tag, FileSearch, CheckCircle, UserCheck, Package } from 'lucide-react';

const STEPS = [
  { key: 'intake',    label: 'Intake',    icon: Package   },
  { key: 'classify',  label: 'Classify',  icon: Tag       },
  { key: 'extract',   label: 'Extract',   icon: FileSearch },
  { key: 'validate',  label: 'Validate',  icon: CheckCircle },
  { key: 'review',    label: 'Review',    icon: UserCheck },
  { key: 'output',    label: 'Output',    icon: Cpu       },
];

/**
 * Maps backend status to which step is "running" and which are "done".
 */
function getStepState(status, idx) {
  const order = {
    pending:         -1,
    processing:       0,  // intake step
    classifying:      1,
    extracting:       2,
    validating:       3,
    awaiting_review:  4,  // review step
    completed:        6,  // all done
    rejected:         -2,
    error:            -2,
  };
  const active = order[status] ?? -1;
  if (active === 6) return 'done';
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
