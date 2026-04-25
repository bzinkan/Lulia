'use client';

/**
 * TanStack Query provider wrapper.
 *
 * Why this lives in its own file:
 *   The root layout is a server component (no 'use client' banner); wiring
 *   QueryClientProvider directly in there would force the whole tree to
 *   become client-side. Extracting the provider keeps `layout.jsx`
 *   server-side and limits the client boundary to this component.
 *
 * Defaults we've picked:
 *   - staleTime 30s — dashboard data isn't real-time, and a teacher who
 *     navigates away and back shouldn't trigger a refetch on every mount.
 *   - refetchOnWindowFocus false — teachers regularly alt-tab to Chrome
 *     for research; we don't want a stampede of refetches on window-focus.
 *   - retry 1 — the server is on the same VPC/cluster, not a flaky third
 *     party; one retry is plenty.
 *
 * This is the narrow rollout footprint: only the dashboard home and any
 * future pages that opt in actually use Query. Existing pages with their
 * own fetch hooks keep working untouched.
 */
import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export default function QueryProvider({ children }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
