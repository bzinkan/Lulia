'use client';

import Image from 'next/image';

/**
 * Recent teacher-scoped activity feed.
 *
 * The backend derives this by unioning the newest rows from several domain
 * tables (assignments, lesson_plans, etc.) with a `kind` discriminator and a
 * precomputed `time_ago` string + icon + accent pair, so the frontend
 * doesn't need to know about the domain schema.
 *
 * Rendering is deliberately a flat, vertical list — no grouping, no
 * pagination — because the server-side LIMIT already keeps this tight, and
 * teachers skim it, not browse it.
 */
export default function RecentActivity({ data }) {
  const activities = data?.recent_activity || [];

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
      {activities.length === 0 ? (
        <div className="py-4 text-[13px]" style={{ color: 'var(--text-light)' }}>
          Nothing here yet. Generate your first assignment to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {activities.map((a, i) => (
            <div key={a.ref_id || i} className="flex items-start gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                // Light tint derived from the accent var; the appended `15`
                // is an 8-bit alpha byte (~8% opacity) so each badge gets a
                // consistent but subtle chip-like background.
                style={{ background: `color-mix(in srgb, ${a.accent} 10%, transparent)` }}
              >
                <Image src={`/icons/${a.icon || 'document.png'}`} alt="" width={20} height={20} style={{ opacity: 0.8 }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                  {a.text}
                </div>
                <div className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                  {a.time_ago}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
