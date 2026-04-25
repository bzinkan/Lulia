'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Weekly Activity bar chart — 7 days ending today, one bar per day.
 *
 * Backend returns an array of {day_label, date, value}. We pick the bar
 * color by index so the palette cycles consistently; this also means a
 * day's bar won't flicker color as the `value` changes on refresh.
 *
 * When the chart is empty (fresh teacher, no activity yet) we still render
 * the seven day labels with zero-height bars so the widget has a consistent
 * footprint in the layout.
 */

const barColors = [
  'var(--coral)',
  'var(--sage)',
  'var(--mustard)',
  'var(--teal)',
  'var(--dusty-pink)',
];

export default function WeeklyActivityChart({ data }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);
  const points = data?.weekly_activity || [];

  // Fall back to 1 so the first real bar still gets a visible height instead
  // of dividing by zero and collapsing.
  const maxValue = Math.max(1, ...points.map(p => p.value || 0));

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
        {points.map((d, i) => (
          <div key={d.date || d.day_label} className="flex-1 flex flex-col items-center gap-2">
            <div className="w-full flex items-end justify-center" style={{ height: 110 }}>
              <div
                className="chart-bar w-full max-w-[36px] rounded-t-lg"
                style={{
                  height: visible ? `${((d.value || 0) / maxValue) * 100}%` : '0%',
                  background: barColors[i % barColors.length],
                  transitionDelay: `${i * 120}ms`,
                  minHeight: d.value > 0 ? 4 : 0,  // show even tiny values
                }}
                title={`${d.value || 0} event${d.value === 1 ? '' : 's'}`}
              />
            </div>
            <span className="text-[11px] font-semibold" style={{ color: 'var(--text-light)' }}>
              {d.day_label}
            </span>
          </div>
        ))}
        {points.length === 0 && (
          // Keep the footprint even when the backend returned nothing.
          <div className="flex-1 text-center text-[12px]" style={{ color: 'var(--text-light)' }}>
            No activity yet this week
          </div>
        )}
      </div>
    </div>
  );
}
