import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Send, Plus, RefreshCw, MessageSquare, FileText, Loader2, AlertTriangle, Library,
  PanelLeft, X, Trash2,
} from 'lucide-react';
import { useApp } from '../store/AppStore';
import {
  sendChatMessage, getChatLibrary, syncChatLibrary, deleteChatConversation,
} from '../api/client';

// Each session's conversation lives with Mistral; the browser keeps the list of
// sessions — id, title and a copy of the transcript — so an older chat can be
// reopened and continued. Per browser: the app has no user accounts, so a
// server-side list would show every visitor everyone else's chats.
const SESSIONS_KEY = 'document-chat-sessions';
const LEGACY_KEY = 'document-chat';   // single-transcript format of the first release
const PANELS_KEY = 'document-chat-panels';

const SUGGESTIONS = [
  'Summarise the documents uploaded most recently',
  'Which documents mention a policy number?',
  'List every applicant with their date of birth',
  'Which invoice has the highest total amount?',
];

const LIBRARY_BADGE = {
  indexed:    { cls: 'badge-green', label: 'Indexed' },
  processing: { cls: 'badge-blue',  label: 'Indexing' },
  queued:     { cls: 'badge-gray',  label: 'Queued' },
  failed:     { cls: 'badge-red',   label: 'Failed' },
};

const newId = () => `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

function titleFrom(question) {
  const oneLine = question.replace(/\s+/g, ' ').trim();
  return oneLine.length > 60 ? `${oneLine.slice(0, 57)}…` : oneLine;
}

function loadStore() {
  try {
    const saved = JSON.parse(localStorage.getItem(SESSIONS_KEY) || 'null');
    if (saved && Array.isArray(saved.sessions)) return saved;

    // Carry the first release's single transcript over as one session.
    const legacy = JSON.parse(localStorage.getItem(LEGACY_KEY) || 'null');
    if (legacy?.messages?.length) {
      const now = Date.now();
      const firstQuestion = legacy.messages.find((m) => m.role === 'user')?.content || 'Earlier chat';
      const session = {
        id: newId(), conversationId: legacy.conversationId, title: titleFrom(firstQuestion),
        createdAt: now, updatedAt: now, messages: legacy.messages,
      };
      localStorage.removeItem(LEGACY_KEY);
      return { activeId: session.id, sessions: [session] };
    }
  } catch { /* storage blocked or corrupt — start fresh */ }
  return { activeId: null, sessions: [] };
}

function loadPanels() {
  const wide = typeof window !== 'undefined' && window.innerWidth > 1000;
  try {
    const saved = JSON.parse(localStorage.getItem(PANELS_KEY) || 'null');
    // On a narrow screen panels overlay the chat, so they always start closed.
    if (saved && wide) return saved;
  } catch { /* fall through to defaults */ }
  return { history: wide, library: wide };
}

function groupByDate(sessions) {
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  const day = 86_400_000;
  const groups = [
    { label: 'Today', items: [] },
    { label: 'Yesterday', items: [] },
    { label: 'Previous 7 days', items: [] },
    { label: 'Older', items: [] },
  ];
  for (const s of sessions) {
    const t = s.updatedAt;
    const idx = t >= startOfToday ? 0 : t >= startOfToday - day ? 1 : t >= startOfToday - 7 * day ? 2 : 3;
    groups[idx].items.push(s);
  }
  return groups.filter((g) => g.items.length);
}

// ─── Minimal markdown: paragraphs, lists, tables, **bold**, `code`, [n] ──────

function renderInline(text, onCite) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g).map((part, i) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (/^`[^`]+`$/.test(part)) return <code key={i} className="chat-code">{part.slice(1, -1)}</code>;
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite) {
      return (
        <button key={i} type="button" className="chat-cite" onClick={() => onCite(Number(cite[1]))}>
          {cite[1]}
        </button>
      );
    }
    return part;
  });
}

function splitRow(line) {
  return line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
}

function Markdown({ text, onCite }) {
  const blocks = text.split(/\n\s*\n/).filter((b) => b.trim());
  return blocks.map((block, bi) => {
    const lines = block.split('\n').filter((l) => l.trim());

    if (lines.every((l) => l.trim().startsWith('|'))) {
      const rows = lines.filter((l) => !/^\|?[\s:|-]+\|?$/.test(l.trim())).map(splitRow);
      const [head, ...body] = rows;
      return (
        <div key={bi} className="chat-table-wrap">
          <table className="chat-table">
            <thead><tr>{head.map((c, i) => <th key={i}>{renderInline(c, onCite)}</th>)}</tr></thead>
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri}>{r.map((c, ci) => <td key={ci}>{renderInline(c, onCite)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (lines.every((l) => /^\s*([-*]|\d+\.)\s+/.test(l))) {
      const ordered = /^\s*\d+\./.test(lines[0]);
      const items = lines.map((l, li) => (
        <li key={li}>{renderInline(l.replace(/^\s*([-*]|\d+\.)\s+/, ''), onCite)}</li>
      ));
      return ordered ? <ol key={bi}>{items}</ol> : <ul key={bi}>{items}</ul>;
    }

    return (
      <p key={bi}>
        {lines.map((l, li) => (
          <span key={li}>
            {li > 0 && <br />}
            {/^#{1,6}\s/.test(l)
              ? <strong>{renderInline(l.replace(/^#{1,6}\s+/, ''), onCite)}</strong>
              : renderInline(l, onCite)}
          </span>
        ))}
      </p>
    );
  });
}

// ─── Page ───────────────────────────────────────────────────────────────────

export function Chat() {
  const { toast } = useApp();
  const navigate = useNavigate();

  const [store, setStore] = useState(loadStore);
  const [panels, setPanels] = useState(loadPanels);
  const [input, setInput] = useState('');
  // The session a question is in flight for. Only one at a time, but the user
  // may switch sessions meanwhile — the answer still lands where it was asked.
  const [sendingId, setSendingId] = useState(null);
  const [library, setLibrary] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const endRef = useRef(null);
  const inputRef = useRef(null);

  const active = store.sessions.find((s) => s.id === store.activeId) || null;
  const messages = active?.messages || [];
  const sending = sendingId !== null;
  const showThinking = sending && sendingId === store.activeId;

  const sortedSessions = useMemo(
    () => [...store.sessions].sort((a, b) => b.updatedAt - a.updatedAt),
    [store.sessions],
  );
  const sessionGroups = useMemo(() => groupByDate(sortedSessions), [sortedSessions]);

  useEffect(() => {
    try { localStorage.setItem(SESSIONS_KEY, JSON.stringify(store)); }
    catch { /* storage blocked — chats still work for this visit */ }
  }, [store]);

  useEffect(() => {
    try { localStorage.setItem(PANELS_KEY, JSON.stringify(panels)); }
    catch { /* not worth surfacing */ }
  }, [panels]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, showThinking, store.activeId]);

  const refreshLibrary = useCallback(async () => {
    try {
      setLibrary(await getChatLibrary());
    } catch (e) {
      setLibrary((prev) => prev ?? { total: 0, counts: {}, documents: [], error: e.message });
    }
  }, []);

  // Indexing finishes on Mistral's side after the upload; keep polling while
  // anything is still on its way so the panel turns green without a reload.
  const stillIndexing = !!library?.documents?.some((d) => d.status === 'queued' || d.status === 'processing');
  useEffect(() => {
    refreshLibrary();
  }, [refreshLibrary]);
  useEffect(() => {
    if (!stillIndexing) return undefined;
    const t = setInterval(refreshLibrary, 10_000);
    return () => clearInterval(t);
  }, [stillIndexing, refreshLibrary]);

  const updateSession = (id, fn) =>
    setStore((s) => ({ ...s, sessions: s.sessions.map((x) => (x.id === id ? fn(x) : x)) }));

  const togglePanel = (name) => setPanels((p) => ({ ...p, [name]: !p[name] }));

  const closeOverlayPanels = () => {
    if (window.innerWidth <= 1000) setPanels({ history: false, library: false });
  };

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || sending) return;

    const now = Date.now();
    const userMsg = { role: 'user', content: question };
    let sessionId = active?.id;
    const conversationId = active?.conversationId || null;

    if (!sessionId) {
      // A session is only created once something is asked, so "New chat"
      // never leaves empty sessions behind in the list.
      sessionId = newId();
      const session = {
        id: sessionId, conversationId: null, title: titleFrom(question),
        createdAt: now, updatedAt: now, messages: [userMsg],
      };
      setStore((s) => ({ activeId: sessionId, sessions: [session, ...s.sessions] }));
    } else {
      updateSession(sessionId, (s) => ({ ...s, updatedAt: now, messages: [...s.messages, userMsg] }));
    }

    setInput('');
    setSendingId(sessionId);
    try {
      const res = await sendChatMessage(question, conversationId);
      updateSession(sessionId, (s) => ({
        ...s,
        conversationId: res.conversation_id,
        updatedAt: Date.now(),
        messages: [...s.messages, { role: 'assistant', content: res.answer, sources: res.sources || [] }],
      }));
    } catch (e) {
      updateSession(sessionId, (s) => ({
        ...s,
        updatedAt: Date.now(),
        messages: [...s.messages, { role: 'assistant', content: e.message, error: true }],
      }));
    } finally {
      setSendingId(null);
      inputRef.current?.focus();
    }
  };

  const newChat = () => {
    setStore((s) => ({ ...s, activeId: null }));
    setInput('');
    closeOverlayPanels();
    inputRef.current?.focus();
  };

  const openSession = (id) => {
    setStore((s) => ({ ...s, activeId: id }));
    closeOverlayPanels();
  };

  const deleteSession = async (session) => {
    if (!window.confirm(`Delete "${session.title}"? This cannot be undone.`)) return;
    setStore((s) => ({
      activeId: s.activeId === session.id ? null : s.activeId,
      sessions: s.sessions.filter((x) => x.id !== session.id),
    }));
    if (session.conversationId) {
      try {
        await deleteChatConversation(session.conversationId);
      } catch (e) {
        toast(`Chat removed here, but Mistral kept its copy: ${e.message}`, 'warn');
        return;
      }
    }
    toast('Chat deleted', 'success');
  };

  const syncAll = async () => {
    setSyncing(true);
    try {
      const { queued } = await syncChatLibrary();
      toast(queued ? `Pushing ${queued} document${queued > 1 ? 's' : ''} to the library` : 'Every document is already in the library', 'success');
      await refreshLibrary();
    } catch (e) {
      toast(`Sync failed: ${e.message}`, 'error');
    } finally {
      setSyncing(false);
    }
  };

  const openDocument = (documentId) => {
    if (documentId) navigate('/extraction', { state: { docId: documentId } });
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const counts = library?.counts || {};
  const indexed = counts.indexed || 0;

  const layoutClass = [
    'page', 'chat-layout',
    panels.history ? 'has-history' : '',
    panels.library ? 'has-library' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={layoutClass}>
      {/* ── Chat sessions ── */}
      {panels.history && (
        <aside className="card chat-side chat-history" aria-label="Chat history">
          <div className="chat-side-header">
            <div className="card-title">Chats</div>
            <button className="btn btn-ghost btn-sm btn-icon" onClick={() => togglePanel('history')} title="Close chats" aria-label="Close chats">
              <X size={13} />
            </button>
          </div>

          <button className="btn btn-primary btn-sm chat-new" onClick={newChat}>
            <Plus size={14} /> New chat
          </button>

          <div className="chat-side-list">
            {sortedSessions.length === 0 && (
              <div className="chat-side-note">Your chats will appear here. Start one by asking a question.</div>
            )}
            {sessionGroups.map((group) => (
              <div key={group.label} className="chat-session-group">
                <div className="chat-session-group-label">{group.label}</div>
                {group.items.map((s) => (
                  <div key={s.id} className={`chat-session${s.id === store.activeId ? ' active' : ''}`}>
                    <button type="button" className="chat-session-open" onClick={() => openSession(s.id)} title={s.title}>
                      {sendingId === s.id
                        ? <Loader2 size={13} className="spin chat-session-icon" />
                        : <MessageSquare size={13} className="chat-session-icon" />}
                      <span className="chat-session-title">{s.title}</span>
                    </button>
                    <button
                      type="button"
                      className="chat-session-delete"
                      onClick={() => deleteSession(s)}
                      disabled={sendingId === s.id}
                      title="Delete chat"
                      aria-label={`Delete chat ${s.title}`}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </aside>
      )}

      {/* ── Conversation ── */}
      <section className="card chat-panel">
        <div className="chat-header">
          <div className="chat-header-main">
            <button
              className={`btn btn-ghost btn-sm btn-icon${panels.history ? ' active' : ''}`}
              onClick={() => togglePanel('history')}
              title={panels.history ? 'Hide chats' : 'Show chats'}
              aria-label={panels.history ? 'Hide chats' : 'Show chats'}
              aria-pressed={panels.history}
            >
              <PanelLeft size={14} />
            </button>
            <div className="chat-header-text">
              <div className="card-title chat-header-title">{active?.title || 'New chat'}</div>
              <div className="card-sub">
                Answers come from {indexed} indexed document{indexed === 1 ? '' : 's'}, with citations
              </div>
            </div>
          </div>
          <div className="chat-header-actions">
            {!panels.history && (
              <button className="btn btn-ghost btn-sm" onClick={newChat} disabled={!active}>
                <Plus size={14} /> New chat
              </button>
            )}
            <button
              className={`btn btn-ghost btn-sm${panels.library ? ' active' : ''}`}
              onClick={() => togglePanel('library')}
              title={panels.library ? 'Hide library' : 'Show library'}
              aria-pressed={panels.library}
            >
              <Library size={14} /> Library
              <span className="chat-count">{indexed}</span>
            </button>
          </div>
        </div>

        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-icon"><MessageSquare size={22} /></div>
              <div className="empty-title">Ask anything about your documents</div>
              <div className="empty-sub">
                Every upload is indexed into a Mistral document library. Questions are answered from it, and each answer cites the documents it used.
              </div>
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="chat-suggestion" onClick={() => send(s)} disabled={sending}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`chat-msg chat-msg-${m.role}${m.error ? ' chat-msg-error' : ''}`}>
              <div className="chat-bubble">
                {m.role === 'user' && m.content}
                {m.role === 'assistant' && m.error && (
                  <span className="chat-error"><AlertTriangle size={14} /> {m.content}</span>
                )}
                {m.role === 'assistant' && !m.error && (
                  <Markdown
                    text={m.content}
                    onCite={(n) => openDocument(m.sources?.find((s) => s.index === n)?.document_id)}
                  />
                )}
              </div>
              {m.sources?.length > 0 && (
                <div className="chat-sources">
                  {m.sources.map((s) => (
                    <button
                      key={s.index}
                      type="button"
                      className="chat-source"
                      onClick={() => openDocument(s.document_id)}
                      disabled={!s.document_id}
                      title={s.document_id ? 'Open document' : s.title}
                    >
                      <span className="chat-source-index">{s.index}</span>
                      <FileText size={12} />
                      <span className="chat-source-title">{s.title}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}

          {showThinking && (
            <div className="chat-msg chat-msg-assistant">
              <div className="chat-bubble chat-thinking">
                <Loader2 size={14} className="spin" /> Searching documents…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="chat-composer">
          <textarea
            ref={inputRef}
            className="chat-input"
            rows={1}
            placeholder={sending && !showThinking ? 'Waiting for an answer in another chat…' : 'Ask about a policy, an applicant, an amount…'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={sending}
            aria-label="Message"
          />
          <button className="btn btn-primary" onClick={() => send()} disabled={sending || !input.trim()} aria-label="Send">
            {sending ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
          </button>
        </div>
      </section>

      {/* ── Library ── */}
      {panels.library && (
        <aside className="card chat-side chat-library" aria-label="Document library">
          <div className="chat-side-header">
            <div>
              <div className="card-title">Library</div>
              <div className="card-sub">
                {library ? `${indexed} of ${library.total} searchable` : 'Loading…'}
              </div>
            </div>
            <div className="chat-header-actions">
              <button className="btn btn-ghost btn-sm btn-icon" onClick={refreshLibrary} title="Refresh" aria-label="Refresh library">
                <RefreshCw size={13} />
              </button>
              <button className="btn btn-ghost btn-sm btn-icon" onClick={() => togglePanel('library')} title="Close library" aria-label="Close library">
                <X size={13} />
              </button>
            </div>
          </div>

          <button className="btn btn-ghost btn-sm chat-sync" onClick={syncAll} disabled={syncing}>
            {syncing ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
            Push missing documents
          </button>

          {library?.error && <div className="chat-side-note">{library.error}</div>}

          <div className="chat-side-list">
            {library?.documents?.length === 0 && (
              <div className="chat-side-note">
                Nothing indexed yet. New uploads are pushed automatically — use “Push missing documents” for files uploaded earlier.
              </div>
            )}
            {library?.documents?.map((d) => {
              const badge = LIBRARY_BADGE[d.status] || LIBRARY_BADGE.queued;
              return (
                <div key={d.document_id} className="chat-library-item" title={d.error || d.filename}>
                  <FileText size={13} className="chat-library-icon" />
                  <button type="button" className="chat-library-name" onClick={() => openDocument(d.document_id)}>
                    {d.filename}
                  </button>
                  <span className={`badge ${badge.cls}`}>{badge.label}</span>
                </div>
              );
            })}
          </div>
        </aside>
      )}

      {/* Narrow screens: panels float over the chat; tapping outside closes them. */}
      {(panels.history || panels.library) && (
        <div className="chat-scrim" onClick={() => setPanels({ history: false, library: false })} />
      )}
    </div>
  );
}
