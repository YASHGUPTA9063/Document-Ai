import { pipelineSteps } from '../../data/mockData';

export function Pipeline({ states = [] }) {
  return (
    <div className="pipeline">
      {pipelineSteps.map((step, i) => {
        const state = states[i] || '';
        return (
          <div key={i} className={`pipeline-step ${state}`}>
            <div className="step-circle">
              {state === 'done' ? '✓' : step.icon}
            </div>
            <div className="step-label">{step.label}</div>
            <div className="step-time">
              {state === 'done' ? step.time : state === 'running' ? '...' : ''}
            </div>
          </div>
        );
      })}
    </div>
  );
}
