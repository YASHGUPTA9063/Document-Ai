import { useState, useEffect } from 'react';
import { procStepsData, procDelays, procPcts } from '../../data/mockData';
import { useApp } from '../../context/AppContext';

export function ProcessingModal() {
  const { setShowModal, navigate } = useApp();
  const [steps, setSteps] = useState(procStepsData.map((s) => ({ ...s, state: 'idle', statusText: 'Waiting' })));
  const [overallPct, setOverallPct] = useState(0);
  const [modalStatus, setModalStatus] = useState('Initializing agents...');

  useEffect(() => {
    let cancelled = false;

    function runStep(i) {
      if (cancelled) return;
      if (i >= procStepsData.length) {
        setModalStatus('✓ Processing complete! Redirecting...');
        setTimeout(() => {
          if (!cancelled) {
            setShowModal(false);
            navigate('extraction');
          }
        }, 1200);
        return;
      }

      setSteps((prev) =>
        prev.map((s, j) => j === i ? { ...s, state: 'active', statusText: '⟳' } : s)
      );
      setOverallPct(Math.round(procPcts[i] * 0.7));

      setTimeout(() => {
        if (cancelled) return;
        setSteps((prev) =>
          prev.map((s, j) =>
            j === i
              ? { ...s, state: 'done', statusText: '✓', detail: procStepsData[i].doneLabel }
              : s
          )
        );
        setOverallPct(procPcts[i]);
        runStep(i + 1);
      }, procDelays[i]);
    }

    runStep(0);
    return () => { cancelled = true; };
  }, [navigate, setShowModal]);

  return (
    <div className="processing-modal-overlay">
      <div className="modal-card">
        <div className="modal-title">🚀 AI Agents Processing</div>
        <div className="modal-sub">invoice_Q2_2024.pdf · Full Agentic Pipeline</div>

        <div className="processing-steps">
          {steps.map((s, i) => (
            <div
              key={i}
              className={`proc-step ${s.state === 'active' ? 'ps-active' : s.state === 'done' ? 'ps-done' : ''}`}
            >
              <div className="proc-icon">{s.icon}</div>
              <div className="proc-info">
                <div className="proc-name">{s.name}</div>
                <div className="proc-detail">{s.detail}</div>
              </div>
              <div
                className="proc-status"
                style={{
                  color: s.state === 'done'
                    ? 'var(--success)'
                    : s.state === 'active'
                    ? 'var(--accent)'
                    : 'var(--muted)',
                }}
              >
                {s.state === 'active' ? <span className="spin">⟳</span> : s.statusText}
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
            <span>Overall Progress</span>
            <span>{overallPct}%</span>
          </div>
          <div className="progress-bar" style={{ height: 8 }}>
            <div className="progress-fill" style={{ width: overallPct + '%', transition: 'width 0.3s ease' }} />
          </div>
        </div>

        <div style={{ marginTop: 16, fontSize: 12, color: 'var(--muted)', textAlign: 'center' }}>
          {modalStatus}
        </div>
      </div>
    </div>
  );
}
