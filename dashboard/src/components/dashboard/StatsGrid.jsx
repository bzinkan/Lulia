'use client';

import Image from 'next/image';
import { useCounterAnimation } from '@/lib/useCounterAnimation';

const stats = [
  { label: 'Total Students', value: 127, change: '+8 this month', icon: 'star.png', accent: 'var(--coral)' },
  { label: 'Assignments',    value: 48,  change: '+12 graded today', icon: 'document.png', accent: 'var(--sage)' },
  { label: 'Average Mastery', value: 82, change: '+6% this week', icon: 'mastery.png', accent: 'var(--mustard)', suffix: '%' },
  { label: 'Hours Saved',    value: 34,  change: 'This semester', icon: 'clock.png', accent: 'var(--teal)' },
];

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
      {/* Accent bar on hover (via CSS) */}
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
      <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--text-light)' }}>
        <span
          className="w-[6px] h-[6px] rounded-full"
          style={{ background: stat.accent }}
        />
        {stat.change}
      </div>
    </div>
  );
}

export default function StatsGrid() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
      {stats.map(stat => (
        <StatCard key={stat.label} stat={stat} />
      ))}
    </div>
  );
}
