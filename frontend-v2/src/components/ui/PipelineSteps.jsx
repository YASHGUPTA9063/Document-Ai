import { Check, Cpu, Tag, FileSearch, CheckCircle, UserCheck, Package, Shield, Wand2, Scissors, ListChecks } from 'lucide-react';
import { useApp } from '../../store/AppStore';

// Every step carries a `phase` — its position in the backend pipeline, fixed
// regardless of which steps are on screen. Optional steps name the feature flag
// that switches them on; with the flag off the step is dropped entirely and the
// remaining phases still order correctly, so nothing has to be renumbered.
const ALL_STEPS = [
  { key: 'intake',     phase: 1,  label: 'Ingestion',      icon: Package },
  { key: 'split',      phase: 2,  label: 'Packet Split',   icon: Scissors,    feature: 'doc_splitting' },
  { key: 'pre_val',    phase: 3,  label: 'Quality Check',  icon: Shield },
  { key: 'preprocess', phase: 4,  label: 'Pre Processing', icon: Wand2 },
  { key: 'classify',   phase: 5,  label: 'Classification', icon: Tag },
  { key: 'checklist',  phase: 6,  label: 'Checklist',      icon: ListChecks,  feature: 'doc_checklist' },
  { key: 'extract',    phase: 7,  label: 'Extraction',     icon: FileSearch },
  { key: 'validate',   phase: 8,  label: 'Validation',     icon: CheckCircle },
  { key: 'review',     phase: 9,  label: 'Human Review',   icon: UserCheck },
  { key: 'output',     phase: 10, label: 'Output',         icon: Cpu },
];

// Anything at or past this phase means the pipeline is finished — every visible
// step reads as done.
const TERMINAL_PHASE = 11;

// Backend status -> pipeline phase. Statuses belonging to a switched-off step
// simply never arrive, so they cost nothing by staying in the table.
const STATUS_PHASE = {
  pending: 0,
  processing: 1,               // intake
  splitting: 2,                // packet split detection
  awaiting_split_review: 2,
  split: TERMINAL_PHASE,       // packet done — its children carry on separately
  pre_validating: 3,
  preprocessing: 4,
  classifying: 5,
  checklist: 6,                    // batch checklist (Step 3.2)
  checklist_hold: 6,               // parked behind the batch barrier
  awaiting_checklist_review: 6,    // parked at the checklist gate
  fraud_checking: 6,      // runs after classification, alongside the checklist
  extracting: 7,
  validating: 8,
  awaiting_review: 9,
  completed: TERMINAL_PHASE,
  rejected: -1,
  error: -1,
};

/**
 * The live pipeline for one document. Optional stages the deployment has
 * switched off are not rendered at all — a step the workflow will never run
 * has no business sitting greyed out in the pipeline.
 */
export function PipelineSteps({ status }) {
  const { features } = useApp();
  const steps = ALL_STEPS.filter((s) => !s.feature || features[s.feature]);

  const activePhase = STATUS_PHASE[status] ?? 0;
  const done = activePhase >= TERMINAL_PHASE;

  // The running step is the last visible one the document has reached. Picking
  // the *last* at or below the phase — rather than an exact match — is what
  // keeps a status whose own step is hidden (a fraud check with the checklist
  // switched off, say) showing progress on the step before it.
  const runningIdx = done
    ? -1
    : steps.reduce((found, s, i) => (s.phase <= activePhase ? i : found), -1);

  return (
    <div className="pipeline">
      {steps.map(({ key, label, icon: Icon }, idx) => {
        const state = done || idx < runningIdx ? 'done' : idx === runningIdx ? 'running' : '';
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
