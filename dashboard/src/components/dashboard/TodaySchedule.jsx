'use client';

import Image from 'next/image';
import Link from 'next/link';

/**
 * "Today's Schedule" reads the approved/generating lesson_plans whose weekly
 * window covers today's date, extracts the `daily_plans` entry matching
 * today's weekday, and surfaces each work order as a schedule row.
 *
 * Empty-state handling: a teacher who has no active plan for today — either
 * because they haven't approved one or because their week starts tomorrow —
 * sees the "no lessons today" empty state with a quick link to the planner.
 * This is by far the most common cold-start shape, so it needs to look
 * intentional instead of broken.
 */

const badgeStyles = {
  live: { background: 'rgba(216,108,82,0.12)', color: 'var(--coral)', label: 'LIVE' },
  prep: { background: 'rgba(107,160,138,0.12)', color: 'var(--sage)', label: 'PREP' },
  done: { background: 'rgba(218,176,78,0.12)', color: 'var(--mustard)', label: 'DONE' },
};

// Subject → 3D Pillow icon name. Keeps the lookup in one place so a new
// subject can pick up a reasonable default without a follow-up PR.
const ICON_BY_SUBJECT = {
  Mathematics: 'calculator.png',
  Math: 'calculator.png',
  Science: 'microscope.png',
  ELA: 'pen.png',
  'English Language Arts': 'pen.png',
  Reading: 'pen.png',
  Writing: 'pen.png',
  'Social Studies': 'calendar.png',
  History: 'calendar.png',
  Art: 'palette.png',
  Music: 'palette.png',
};

function iconFor(subject) {
  return ICON_BY_SUBJECT[subject] || 'document.png';
}

export default function TodaySchedule({ data, loading }) {
  const items = data?.today?.schedule || [];

  return (
    <div
      className="rounded-card p-6"
      style={{
        background: 'var(--warm-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 4px 16px var(--shadow)',
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
          Today&apos;s Schedule
        </h2>
        <Link
          href="/planner"
          className="text-[13px] font-semibold"
          style={{ color: 'var(--coral)' }}
        >
          View full planner &rsaquo;
        </Link>
      </div>

      {loading && !data ? (
        <div className="space-y-2">
          {[0, 1, 2].map(i => (
            <div
              key={i}
              className="h-[56px] rounded-xl animate-pulse"
              style={{ background: 'var(--border)', opacity: 0.4 }}
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="py-6 text-center">
          <div className="text-[13px]" style={{ color: 'var(--text-mid)' }}>
            No lessons planned for today.
          </div>
          <Link
            href="/planner"
            className="inline-block mt-2 text-[13px] font-semibold"
            style={{ color: 'var(--coral)' }}
          >
            Open the planner →
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item, i) => {
            const badge = badgeStyles[item.status] || badgeStyles.prep;
            return (
              <div
                key={item.work_order_id || i}
                className="schedule-hover flex items-center gap-3 p-3 rounded-xl cursor-pointer"
              >
                <Image
                  src={`/icons/${iconFor(item.subject)}`}
                  alt=""
                  width={32}
                  height={32}
                  style={{ opacity: 0.8 }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-bold" style={{ color: 'var(--text-dark)' }}>
                    {item.subject || '—'}
                  </div>
                  <div className="text-[12px] truncate" style={{ color: 'var(--text-mid)' }}>
                    {item.topic || '—'}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  {item.time && (
                    <div className="text-[12px] font-semibold" style={{ color: 'var(--text-mid)' }}>
                      {item.time}
                    </div>
                  )}
                  <span
                    className="inline-block text-[9px] font-bold px-2 py-0.5 rounded-full mt-0.5"
                    style={badge}
                  >
                    {badge.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
