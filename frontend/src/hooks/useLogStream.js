import { useState, useEffect, useRef, useCallback } from 'react';
import { logMessages } from '../data/mockData';

export function useLogStream(containerId) {
  const [logs, setLogs] = useState([]);
  const indexRef = useRef(0);
  const timerRef = useRef(null);

  const addLog = useCallback((msg) => {
    const now = new Date();
    const ts = [
      now.getHours().toString().padStart(2, '0'),
      now.getMinutes().toString().padStart(2, '0'),
      now.getSeconds().toString().padStart(2, '0'),
    ].join(':');
    setLogs((prev) => [...prev, { ts, icon: msg[0], cls: msg[1], agent: msg[2], text: msg[3], id: Date.now() + Math.random() }]);
  }, []);

  const stream = useCallback(() => {
    if (indexRef.current < logMessages.length) {
      addLog(logMessages[indexRef.current++]);
      timerRef.current = setTimeout(stream, 400 + Math.random() * 600);
    }
  }, [addLog]);

  const reset = useCallback(() => {
    indexRef.current = 0;
    setLogs([]);
  }, []);

  const start = useCallback((delay = 0) => {
    timerRef.current = setTimeout(stream, delay);
  }, [stream]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return { logs, start, reset };
}
