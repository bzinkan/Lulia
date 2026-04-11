'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for animated stat counters.
 *
 * Counts from 0 to the target value over `duration` ms with cubic ease-out.
 * Animation only triggers when the element is visible (via IntersectionObserver).
 *
 * Usage:
 *   function StatCard({ value }) {
 *     const { ref, displayValue } = useCounterAnimation(value);
 *     return <div ref={ref}>{displayValue}</div>;
 *   }
 *
 * @param {number} target - The target number to count to
 * @param {number} duration - Animation duration in ms (default: 1400)
 * @param {string} suffix - Optional suffix like "%" or "h"
 * @returns {{ ref: React.RefObject, displayValue: string }}
 */
export function useCounterAnimation(target, duration = 1400, suffix = '') {
  const [displayValue, setDisplayValue] = useState(`0${suffix}`);
  const ref = useRef(null);
  const hasAnimated = useRef(false);

  const animate = useCallback(() => {
    if (hasAnimated.current) return;
    hasAnimated.current = true;

    const startTime = performance.now();
    const targetNum = Number(target) || 0;

    function tick(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Cubic ease-out: 1 - (1 - p)^3
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(targetNum * eased);

      setDisplayValue(`${current.toLocaleString()}${suffix}`);

      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    }

    requestAnimationFrame(tick);
  }, [target, duration, suffix]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          animate();
          observer.disconnect();
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [animate]);

  return { ref, displayValue };
}
