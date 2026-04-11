'use client';

import { useEffect, useRef, useState } from 'react';

// TODO: fetch from API
const data = [
  { day: 'Mon', value: 65 },
  { day: 'Tue', value: 45 },
  { day: 'Wed', value: 80 },
  { day: 'Thu', value: 55 },
  { day: 'Fri', value: 70 },
];

const barColors = [
  'var(--coral)',
  'var(--sage)',
  'var(--mustard)',
  'var(--teal)',
  'var(--dusty-pink)',
];

export default function WeeklyActivityChart() {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);
  const maxValue = Math.max(...data.map(d => d.value));

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
        Weekly Activity
      </h2>
      <div className="flex items-end gap-3 h-[140px]">
        {data.map((d, i) => (
          <div key={d.day} className="flex-1 flex flex-col items-center gap-2">
            <div className="w-full flex items-end justify-center" style={{ height: 110 }}>
              <div
                className="chart-bar w-full max-w-[36px] rounded-t-lg"
                style={{
                  height: visible ? `${(d.value / maxValue) * 100}%` : '0%',
                  background: barColors[i],
                  transitionDelay: `${i * 120}ms`,
                }}
              />
            </div>
            <span className="text-[11px] font-semibold" style={{ color: 'var(--text-light)' }}>
              {d.day}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
