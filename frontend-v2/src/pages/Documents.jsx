import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, RefreshCw, ChevronLeft, ChevronRight, Folder, FileText, AlertCircle, ChevronDown, ChevronUp, Scissors, CornerDownRight } from 'lucide-react';
import { deleteDocument, listDocuments } from '../api/client';
import { useApp } from '../store/AppStore';
import { StatusBadge } from '../components/ui/StatusBadge';
import { SplitReviewModal } from '../components/ui/SplitReviewModal';

const STATUS_FILTERS = ['all', 'pending', 'processing', 'awaiting_review', 'completed', 'rejected', 'failed', 'error'];

const STATUS_FILTER_LABELS = {
  all:             'All',
  pending:         'Pending',
  processing:      'Ingestion',
  awaiting_review: 'Human Review',
  completed:       'Completed',
  rejected:        'Rejected',
  failed:          'Failed',
  error:           'Error',
};

/** Renders a rejection/failure reason with expand/collapse if the text is long */
function ExpandableReason({ reason }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = reason.length > 80;
  return (
    <div style={{
      marginTop: 5, padding: '5px 8px',
      background: 'var(--danger-dim, rgba(239,68,68,0.08))',
      border: '1px solid var(--danger-border, rgba(239,68,68,0.2))',
      borderRadius: 6, maxWidth: 340,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 5 }}>
        <AlertCircle size={12} style={{ color: 'var(--danger)', marginTop: 2, flexShrink: 0 }} />
        <span style={{ fontSize: 11, color: 'var(--danger)', lineHeight: 1.4, flex: 1 }}>
          {isLong && !expanded ? reason.slice(0, 80) + '…' : reason}
        </span>
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            marginTop: 4, marginLeft: 17,
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--danger)', fontSize: 10, display: 'flex', alignItems: 'center', gap: 2,
            opacity: 0.75, padding: 0,
          }}
        >
          {expanded ? <><ChevronUp size={10} /> Show less</> : <><ChevronDown size={10} /> Show more</>}
        </button>
      )}
    </div>
  );
}


export function Documents() {
  const { documents, setDocuments, removeDocument, toast } = useApp();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [collapsed, setCollapsed] = useState({});   // parent id -> children hidden
  const [reviewingSplit, setReviewingSplit] = useState(null);
  const navigate = useNavigate();
  const LIMIT = 20;

  const load = async (p = 1) => {
    setLoading(true);
    try {
      const docs = await listDocuments(p, LIMIT);
      setDocuments(docs);
    } catch (err) {
      toast('Error loading documents: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const filtered = filter === 'all' ? documents : documents.filter((d) => d.status === filter);

  // Nest split children under the packet they came from. A child whose parent is
  // not on this page (pagination, or a filter) still renders on its own so it can
  // never silently disappear from the list.
  const rows = (() => {
    const byParent = {};
    filtered.forEach((d) => {
      if (d.parent_document_id) {
        (byParent[d.parent_document_id] ||= []).push(d);
      }
    });
    const visibleIds = new Set(filtered.map((d) => d.id));
    const ordered = [];
    filtered.forEach((d) => {
      if (d.parent_document_id && visibleIds.has(d.parent_document_id)) return;  // rendered under its parent
      ordered.push({ doc: d, depth: 0 });
      if (!collapsed[d.id]) {
        (byParent[d.id] || []).forEach((child) => ordered.push({ doc: child, depth: 1 }));
      }
    });
    return ordered;
  })();

  const toggleCollapsed = (id) => setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));

  const handleDelete = async (doc) => {
    const warning = doc.is_split_parent && doc.child_count
      ? `Delete "${doc.filename}" and the ${doc.child_count} document(s) split out of it?`
      : `Delete "${doc.filename}"?`;
    if (!confirm(warning)) return;
    setDeleting(doc.id);
    try {
      await deleteDocument(doc.id);
      removeDocument(doc.id);
      toast(`"${doc.filename}" deleted.`, 'info');
    } catch (err) {
      toast('Delete failed: ' + err.message, 'error');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="page">
      {reviewingSplit && (
        <SplitReviewModal
          documentId={reviewingSplit}
          open
          toast={toast}
          onClose={() => setReviewingSplit(null)}
          onDecided={() => load(page)}
        />
      )}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">All Documents</div>
            <div className="card-sub">{filtered.length} document{filtered.length !== 1 ? 's' : ''}</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => load(page)} disabled={loading}>
              <RefreshCw size={12} className={loading ? 'spin' : ''} /> Refresh
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => navigate('/upload')}>
              + Upload
            </button>
          </div>
        </div>

        {/* Filter Bar */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              className={`btn btn-ghost btn-sm`}
              style={filter === s ? { borderColor: 'var(--accent)', color: 'var(--accent)', background: 'var(--accent-dim)' } : {}}
              onClick={() => setFilter(s)}
            >
              {STATUS_FILTER_LABELS[s] || s}
              {s !== 'all' && (
                <span style={{ marginLeft: 4, opacity: 0.6 }}>
                  ({documents.filter((d) => d.status === s).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">
            <Folder className="empty-icon" size={36} />
            <div className="empty-title">No documents</div>
            <div className="empty-sub">
              {filter !== 'all' ? `No documents with status "${STATUS_FILTER_LABELS[filter] || filter}".` : 'Upload a document to get started.'}
            </div>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>ID</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ doc, depth }) => (
                  <tr key={doc.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: depth * 22 }}>
                        {depth > 0 && <CornerDownRight size={12} style={{ color: 'var(--muted)', flexShrink: 0 }} />}

                        {doc.is_split_parent ? (
                          <button
                            onClick={() => toggleCollapsed(doc.id)}
                            title={collapsed[doc.id] ? 'Show contained documents' : 'Hide contained documents'}
                            style={{ all: 'unset', cursor: 'pointer', display: 'inline-flex', color: 'var(--muted)' }}
                          >
                            {collapsed[doc.id] ? <ChevronRight size={13} /> : <ChevronDown size={13} />}
                          </button>
                        ) : (
                          <FileText size={14} className="doc-icon" style={{ flexShrink: 0 }} />
                        )}

                        <span
                          className="doc-filename-link"
                          onClick={() => navigate('/extraction', { state: { docId: doc.id } })}
                        >
                          {doc.filename}
                        </span>

                        {doc.is_split_parent && (
                          <span className="badge badge-purple" style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                            <Scissors size={10} /> {doc.child_count} inside
                          </span>
                        )}
                        {doc.page_range && (
                          <span className="badge badge-gray">p{doc.page_range}</span>
                        )}
                      </div>
                    </td>
                    <td>
                      {doc.doc_type
                        ? <span className="badge badge-cyan">{doc.doc_type}</span>
                        : null}
                    </td>
                    <td style={{ whiteSpace: 'normal', overflow: 'visible' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                        <StatusBadge status={doc.status} />
                        {doc.status === 'awaiting_split_review' && (
                          <button
                            className="btn btn-primary btn-sm"
                            style={{ padding: '3px 8px', fontSize: 11 }}
                            onClick={() => setReviewingSplit(doc.id)}
                          >
                            <Scissors size={11} /> Review split
                          </button>
                        )}
                        {['rejected', 'failed', 'error'].includes(doc.status) && doc.message && (
                          <ExpandableReason reason={doc.message} />
                        )}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--muted)' }}>
                        {doc.id.slice(0, 8)}…
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        style={{ padding: '4px 8px' }}
                        onClick={() => handleDelete(doc)}
                        disabled={deleting === doc.id}
                      >
                        {deleting === doc.id
                          ? <span className="spin" style={{ width: 12, height: 12, border: '2px solid rgba(239,68,68,0.3)', borderTopColor: 'var(--danger)', borderRadius: '50%', display: 'inline-block' }} />
                          : <Trash2 size={12} />
                        }
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, fontSize: 12, color: 'var(--muted)' }}>
          <span>Page {page}</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1 || loading}>
              <ChevronLeft size={13} />
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setPage((p) => p + 1)} disabled={documents.length < LIMIT || loading}>
              <ChevronRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
