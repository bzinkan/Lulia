'use client';

import { useScrollReveal } from '@/lib/useScrollReveal';
import HeroBanner from '@/components/dashboard/HeroBanner';
import StatsGrid from '@/components/dashboard/StatsGrid';
import TodaySchedule from '@/components/dashboard/TodaySchedule';
import QuickActions from '@/components/dashboard/QuickActions';
import WeeklyActivityChart from '@/components/dashboard/WeeklyActivityChart';
import ClassMastery from '@/components/dashboard/ClassMastery';
import RecentActivity from '@/components/dashboard/RecentActivity';

export default function DashboardPage() {
  useScrollReveal();

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto">
      {/* Hero banner */}
      <div className="reveal">
        <HeroBanner />
      </div>

      {/* Stats grid */}
      <div className="reveal">
        <StatsGrid />
      </div>

      {/* Main content: 2-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
        {/* Left column */}
        <div className="space-y-6">
          <div className="reveal">
            <TodaySchedule />
          </div>
          <div className="reveal">
            <QuickActions />
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <div className="reveal">
            <WeeklyActivityChart />
          </div>
        </div>
      </div>

      {/* Bottom grid: 3-column layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="reveal">
          <ClassMastery />
        </div>
        <div className="reveal">
          <RecentActivity />
        </div>
        <div className="reveal md:col-span-2 lg:col-span-1">
          {/* Upcoming events */}
          <div
            className="rounded-card p-6 h-full"
            style={{
              background: 'var(--warm-card)',
              border: '1px solid var(--border)',
              boxShadow: '0 4px 16px var(--shadow)',
            }}
          >
            <h2 className="font-serif text-[20px] mb-4" style={{ color: 'var(--text-dark)' }}>
              Upcoming
            </h2>
            <div className="space-y-3">
              {[
                { title: 'Progress Reports Due', date: 'Fri, Oct 11', color: 'var(--coral)' },
                { title: 'Math Bee Competition', date: 'Mon, Oct 14', color: 'var(--sage)' },
                { title: 'Student Awards Ceremony', date: 'Wed, Oct 16', color: 'var(--mustard)' },
              ].map((event, i) => (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl" style={{ background: 'var(--cream)' }}>
                  <div
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ background: event.color }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
                      {event.title}
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                      {event.date}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
