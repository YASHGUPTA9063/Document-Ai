import { useEffect, useRef } from 'react';

export function LogContainer({ logs, maxHeight = 280 }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="log-container" style={{ maxHeight }}>
      {logs.map((entry) => (
        <div key={entry.id} className="log-entry">
          <span className="log-time">{entry.ts}</span>
          <span className={`log-agent ${entry.cls}`}>{entry.agent}</span>
          <span className="log-msg">{entry.text}</span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
