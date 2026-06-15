import { createContext, useContext, useReducer, useCallback } from 'react';

// ─── Initial State ───────────────────────────────
function lsGet(key, fallback) {
  try { const v = localStorage.getItem(key); return v !== null ? JSON.parse(v) : fallback; } catch { return fallback; }
}

const initialState = {
  documents: [],        // [{id, filename, status, doc_type, workflow_run_id}]
  activeDocId: null,    // currently viewed document id
  pollingIds: new Set(),
  toasts: [],
  loading: false,
  confidenceMode: (() => {
    try {
      return localStorage.getItem('idp-confidence-mode') || 'word';
    } catch {
      return 'word';
    }
  })(),
  // Confidence thresholds (user-configurable)
  fieldHighlightThreshold: lsGet('idp-field-highlight-threshold', 95), // % below which a field value is amber-highlighted
  autoApproveThreshold:    lsGet('idp-auto-approve-threshold', 80),    // % below which a doc enters review queue
  confHighThreshold:       lsGet('idp-conf-high-threshold', 90),       // % for green badge
  confMedThreshold:        lsGet('idp-conf-med-threshold', 70),        // % for amber badge (below → red)
};

// ─── Reducer ─────────────────────────────────────
function reducer(state, action) {
  switch (action.type) {
    case 'SET_DOCUMENTS':
      return { ...state, documents: action.payload };

    case 'ADD_DOCUMENT':
      return {
        ...state,
        documents: [action.payload, ...state.documents.filter((d) => d.id !== action.payload.id)],
      };

    case 'UPDATE_DOCUMENT': {
      const docs = state.documents.map((d) =>
        d.id === action.payload.id ? { ...d, ...action.payload } : d
      );
      // If the doc wasn't in the list yet, add it
      if (!docs.find((d) => d.id === action.payload.id)) {
        docs.unshift(action.payload);
      }
      return { ...state, documents: docs };
    }

    case 'REMOVE_DOCUMENT':
      return { ...state, documents: state.documents.filter((d) => d.id !== action.payload) };

    case 'SET_ACTIVE_DOC':
      return { ...state, activeDocId: action.payload };

    case 'ADD_POLLING':
      return { ...state, pollingIds: new Set([...state.pollingIds, action.payload]) };

    case 'REMOVE_POLLING': {
      const next = new Set(state.pollingIds);
      next.delete(action.payload);
      return { ...state, pollingIds: next };
    }

    case 'ADD_TOAST':
      return { ...state, toasts: [...state.toasts, action.payload] };

    case 'REMOVE_TOAST':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.payload) };

    case 'SET_LOADING':
      return { ...state, loading: action.payload };

    case 'SET_CONFIDENCE_MODE':
      try { localStorage.setItem('idp-confidence-mode', action.payload); } catch {}
      return { ...state, confidenceMode: action.payload };

    case 'SET_FIELD_HIGHLIGHT_THRESHOLD':
      try { localStorage.setItem('idp-field-highlight-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, fieldHighlightThreshold: action.payload };

    case 'SET_AUTO_APPROVE_THRESHOLD':
      try { localStorage.setItem('idp-auto-approve-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, autoApproveThreshold: action.payload };

    case 'SET_CONF_HIGH_THRESHOLD':
      try { localStorage.setItem('idp-conf-high-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, confHighThreshold: action.payload };

    case 'SET_CONF_MED_THRESHOLD':
      try { localStorage.setItem('idp-conf-med-threshold', JSON.stringify(action.payload)); } catch {}
      return { ...state, confMedThreshold: action.payload };

    default:
      return state;
  }
}

// ─── Context ─────────────────────────────────────
const AppContext = createContext(null);

let toastId = 0;

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const setDocuments = useCallback((docs) => dispatch({ type: 'SET_DOCUMENTS', payload: docs }), []);
  const addDocument  = useCallback((doc)  => dispatch({ type: 'ADD_DOCUMENT',  payload: doc }),  []);
  const updateDocument = useCallback((doc) => dispatch({ type: 'UPDATE_DOCUMENT', payload: doc }), []);
  const removeDocument = useCallback((id)  => dispatch({ type: 'REMOVE_DOCUMENT', payload: id }),  []);
  const setActiveDoc = useCallback((id)   => dispatch({ type: 'SET_ACTIVE_DOC', payload: id }),   []);
  const addPolling   = useCallback((id)   => dispatch({ type: 'ADD_POLLING',   payload: id }),    []);
  const removePolling= useCallback((id)   => dispatch({ type: 'REMOVE_POLLING',payload: id }),    []);
  const setConfidenceMode           = useCallback((mode) => dispatch({ type: 'SET_CONFIDENCE_MODE',           payload: mode }), []);
  const setFieldHighlightThreshold  = useCallback((v)    => dispatch({ type: 'SET_FIELD_HIGHLIGHT_THRESHOLD', payload: v }),    []);
  const setAutoApproveThreshold     = useCallback((v)    => dispatch({ type: 'SET_AUTO_APPROVE_THRESHOLD',    payload: v }),    []);
  const setConfHighThreshold        = useCallback((v)    => dispatch({ type: 'SET_CONF_HIGH_THRESHOLD',       payload: v }),    []);
  const setConfMedThreshold         = useCallback((v)    => dispatch({ type: 'SET_CONF_MED_THRESHOLD',        payload: v }),    []);

  const toast = useCallback((msg, type = 'info', duration = 4000) => {
    const id = ++toastId;
    dispatch({ type: 'ADD_TOAST', payload: { id, msg, type } });
    setTimeout(() => dispatch({ type: 'REMOVE_TOAST', payload: id }), duration);
  }, []);

  const dismissToast = useCallback((id) => dispatch({ type: 'REMOVE_TOAST', payload: id }), []);

  // ─── Derived helpers ────────────────────────────
  const pendingDocs = state.documents.filter((d) => ['pending','processing','classifying','extracting','validating'].includes(d.status));
  const reviewDocs  = state.documents.filter((d) => d.status === 'awaiting_review');
  const completedDocs = state.documents.filter((d) => d.status === 'completed');

  return (
    <AppContext.Provider value={{
      ...state,
      pendingDocs,
      reviewDocs,
      completedDocs,
      setDocuments,
      addDocument,
      updateDocument,
      removeDocument,
      setActiveDoc,
      addPolling,
      removePolling,
      toast,
      dismissToast,
      setConfidenceMode,
      setFieldHighlightThreshold,
      setAutoApproveThreshold,
      setConfHighThreshold,
      setConfMedThreshold,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be inside AppProvider');
  return ctx;
}
