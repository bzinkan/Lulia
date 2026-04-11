'use client';

import Image from 'next/image';

// TODO: fetch from /api/v1/activity/recent
const activities = [
  { text: 'Fractions worksheet generated', time: '2 min ago', icon: 'document.png', accent: 'var(--sage)' },
  { text: 'Science lab graded — 24 students', time: '15 min ago', icon: 'check.png', accent: 'var(--coral)' },
  { text: 'Weekly plan approved for next week', time: '1 hr ago', icon: 'calendar.png', accent: 'var(--teal)' },
  { text: 'New video: Rock Cycle Intro', time: '2 hrs ago', icon: 'clipboard.png', accent: 'var(--mustard)' },
  { text: 'Interactive quiz shared to class', time: '3 hrs ago', icon: 'gamepad.png', accent: 'var(--dusty-pink)' },
];

export default function RecentActivity() {
  return (
    <div
      className="rounded-card p-6"
      style={{
        background: 'var(--warm-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 4px 16px var(--shadow)',
      }}
    >
      <h2 className="font-serif text-[20px] mb-4" style={{ color: 'var(--text-dark)' }}>
        Recent Activity
      </h2>
      <div className="space-y-3">
        {activities.map((a, i) => (
          <div key={i} className="flex items-start gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{ background: `${a.accent}15` }}
            >
              <Image src={`/icons/${a.icon}`} alt="" width={20} height={20} style={{ opacity: 0.8 }} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                {a.text}
              </div>
              <div className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                {a.time}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
