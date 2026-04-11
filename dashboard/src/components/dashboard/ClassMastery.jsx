'use client';

import { useEffect, useRef, useState } from 'react';

// TODO: fetch from /api/v1/analytics/mastery-summary
const subjects = [
  { name: 'Mathematics', pct: 85, color: 'var(--coral)' },
  { name: 'Science',     pct: 78, color: 'var(--sage)' },
  { name: 'ELA',         pct: 82, color: 'var(--mustard)' },
  { name: 'Social Studies', pct: 71, color: 'var(--teal)' },
  { name: 'Art',         pct: 93, color: 'var(--dusty-pink)' },
];

export default function ClassMastery() {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);

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
      <div className="space-y-4">
        {subjects.map((s, i) => (
          <div key={s.name}>
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                {s.name}
              </span>
              <span className="text-[13px] font-bold" style={{ color: s.color }}>
                {s.pct}%
              </span>
            </div>
            <div
              className="h-2.5 rounded-full overflow-hidden"
              style={{ background: 'var(--border)' }}
            >
              <div
                className="mastery-fill h-full rounded-full"
                style={{
                  width: visible ? `${s.pct}%` : '0%',
                  background: s.color,
                  transitionDelay: `${i * 150}ms`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
