'use client';

/**
 * useDashboardHome — single fetch for the whole dashboard home page.
 *
 * Backed by TanStack Query. The widget tree passes `data` + `loading` down
 * to each component, so migrating to Query doesn't change any consumer.
 *
 * Query key:
 *   ['dashboard.home', teacherId, activeClassId]
 *
 * We include the activeClassId because scope changes with it (today/stats
 * narrow to that class). Switching classes triggers a fresh fetch rather
 * than surfacing stale data from the previous tab.
 */
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './api';
import { useClassContext } from '@/components/ClassContext';

export function useDashboardHome() {
  const { teacherId, activeClassId, loading: classesLoading } = useClassContext();

  const query = useQuery({
    // `enabled` guards the initial render: until we've loaded the class
    // list, we don't know what to fetch. The ClassContext provider sets
    // loading=false once /classes has returned, at which point this fires.
    enabled: !!teacherId && !classesLoading,
    queryKey: ['dashboard.home', teacherId, activeClassId || null],
    queryFn: async () => {
      const params = new URLSearchParams({ teacher_id: teacherId });
      if (activeClassId) params.set('class_id', activeClassId);
      return apiFetch(`/api/v1/dashboard/home?${params.toString()}`);
    },
  });

  return {
    data: query.data ?? null,
    loading: query.isPending || classesLoading,
    error: query.error ?? null,
    refresh: query.refetch,
  };
}
