'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Per-subject mastery rollup across all of the teacher's classes.
 *
 * The backend returns `{name, pct, color}` for each distinct subject the
 * teacher teaches. We keep the CSS-variable string on `color` so the bar
 * theme stays consistent if the palette changes globally.
 *
 * Cold accounts: if there are no students or no submissions yet, we show a
 * helpful empty state instead of an awkward list of 0% bars.
 */
export default function ClassMastery({ data }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);
  const subjects = data?.mastery?.subjects || [];

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); observer.disconnect(); } },
      { threshold: 0.3 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // A subject row with pct === 0 is almost always "no data yet" rather than
  // "students answered zero correctly" — filter those out so the widget
  // doesn't visually imply catastrophe on a fresh account.
  const visibleSubjects = subjects.filter(s => (s.pct ?? 0) > 0);

  return (
    <div
      ref={ref}
      className="rounded-card p-6"
      style={{
        background: 'var(--warm-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 4px 16px var(--shadow)',
      }}
    >
      <h2 className="font-serif text-[20px] mb-4" style={{ color: 'var(--text-dark)' }}>
        Class Mastery
      </h2>
      {visibleSubjects.length === 0 ? (
        <div className="py-6 text-[13px]" style={{ color: 'var(--text-light)' }}>
          Grade some assignments to see mastery trends by subject.
        </div>
      ) : (
        <div className="space-y-4">
          {visibleSubjects.map((s, i) => (
            <div key={s.name}>
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                  {s.name}
                </span>
                <span className="text-[13px] font-bold" style={{ color: s.color }}>
                  {Math.round(s.pct)}%
                </span>
              </div>
              <div
                className="h-2.5 rounded-full overflow-hidden"
                style={{ background: 'var(--border)' }}
              >
                <div
                  className="mastery-fill h-full rounded-full"
                  style={{
                    width: visible ? `${Math.min(100, Math.max(0, s.pct))}%` : '0%',
                    background: s.color,
                    transitionDelay: `${i * 150}ms`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
