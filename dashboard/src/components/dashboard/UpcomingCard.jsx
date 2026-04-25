'use client';

import Link from 'next/link';

/**
 * Upcoming card — surfaces the next few non-regular-school-day entries
 * from the teacher's `school_calendar` overlay (holidays, early-release,
 * testing windows, custom notes).
 *
 * The widget was originally hardcoded to "Progress Reports Due" /
 * "Math Bee Competition" / "Student Awards Ceremony" so demo screenshots
 * would look busy. Those were misleading on real accounts, so they're
 * replaced by the teacher's own calendar data. Empty state points to the
 * calendar page where they can add items.
 */
export default function UpcomingCard({ data }) {
  const items = data?.upcoming || [];

  return (
    <div
      className="rounded-card p-6 h-full"
      style={{
        background: 'var(--warm-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 4px 16px var(--shadow)',
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
          Upcoming
        </h2>
        <Link
          href="/calendar"
          className="text-[13px] font-semibold"
          style={{ color: 'var(--coral)' }}
        >
          View calendar &rsaquo;
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="py-4 text-[13px]" style={{ color: 'var(--text-light)' }}>
          Nothing on the next two weeks.{' '}
          <Link href="/calendar" className="font-semibold" style={{ color: 'var(--coral)' }}>
            Add a note →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((event, i) => (
            <div
              key={event.date || i}
              className="flex items-center gap-3 p-2.5 rounded-xl"
              style={{ background: 'var(--cream)' }}
            >
              <div
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ background: event.color }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-bold truncate" style={{ color: 'var(--text-dark)' }}>
                  {event.title}
                </div>
                <div className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                  {event.date_label || event.date}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
