'use client';

import { useEffect } from 'react';

/**
 * Custom hook that adds scroll-triggered reveal animations.
 *
 * Elements with the `.reveal` class start invisible (opacity: 0, translateY: 30px).
 * When they scroll into view, the `.visible` class is added with an 80ms stagger
 * per element, creating a cascading entrance effect.
 *
 * Usage:
 *   function MyPage() {
 *     useScrollReveal();
 *     return (
 *       <div className="reveal">First item</div>
 *       <div className="reveal">Second item (80ms later)</div>
 *     );
 *   }
 */
export function useScrollReveal() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // Find all .reveal siblings in the same parent for staggering
            const parent = entry.target.parentElement;
            if (!parent) {
              entry.target.classList.add('visible');
              return;
            }

            const siblings = parent.querySelectorAll('.reveal');
            const index = Array.from(siblings).indexOf(entry.target);
            const delay = index >= 0 ? index * 80 : 0;

            setTimeout(() => {
              entry.target.classList.add('visible');
            }, delay);

            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );

    // Small delay to ensure DOM is ready after React render
    const timer = setTimeout(() => {
      document.querySelectorAll('.reveal').forEach((el) => {
        observer.observe(el);
      });
    }, 100);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, []);
}
