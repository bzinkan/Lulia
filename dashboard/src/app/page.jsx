'use client';

import { useScrollReveal } from '@/lib/useScrollReveal';
import { useDashboardHome } from '@/lib/useDashboardHome';
import HeroBanner from '@/components/dashboard/HeroBanner';
import StatsGrid from '@/components/dashboard/StatsGrid';
import TodaySchedule from '@/components/dashboard/TodaySchedule';
import QuickActions from '@/components/dashboard/QuickActions';
import WeeklyActivityChart from '@/components/dashboard/WeeklyActivityChart';
import ClassMastery from '@/components/dashboard/ClassMastery';
import RecentActivity from '@/components/dashboard/RecentActivity';
import UpcomingCard from '@/components/dashboard/UpcomingCard';

export default function DashboardPage() {
  useScrollReveal();
  const { data, loading } = useDashboardHome();

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto">
      {/* Hero banner */}
      <div className="reveal">
        <HeroBanner data={data} loading={loading} />
      </div>

      {/* Stats grid */}
      <div className="reveal">
        <StatsGrid data={data} loading={loading} />
      </div>

      {/* Main content: 2-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
        {/* Left column */}
        <div className="space-y-6">
          <div className="reveal">
            <TodaySchedule data={data} loading={loading} />
          </div>
          <div className="reveal">
            <QuickActions />
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <div className="reveal">
            <WeeklyActivityChart data={data} loading={loading} />
          </div>
        </div>
      </div>

      {/* Bottom grid: 3-column layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="reveal">
          <ClassMastery data={data} loading={loading} />
        </div>
        <div className="reveal">
          <RecentActivity data={data} loading={loading} />
        </div>
        <div className="reveal md:col-span-2 lg:col-span-1">
          <UpcomingCard data={data} loading={loading} />
        </div>
      </div>
    </div>
  );
}
