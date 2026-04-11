'use client';

import Image from 'next/image';

// TODO: fetch from /api/v1/planner/today or similar
const scheduleItems = [
  { subject: 'Mathematics', topic: 'Fractions — hands-on activity', time: '8:30 AM', status: 'live', icon: 'calculator.png' },
  { subject: 'Science', topic: 'Force & Motion lab', time: '10:15 AM', status: 'prep', icon: 'microscope.png' },
  { subject: 'ELA', topic: 'Narrative Writing — final drafts', time: '1:00 PM', status: 'prep', icon: 'pen.png' },
  { subject: 'Art', topic: 'Perspective — urban landscape project', time: '2:30 PM', status: 'done', icon: 'palette.png' },
];

const badgeStyles = {
  live: { background: 'rgba(216,108,82,0.12)', color: 'var(--coral)', label: 'LIVE' },
  prep: { background: 'rgba(107,160,138,0.12)', color: 'var(--sage)', label: 'PREP' },
  done: { background: 'rgba(218,176,78,0.12)', color: 'var(--mustard)', label: 'DONE' },
};

export default function TodaySchedule() {
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
        <button className="text-[13px] font-semibold" style={{ color: 'var(--coral)', background: 'none', border: 'none', cursor: 'pointer' }}>
          View full planner &rsaquo;
        </button>
      </div>

      <div className="space-y-2">
        {scheduleItems.map((item, i) => {
          const badge = badgeStyles[item.status];
          return (
            <div
              key={i}
              className="schedule-hover flex items-center gap-3 p-3 rounded-xl cursor-pointer"
            >
              <Image
                src={`/icons/${item.icon}`}
                alt=""
                width={32}
                height={32}
                style={{ opacity: 0.8 }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-bold" style={{ color: 'var(--text-dark)' }}>
                  {item.subject}
                </div>
                <div className="text-[12px] truncate" style={{ color: 'var(--text-mid)' }}>
                  {item.topic}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-[12px] font-semibold" style={{ color: 'var(--text-mid)' }}>
                  {item.time}
                </div>
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
    </div>
  );
}
