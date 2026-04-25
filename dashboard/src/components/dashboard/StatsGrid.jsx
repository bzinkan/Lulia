'use client';

import Image from 'next/image';
import { useCounterAnimation } from '@/lib/useCounterAnimation';

/**
 * Compose the 4 stat cards from the dashboard payload.
 *
 * Why we build the array inside the component (instead of static top-level):
 * the numbers come from props, and we want the counter animation to animate
 * from 0 → `value` only once per render. A `useCounterAnimation` keyed on a
 * live prop would also let us gracefully swap in real numbers as the
 * network request completes.
 *
 * `change` is intentionally short and decorative — if the backend doesn't
 * have a delta we hide the sub-line rather than showing a misleading one.
 */
function buildStats(data) {
  const stats = data?.stats || {};
  const mastery = data?.mastery || {};
  return [
    {
      label: 'Total Students',
      value: stats.total_students ?? 0,
      change: '',  // no reliable "new this month" signal yet
      icon: 'star.png',
      accent: 'var(--coral)',
    },
    {
      label: 'Assignments',
      value: stats.assignments_week ?? 0,
      change: 'This week',
      icon: 'document.png',
      accent: 'var(--sage)',
    },
    {
      label: 'Average Mastery',
      value: Math.round(stats.class_average_pct ?? 0),
      change: formatDelta(mastery.week_delta_pct),
      icon: 'mastery.png',
      accent: 'var(--mustard)',
      suffix: '%',
    },
    {
      label: 'Credits Left',
      value: stats.credits_remaining ?? 0,
      change: '',
      icon: 'clock.png',
      accent: 'var(--teal)',
    },
  ];
}

function formatDelta(delta) {
  if (delta === undefined || delta === null) return '';
  if (delta === 0) return 'Flat vs last week';
  const sign = delta > 0 ? '+' : '';
  return `${sign}${delta}% this week`;
}

function StatCard({ stat }) {
  const { ref, displayValue } = useCounterAnimation(stat.value, 1400, stat.suffix || '');

  return (
    <div
      ref={ref}
      className="hover-lift rounded-stat p-5"
      style={{
        background: 'var(--warm-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 4px 16px var(--shadow)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        className="absolute top-0 left-0 right-0 h-[3px] opacity-0 transition-opacity"
        style={{ background: stat.accent }}
      />
      <div className="flex items-start justify-between mb-3">
        <Image
          src={`/icons/${stat.icon}`}
          alt=""
          width={36}
          height={36}
          style={{ opacity: 0.85 }}
        />
      </div>
      <div className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-light)' }}>
        {stat.label}
      </div>
      <div className="font-serif text-[28px] leading-none mb-1" style={{ color: 'var(--text-dark)' }}>
        {displayValue}
      </div>
      <div
        className="flex items-center gap-1.5 text-[11px] min-h-[16px]"
        style={{ color: 'var(--text-light)' }}
      >
        {stat.change && (
          <>
            <span
              className="w-[6px] h-[6px] rounded-full"
              style={{ background: stat.accent }}
            />
            {stat.change}
          </>
        )}
      </div>
    </div>
  );
}

export default function StatsGrid({ data }) {
  const stats = buildStats(data);
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
      {stats.map(stat => (
        <StatCard key={stat.label} stat={stat} />
      ))}
    </div>
  );
}
