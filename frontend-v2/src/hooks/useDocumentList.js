import { useCallback, useState } from 'react';
import { listDocuments } from '../api/client';
import { useApp } from '../store/AppStore';

/**
 * Hook to fetch the document list from the backend and sync to AppStore.
 */
export function useDocumentList() {
  const { setDocuments, toast } = useApp();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async (page = 1, limit = 100) => {
    // Guard against React synthetic event objects passed via onClick={refresh}
    const pageNum = typeof page === 'number' ? page : 1;
    const limitNum = typeof limit === 'number' ? limit : 100;
    setLoading(true);
    setError(null);
    try {
      const docs = await listDocuments(pageNum, limitNum);
      setDocuments(docs);
    } catch (err) {
      setError(err.message);
      toast('Failed to load documents: ' + err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [setDocuments, toast]);

  return { refresh, loading, error };
}
