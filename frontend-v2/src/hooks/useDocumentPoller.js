import { useEffect, useRef } from 'react';
import { getStatus } from '../api/client';
import { useApp } from '../store/AppStore';

const TERMINAL_STATUSES = new Set(['completed', 'rejected', 'error', 'deleted']);
const POLL_INTERVAL = 2500; // ms

/**
 * Polls /status/{documentId} every 2.5s until a terminal status is reached.
 * Updates AppStore on every tick.
 */
export function useDocumentPoller(documentId) {
  const { updateDocument, addPolling, removePolling, toast } = useApp();
  const timerRef = useRef(null);
  const prevStatus = useRef(null);

  useEffect(() => {
    if (!documentId) return;

    let active = true;
    addPolling(documentId);

    const poll = async () => {
      try {
        const data = await getStatus(documentId);
        if (!active) return;

        // Map document_id to id so AppStore updates the correct item
        const payload = { ...data, id: data.document_id };
        updateDocument(payload);

        // Toast on status transitions
        if (prevStatus.current && prevStatus.current !== data.status) {
          if (data.status === 'completed') toast(`Document processed successfully!`, 'success');
          if (data.status === 'awaiting_review') toast(`Document needs human review.`, 'warn');
          if (data.status === 'rejected') toast(`Document rejected: ${data.message || 'See document for reason.'}`, 'error');
          if (data.status === 'error') toast(`Processing error: ${data.message}`, 'error');
        }
        prevStatus.current = data.status;

        if (!TERMINAL_STATUSES.has(data.status)) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL);
        } else {
          removePolling(documentId);
        }
      } catch (err) {
        if (!active) return;
        console.warn('Polling error for', documentId, err.message);
        timerRef.current = setTimeout(poll, POLL_INTERVAL * 2); // back-off
      }
    };

    poll();

    return () => {
      active = false;
      clearTimeout(timerRef.current);
      removePolling(documentId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);
}
