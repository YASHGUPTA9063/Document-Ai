import { createContext, useContext, useReducer, useCallback } from 'react';

// ─── Initial State ───────────────────────────────
const initialState = {
  documents: [],        // [{id, filename, status, doc_type, workflow_run_id}]
  activeDocId: null,    // currently viewed document id
  pollingIds: new Set(),
  toasts: [],
  loading: false,
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
