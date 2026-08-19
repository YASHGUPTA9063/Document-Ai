import { useEffect, useMemo, useState } from 'react';
import { Scissors, AlertTriangle, FileText, Check, X, CornerDownRight } from 'lucide-react';
import { getSplitManifest, submitSplitDecision, getClassificationConfig } from '../../api/client';
import { Modal } from './Modal';

/**
 * Split boundary review.
 *
 * Shown when the splitter found multiple documents in one upload but was not
 * confident enough to act alone. The reviewer works page by page: each page
 * after the first carries a "starts a new document" toggle, and every resulting
 * segment gets a document-type dropdown fed by the live classification config.
 *
 * Boundaries are edited here rather than after the fact because it is the last
 * moment where nothing has been written — no child rows, no files, no workflows.
 */
export function SplitReviewModal({ documentId, open, onClose, onDecided, toast }) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [manifest, setManifest] = useState(null);
  const [docTypes, setDocTypes] = useState([]);
  // starts[i] === true  =>  page i opens a new document. Page 0 is always true.
  const [starts, setStarts] = useState([]);
  const [types, setTypes] = useState({});   // start page index -> doc_type

  useEffect(() => {
    if (!open || !documentId) return;
    let active = true;

    (async () => {
      setLoading(true);
      try {
        const [data, configuredTypes] = await Promise.all([
          getSplitManifest(documentId),
          getClassificationConfig().catch(() => []),
        ]);
        if (!active) return;

        setManifest(data);
        setDocTypes((configuredTypes || []).map((t) => t.trim().toLowerCase().replace(/\s+/g, '_')));

        const pageCount = data.pages?.length || 0;
        const nextStarts = Array(pageCount).fill(false);
        const nextTypes = {};
        (data.segments || []).forEach((seg) => {
          nextStarts[seg.start] = true;
          nextTypes[seg.start] = seg.doc_type;
        });
        if (pageCount > 0) nextStarts[0] = true;
        setStarts(nextStarts);
        setTypes(nextTypes);
      } catch (err) {
        if (active) toast?.(err.message || 'Failed to load the split manifest', 'error');
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => { active = false; };
  }, [open, documentId, toast]);

  /** Rebuild segments from the current boundary toggles. */
  const segments = useMemo(() => {
    const result = [];
    starts.forEach((isStart, index) => {
      if (isStart || index === 0) {
        result.push({ start: index, end: index, doc_type: types[index] || 'others' });
      } else if (result.length) {
        result[result.length - 1].end = index;
      }
    });
    return result;
  }, [starts, types]);

  const pageInfo = (index) => manifest?.pages?.[index] || {};

  const toggleBoundary = (index) => {
    if (index === 0) return;   // the first page always opens a document
    setStarts((prev) => {
      const next = [...prev];
      next[index] = !next[index];
      return next;
    });
  };

  const setSegmentType = (start, value) => setTypes((prev) => ({ ...prev, [start]: value }));

  const decide = async (approved) => {
    setSubmitting(true);
    try {
      await submitSplitDecision(
        documentId,
        approved,
        approved ? segments.map(({ doc_type, start, end }) => ({ doc_type, start, end })) : null,
      );
      toast?.(
        approved
          ? `Split confirmed — ${segments.length} documents will be processed.`
          : 'Split cancelled — the file will be processed as one document.',
        'success',
      );
      onDecided?.();
      onClose?.();
    } catch (err) {
      toast?.(err.message || 'Failed to submit the split decision', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <Modal
      title="Confirm document split"
      subtitle="This upload looks like several documents stacked into one file."
      onClose={onClose}
      wide
    >
      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
          Loading detected boundaries…
        </div>
      ) : (
        <div style={{ maxWidth: 720 }}>
          <div style={{
            display: 'flex', gap: 10, alignItems: 'flex-start',
            background: 'var(--accent-dim)', border: '1px solid rgba(79,110,247,0.2)',
            borderRadius: 10, padding: '12px 14px', marginBottom: 16,
          }}>
            <Scissors size={15} style={{ color: 'var(--accent)', marginTop: 2, flexShrink: 0 }} />
            <div style={{ fontSize: 12.5, color: 'var(--text-dim)', lineHeight: 1.6 }}>
              <strong style={{ color: 'var(--text)' }}>{segments.length} documents</strong> detected
              across {manifest?.pages?.length || 0} pages of <em>{manifest?.filename}</em>. Toggle a page
              to change where a document starts, then confirm. Each document is processed
              independently from here.
            </div>
          </div>

          <div style={{ maxHeight: 420, overflowY: 'auto', paddingRight: 4 }}>
            {segments.map((segment) => (
              <div key={segment.start} style={{
                border: '1px solid var(--border)', borderRadius: 10,
                marginBottom: 10, overflow: 'hidden',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 12px', background: 'var(--card-alt)',
                  borderBottom: '1px solid var(--border)',
                }}>
                  <FileText size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
                    Pages {segment.start + 1}
                    {segment.end > segment.start ? `–${segment.end + 1}` : ''}
                  </span>
                  <select
                    value={segment.doc_type}
                    onChange={(e) => setSegmentType(segment.start, e.target.value)}
                    style={{
                      marginLeft: 'auto', fontSize: 12, padding: '4px 8px',
                      borderRadius: 6, border: '1px solid var(--border)',
                      background: 'var(--card)', color: 'var(--text)',
                    }}
                  >
                    {[...new Set([...docTypes, segment.doc_type, 'others'])].map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>

                {Array.from({ length: segment.end - segment.start + 1 }, (_, offset) => {
                  const index = segment.start + offset;
                  const info = pageInfo(index);
                  const lowConfidence = (info.confidence ?? 1) < 0.75;
                  return (
                    <div key={index} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 12px', borderTop: offset ? '1px solid var(--border)' : 'none',
                    }}>
                      <button
                        onClick={() => toggleBoundary(index)}
                        disabled={index === 0}
                        title={index === 0 ? 'The first page always starts a document' : 'Toggle: starts a new document'}
                        style={{
                          all: 'unset', cursor: index === 0 ? 'default' : 'pointer',
                          display: 'inline-flex', alignItems: 'center', gap: 5,
                          fontSize: 11, fontWeight: 600,
                          color: starts[index] ? 'var(--accent)' : 'var(--muted)',
                          opacity: index === 0 ? 0.5 : 1,
                        }}
                      >
                        {starts[index] ? <Scissors size={12} /> : <CornerDownRight size={12} />}
                        {starts[index] ? 'starts here' : 'continues'}
                      </button>

                      <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>Page {index + 1}</span>

                      {lowConfidence && (
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          fontSize: 10.5, color: 'var(--warn, #f59e0b)', marginLeft: 'auto',
                        }}>
                          <AlertTriangle size={11} />
                          low confidence ({((info.confidence ?? 0) * 100).toFixed(0)}%)
                        </span>
                      )}
                      {info.reasoning && !lowConfidence && (
                        <span style={{
                          fontSize: 10.5, color: 'var(--muted)', marginLeft: 'auto',
                          maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {info.reasoning}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 18 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => decide(false)} disabled={submitting}>
              <X size={13} /> Not a packet — process whole
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => decide(true)} disabled={submitting}>
              <Check size={13} /> {submitting ? 'Submitting…' : `Split into ${segments.length} documents`}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
