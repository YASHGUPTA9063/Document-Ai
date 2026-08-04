import { Check, Cpu, Tag, FileSearch, CheckCircle, UserCheck, Package, Shield, Wand2 } from 'lucide-react';

const STEPS = [
  { key: 'intake', label: 'Ingestion', icon: Package },
  { key: 'pre_val', label: 'Quality Check', icon: Shield },
  { key: 'preprocess', label: 'Pre Processing', icon: Wand2 },
  { key: 'classify', label: 'Split & Classification', icon: Tag },
  { key: 'extract', label: 'Extraction', icon: FileSearch },
  { key: 'validate', label: 'Validation', icon: CheckCircle },
  { key: 'review', label: 'Human Review', icon: UserCheck },
  { key: 'output', label: 'Output', icon: Cpu },
];

/**
 * Maps backend status to which step is "running" and which are "done".
 *
 * Every status the backend writes must appear here — an unmapped status falls
 * back to -1 and freezes the timeline before the first step.
 */
const STATUS_TO_STEP = {
  pending: -1,
  processing: 0,        // intake
  pre_validating: 1,    // quality check
  preprocessing: 2,     // pre processing
  classifying: 3,       // split & classification
  fraud_checking: 3,    // runs alongside classification
  extracting: 4,        // extraction
  validating: 5,        // validation
  auto_verifying: 5,    // signature/face matching, part of validation
  reviewing: 6,         // human review
  awaiting_review: 6,   // parked waiting on a reviewer
  finalizing: 7,        // output
  completed: STEPS.length,  // every step done
  duplicate: -2,
  rejected: -2,
  failed: -2,
  error: -2,
};

function getStepState(status, idx) {
  const active = STATUS_TO_STEP[status] ?? -1;
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
