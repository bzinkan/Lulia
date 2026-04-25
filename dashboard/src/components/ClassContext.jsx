'use client';
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '@/lib/api';

// Teacher identity: read from env var so dev/staging/prod can differ.
// When real auth arrives, this will be replaced by a value derived from the
// session cookie / JWT claim. Consumers should prefer `useClassContext().teacherId`
// rather than importing this constant directly.
const TEACHER_ID =
  process.env.NEXT_PUBLIC_DEV_TEACHER_ID ||
  '00000000-0000-0000-0000-000000000001';
const STORAGE_KEY = 'lulia_active_class_id';

const ClassContext = createContext(null);

export function useClassContext() {
  const ctx = useContext(ClassContext);
  if (!ctx) throw new Error('useClassContext must be used within ClassProvider');
  return ctx;
}

export function ClassProvider({ children }) {
  const [classes, setClasses] = useState([]);
  const [activeClassId, setActiveClassIdState] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshClasses = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/v1/classes/?teacher_id=${TEACHER_ID}`);
      const active = (res.classes || []).filter(c => !c.archived_at);
      setClasses(active);
      return active;
    } catch (e) {
      console.error('Failed to load classes:', e);
      return [];
    }
  }, []);

  // Set active class and persist to localStorage
  const setActiveClassId = useCallback((id) => {
    setActiveClassIdState(id);
    if (typeof window !== 'undefined') {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Load classes on mount, restore active from localStorage
  useEffect(() => {
    (async () => {
      const active = await refreshClasses();
      const stored = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
      if (stored && active.some(c => c.class_id === stored)) {
        setActiveClassIdState(stored);
      } else if (active.length > 0) {
        setActiveClassId(active[0].class_id);
      }
      setLoading(false);
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const activeClass = classes.find(c => c.class_id === activeClassId) || null;

  // CRUD operations
  const createClass = useCallback(async (payload) => {
    const res = await apiFetch('/api/v1/classes/', {
      method: 'POST',
      body: JSON.stringify({ ...payload, teacher_id: TEACHER_ID }),
    });
    const updated = await refreshClasses();
    if (res.class_id) setActiveClassId(res.class_id);
    return res;
  }, [refreshClasses, setActiveClassId]);

  const updateClass = useCallback(async (classId, payload) => {
    const res = await apiFetch(`/api/v1/classes/${classId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    await refreshClasses();
    return res;
  }, [refreshClasses]);

  const archiveClass = useCallback(async (classId) => {
    await apiFetch(`/api/v1/classes/${classId}/archive`, { method: 'POST' });
    const updated = await refreshClasses();
    // If we archived the active class, switch to first available
    if (classId === activeClassId && updated.length > 0) {
      setActiveClassId(updated[0].class_id);
    } else if (updated.length === 0) {
      setActiveClassId(null);
    }
  }, [activeClassId, refreshClasses, setActiveClassId]);

  const unarchiveClass = useCallback(async (classId) => {
    await apiFetch(`/api/v1/classes/${classId}/unarchive`, { method: 'POST' });
    await refreshClasses();
  }, [refreshClasses]);

  return (
    <ClassContext.Provider value={{
      classes,
      activeClassId,
      activeClass,
      setActiveClassId,
      refreshClasses,
      createClass,
      updateClass,
      archiveClass,
      unarchiveClass,
      loading,
      teacherId: TEACHER_ID,
    }}>
      {children}
    </ClassContext.Provider>
  );
}
