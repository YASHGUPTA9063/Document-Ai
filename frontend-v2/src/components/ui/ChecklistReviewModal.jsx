import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ListChecks, AlertTriangle, Check, X, FileText, UploadCloud, RefreshCw, HelpCircle,
} from 'lucide-react';
import {
  getBatchChecklist, submitChecklistDecision, uploadDocumentsBatch,
} from '../../api/client';
import { Modal } from './Modal';

/**
 * Batch checklist review (Step 3.2).
 *
 * Shown when every document in an upload batch has been classified but the
 * batch does not cover all of the configured classification types. The reviewer
 * either supplies the missing documents — they are uploaded into the *same*
 * batch, so the checklist is re-evaluated against them — or continues anyway
 * because the missing types do not apply to this submission.
 *
 * The gate is held by one document per batch (the last one to classify), which
 * is why the decision is submitted against `gateDocumentId` rather than against
 * whichever row the reviewer happened to click.
 */
export function ChecklistReviewModal({ batchId, gateDocumentId, open, onClose, onDecided, toast }) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [checklist, setChecklist] = useState(null);
  const [note, setNote] = useState('');
  const fileInput = useRef(null);

  const load = useCallback(async () => {
    if (!batchId) return;
    setLoading(true);
    try {
      setChecklist(await getBatchChecklist(batchId));
    } catch (err) {
      toast?.(err.message || 'Failed to load the batch checklist', 'error');
    } finally {
      setLoading(false);
    }
  }, [batchId, toast]);

  useEffect(() => {
    if (!open) return;
    // Deferred into a task rather than called straight from the effect body, so
    // the first fetch does not set state during the render commit.
    (async () => { await load(); })();
  }, [open, load]);

  const addMissingFiles = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';           // let the same file be picked again after a failure
    if (!files.length) return;

    setUploading(true);
    try {
      // Same batchId — the new documents join the set the gate is waiting on,
      // which is what makes the re-check meaningful rather than cosmetic.
      const result = await uploadDocumentsBatch(files, null, { batchId });
      toast?.(
        `${result.succeeded} document(s) added to this batch. They will be classified, then re-checked.`,
        'success',
      );
      await load();
    } catch (err) {
      toast?.(err.message || 'Failed to upload the missing documents', 'error');
    } finally {
      setUploading(false);
    }
  };

  const decide = async (proceed) => {
    setSubmitting(true);
    try {
      await submitChecklistDecision(gateDocumentId, proceed, note.trim() || null);
      toast?.(
        proceed
          ? 'Continuing with the batch as it stands.'
          : 'Batch rejected as incomplete.',
        proceed ? 'success' : 'info',
      );
      onDecided?.();
      onClose?.();
    } catch (err) {
      toast?.(err.message || 'Failed to submit the checklist decision', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  const missing = checklist?.missing || [];
  const present = checklist?.present || [];
  const required = checklist?.required || [];
  const unclassified = checklist?.unclassified || [];
  const pendingCount = checklist?.pending_count || 0;

  return (
    <Modal
      title="Missing documents in this upload"
      subtitle="Some of the configured document types were not uploaded."
      onClose={onClose}
      wide
    >
      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
          Loading the batch checklist…
        </div>
      ) : (
        <div style={{ maxWidth: 720 }}>
          {/* Agent summary */}
          <div style={{
            display: 'flex', gap: 10, alignItems: 'flex-start',
            background: missing.length ? 'rgba(245,158,11,0.08)' : 'var(--accent-dim)',
            border: `1px solid ${missing.length ? 'rgba(245,158,11,0.25)' : 'rgba(79,110,247,0.2)'}`,
            borderRadius: 10, padding: '12px 14px', marginBottom: 16,
          }}>
            <ListChecks
              size={15}
              style={{ color: missing.length ? 'var(--warn, #f59e0b)' : 'var(--accent)', marginTop: 2, flexShrink: 0 }}
            />
            <div style={{ fontSize: 12.5, color: 'var(--text-dim)', lineHeight: 1.6 }}>
              <strong style={{ color: 'var(--text)' }}>
                {present.length} of {required.length} document types present
              </strong>
              {checklist?.summary ? <> — {checklist.summary}</> : null}
              {checklist?.source === 'deterministic' && (
                <span style={{ opacity: 0.6, fontSize: 11 }}> (checklist agent unavailable)</span>
              )}
              {/* The lines below are always reconciled live, so they can disagree
                  with the verdict the gate was opened on — documents arrived, or
                  an admin edited the classification types since. */}
              {checklist?.stale && (
                <div style={{ marginTop: 6, fontSize: 11.5, color: 'var(--warn, #f59e0b)' }}>
                  This batch has changed since it was checked — the list below is current.
                  {missing.length === 0 && ' Nothing is outstanding now; continue to release it.'}
                </div>
              )}
            </div>
          </div>

          {/* Checklist lines */}
          <div style={{ maxHeight: 340, overflowY: 'auto', paddingRight: 4 }}>
            {required.map((entry) => {
              const hit = present.find((p) => p.doc_type === entry.doc_type);
              return (
                <div key={entry.doc_type} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 12px', marginBottom: 6,
                  border: '1px solid var(--border)', borderRadius: 8,
                  background: hit ? 'rgba(16,185,129,0.04)' : 'transparent',
                }}>
                  {hit
                    ? <Check size={14} style={{ color: 'var(--success)', flexShrink: 0 }} />
                    : <AlertTriangle size={14} style={{ color: 'var(--warn, #f59e0b)', flexShrink: 0 }} />}
                  <span style={{
                    fontSize: 12.5, fontWeight: 600,
                    color: hit ? 'var(--text)' : 'var(--text-dim)',
                  }}>
                    {entry.label}
                  </span>
                  <span style={{ fontSize: 10.5, color: 'var(--muted)' }}>{entry.doc_type}</span>
                  <span style={{
                    marginLeft: 'auto', fontSize: 10.5, fontWeight: 600,
                    color: hit ? 'var(--success)' : 'var(--warn, #f59e0b)',
                  }}>
                    {hit ? `${hit.document_ids.length} uploaded` : 'not uploaded'}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Documents the classifier could not place — the likeliest explanation
              for a missing type, so it is called out rather than buried. */}
          {unclassified.length > 0 && (
            <div style={{
              display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 12,
              padding: '10px 12px', borderRadius: 8,
              border: '1px solid var(--border)', background: 'var(--card-alt)',
            }}>
              <HelpCircle size={13} style={{ color: 'var(--muted)', marginTop: 2, flexShrink: 0 }} />
              <div style={{ fontSize: 11.5, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                {unclassified.length} document(s) in this batch came back as <em>others</em> or
                unclassified. One of them may be a missing type the classifier did not recognise —
                check the classification types in Settings if that looks wrong.
              </div>
            </div>
          )}

          {pendingCount > 0 && (
            <div style={{ marginTop: 10, fontSize: 11.5, color: 'var(--muted)' }}>
              {pendingCount} document(s) added since the check are still classifying.
            </div>
          )}

          {/* Reviewer note */}
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note — why the missing documents do not apply"
            style={{
              width: '100%', marginTop: 14, fontSize: 12, padding: '8px 10px',
              borderRadius: 8, border: '1px solid var(--border)',
              background: 'var(--card)', color: 'var(--text)',
            }}
          />

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16, flexWrap: 'wrap' }}>
            <input
              ref={fileInput}
              type="file"
              multiple
              onChange={addMissingFiles}
              style={{ display: 'none' }}
            />
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => fileInput.current?.click()}
              disabled={uploading || submitting}
            >
              <UploadCloud size={13} /> {uploading ? 'Uploading…' : 'Add missing documents'}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading || submitting}>
              <RefreshCw size={13} /> Re-check
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => decide(false)} disabled={submitting}>
              <X size={13} /> Reject as incomplete
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => decide(true)} disabled={submitting}>
              <Check size={13} /> {submitting ? 'Submitting…' : 'Continue anyway'}
            </button>
          </div>

          <div style={{
            display: 'flex', gap: 6, alignItems: 'flex-start',
            marginTop: 12, fontSize: 11, color: 'var(--muted)', lineHeight: 1.5,
          }}>
            <FileText size={11} style={{ marginTop: 2, flexShrink: 0 }} />
            Documents added here join this same batch. They are classified first, so use
            <strong style={{ margin: '0 3px', color: 'var(--text-dim)' }}>Re-check</strong>
            once they finish before deciding.
          </div>
        </div>
      )}
    </Modal>
  );
}
