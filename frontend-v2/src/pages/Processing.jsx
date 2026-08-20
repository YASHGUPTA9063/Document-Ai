import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Cpu, CheckCircle, ListTodo, FileText, AlertCircle, ChevronDown, ChevronUp, Scissors, ListChecks } from 'lucide-react';
import { useApp } from '../store/AppStore';
import {
  ACTIVE_STATUSES, REVIEW_STATUSES, SPLIT_REVIEW_STATUS,
  CHECKLIST_REVIEW_STATUS, CHECKLIST_GATE_STATUSES,
} from '../store/documentStatus';
import { useDocumentList } from '../hooks/useDocumentList';
import { useDocumentPoller } from '../hooks/useDocumentPoller';
import { StatusBadge } from '../components/ui/StatusBadge';
import { PipelineSteps } from '../components/ui/PipelineSteps';
import { SplitReviewModal } from '../components/ui/SplitReviewModal';
import { ChecklistReviewModal } from '../components/ui/ChecklistReviewModal';

// While anything is in flight the list is re-fetched on this cadence. A packet
// split creates its child documents server-side, and they only become visible
// to the queue on the next fetch — the per-document poller never sees them.
const LIST_REFRESH_INTERVAL = 4000; // ms

// The queue is briefly empty at the seam between a packet finishing its split
// and its children appearing in the list. Confirm the drain against the server
// before treating it as "everything is done".
const DRAIN_SETTLE_DELAY = 1500; // ms

/** Renders a rejection/failure reason with expand/collapse if the text is long */
function ExpandableReason({ reason }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = reason.length > 80;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      marginTop: 4, padding: '4px 7px',
      background: 'rgba(239,68,68,0.08)',
      border: '1px solid rgba(239,68,68,0.2)',
      borderRadius: 5,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 5 }}>
        <AlertCircle size={11} style={{ color: 'var(--danger)', marginTop: 1, flexShrink: 0 }} />
        <span style={{ fontSize: 10, color: 'var(--danger)', lineHeight: 1.4, flex: 1 }}>
          {isLong && !expanded ? reason.slice(0, 80) + '…' : reason}
        </span>
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            marginTop: 3, marginLeft: 16,
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--danger)', fontSize: 9, display: 'flex', alignItems: 'center', gap: 2,
            opacity: 0.75, padding: 0,
          }}
        >
          {expanded ? <><ChevronUp size={9} /> Show less</> : <><ChevronDown size={9} /> Show more</>}
        </button>
      )}
    </div>
  );
}

// Renders one poller per active doc
function PollersRenderer({ ids }) {
  return ids.map((id) => <SinglePoller key={id} docId={id} />);
}
function SinglePoller({ docId }) {
  useDocumentPoller(docId);
  return null;
}

export function Processing() {
  const { documents, pendingDocs, reviewDocs, toast } = useApp();
  const { refresh, loading } = useDocumentList();
  const navigate = useNavigate();
  const [reviewingSplit, setReviewingSplit] = useState(null);
  // batch_id of the upload parked at the checklist barrier. The decision is
  // batch-scoped, so it does not matter which held document was clicked.
  const [reviewingChecklist, setReviewingChecklist] = useState(null);

  useEffect(() => { refresh(); }, []);

  // Keep the list in sync while work is in flight, so documents that appear
  // out of band — the children of a split packet — join the queue on their own.
  useEffect(() => {
    if (pendingDocs.length === 0) return;
    const id = setInterval(() => refresh(), LIST_REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [pendingDocs.length, refresh]);

  // Redirect to /validation when any doc needs human review
  useEffect(() => {
    if (reviewDocs.length > 0) navigate('/validation');
  }, [reviewDocs.length]);

  // Redirect to /extraction when all queued docs finish processing
  const prevPendingCount = useRef(0);
  const prevPendingIds = useRef([]);
  const settleTimer = useRef(null);
  useEffect(() => {
    if (prevPendingCount.current > 0 && pendingDocs.length === 0 && reviewDocs.length === 0) {
      const drainedIds = prevPendingIds.current;
      clearTimeout(settleTimer.current);
      settleTimer.current = setTimeout(async () => {
        // Re-check against the server: a packet that just finished splitting
        // empties the local queue a beat before its children show up, and
        // navigating away on that gap is what made the page look broken.
        const docs = await refresh();
        if (!docs) return;  // fetch failed — stay put rather than guess
        const stillWorking = docs.some(
          (d) => ACTIVE_STATUSES.includes(d.status) || REVIEW_STATUSES.includes(d.status)
        );
        if (stillWorking) return;

        // Find the first doc that just completed from the previous pending set
        const justCompleted = docs.find(
          (d) => drainedIds.includes(d.id) && d.status === 'completed'
        );
        navigate('/extraction', { state: { docId: justCompleted?.id } });
      }, DRAIN_SETTLE_DELAY);
    }
    prevPendingCount.current = pendingDocs.length;
    prevPendingIds.current = pendingDocs.map((d) => d.id);
  }, [pendingDocs.length, reviewDocs.length]);

  useEffect(() => () => clearTimeout(settleTimer.current), []);

  // Most recently active doc for the live pipeline display. A packet waiting on
  // a split decision is the one thing worth looking at, so it wins the slot.
  const featured =
    pendingDocs.find((d) => d.status === SPLIT_REVIEW_STATUS) ||
    pendingDocs.find((d) => d.status === CHECKLIST_REVIEW_STATUS) ||
    pendingDocs[0];

  return (
    <div className="page">
      {/* Activate pollers for all pending docs */}
      <PollersRenderer ids={pendingDocs.map((d) => d.id)} />

      {reviewingSplit && (
        <SplitReviewModal
          documentId={reviewingSplit}
          open
          toast={toast}
          onClose={() => setReviewingSplit(null)}
          onDecided={() => refresh()}
        />
      )}

      {reviewingChecklist && (
        <ChecklistReviewModal
          batchId={reviewingChecklist}
          open
          toast={toast}
          onClose={() => setReviewingChecklist(null)}
          onDecided={() => refresh()}
        />
      )}

      {/* Live Pipeline for featured doc */}
      {featured ? (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Cpu size={16} style={{ color: 'var(--accent)' }} />
                Live Processing Pipeline
              </div>
              <div className="card-sub">
                Processing: <strong style={{ color: 'var(--accent)' }}>{featured.filename}</strong>
              </div>
            </div>
            <div className="chip" style={{ gap: 6 }}>
              <span className="pulse-dot" style={{ width: 6, height: 6 }} />
              Live
            </div>
          </div>
          <PipelineSteps status={featured.status} />
        </div>
      ) : (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon-wrap" style={{ color: 'var(--success)', background: 'var(--success-dim)', border: '1px solid var(--success-border)' }}>
              <CheckCircle size={32} />
            </div>
            <div className="empty-title">No active processing</div>
            <div className="empty-sub">All documents have been processed or the queue is empty.</div>
            <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => navigate('/upload')}>
              Upload Documents
            </button>
          </div>
        </div>
      )}

      {/* Processing Queue Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ListTodo size={16} style={{ color: 'var(--accent)' }} />
            Processing Queue
          </div>
          <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>
            <RefreshCw size={12} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>

        {pendingDocs.length === 0 ? (
          <div className="empty-state" style={{ padding: '24px' }}>
            <div className="empty-sub">No documents currently in the processing pipeline.</div>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Workflow Run</th>
                </tr>
              </thead>
              <tbody>
                {pendingDocs.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
                      <span style={{ fontSize: 12 }}>{doc.filename}</span>
                    </td>
                    <td>
                      {doc.doc_type
                        ? <span className="badge badge-cyan">{doc.doc_type}</span>
                        : <span style={{ color: 'var(--muted)', fontSize: 11 }}>Classifying…</span>}
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                        <StatusBadge status={doc.status} />
                        {doc.status === SPLIT_REVIEW_STATUS && (
                          <button
                            className="btn btn-primary btn-sm"
                            style={{ padding: '3px 8px', fontSize: 11 }}
                            onClick={() => setReviewingSplit(doc.id)}
                          >
                            <Scissors size={11} /> Review split
                          </button>
                        )}
                        {/* Offered on every held document, not just the gate
                            holder — the decision covers the whole batch. */}
                        {CHECKLIST_GATE_STATUSES.includes(doc.status) && (
                          <button
                            className="btn btn-primary btn-sm"
                            style={{ padding: '3px 8px', fontSize: 11 }}
                            onClick={() => setReviewingChecklist(doc.batch_id)}
                            disabled={!doc.batch_id}
                            title={doc.batch_id ? 'Review the batch checklist' : 'This document has no upload batch'}
                          >
                            <ListChecks size={11} /> Review checklist
                          </button>
                        )}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'monospace' }}>
                        {doc.workflow_run_id?.slice(0, 16) || '—'}…
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* All Documents Mini Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">All Documents</div>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/documents')}>
            Full List →
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th><th>Type</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {documents.slice(0, 10).map((doc) => (
                <tr key={doc.id} style={{ cursor: 'pointer' }} onClick={() => navigate('/extraction')}>
                  <td>
                    <FileText size={14} className="doc-icon" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
                    <span style={{ fontSize: 12 }}>{doc.filename}</span>
                  </td>
                  <td>
                    {doc.doc_type
                      ? <span className="badge badge-cyan">{doc.doc_type}</span>
                      : <span style={{ color: 'var(--muted)', fontSize: 11 }}>—</span>}
                  </td>
                  <td style={{ whiteSpace: 'normal', overflow: 'visible' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                      <StatusBadge status={doc.status} />
                      {['rejected', 'failed', 'error'].includes(doc.status) && doc.message && (
                        <ExpandableReason reason={doc.message} />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
