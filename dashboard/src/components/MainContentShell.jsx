'use client';
import { usePathname } from 'next/navigation';

/**
 * Wraps <main> and toggles the sidebar-offset margin based on route.
 * Pages like /join (student-facing) and /play/{pin} (teacher game control)
 * render full-bleed without the 240px sidebar gutter.
 */
export default function MainContentShell({ children }) {
  const pathname = usePathname() || '';
  const isStandalone = pathname === '/join'
    || pathname.startsWith('/join/')
    || pathname.startsWith('/play/');

  return (
    <main
      className={
        isStandalone
          ? 'min-h-screen relative z-10'
          : 'md:ml-[240px] pt-14 md:pt-0 min-h-screen relative z-10'
      }
    >
      {children}
    </main>
  );
}
