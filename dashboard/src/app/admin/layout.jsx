'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Shield, BarChart3, Users, Activity, AlertTriangle, DollarSign, Heart, FileText, Flag, MessageSquare, ToggleRight, Megaphone } from 'lucide-react';

const adminNav = [
  { label: 'Overview', icon: BarChart3, href: '/admin' },
  { label: 'Teachers', icon: Users, href: '/admin/teachers' },
  { label: 'Billing', icon: DollarSign, href: '/admin/billing' },
  { label: 'Moderation', icon: Flag, href: '/admin/moderation' },
  { label: 'Support', icon: MessageSquare, href: '/admin/support' },
  { label: 'Features', icon: ToggleRight, href: '/admin/features' },
  { label: 'Announcements', icon: Megaphone, href: '/admin/announcements' },
  { label: 'Activity', icon: Activity, href: '/admin/activity' },
  { label: 'Errors', icon: AlertTriangle, href: '/admin/errors' },
  { label: 'Costs', icon: DollarSign, href: '/admin/costs' },
  { label: 'Health', icon: Heart, href: '/admin/health' },
  { label: 'Audit', icon: FileText, href: '/admin/audit' },
];

export default function AdminLayout({ children }) {
  const pathname = usePathname();

  return (
    <div style={{ background: '#EDE0D4', minHeight: '100vh' }}>
      {/* Admin top bar */}
      <div className="sticky top-0 z-50 flex items-center justify-between px-6 py-3" style={{ background: '#1C1917' }}>
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-orange-400" />
          <span className="text-white font-semibold">Lulia Admin</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-orange-500 text-white font-bold uppercase">Super Admin</span>
        </div>
        <Link href="/" className="text-xs text-gray-400 hover:text-white transition-colors">
          Exit to Dashboard ›
        </Link>
      </div>

      {/* Admin nav */}
      <div className="flex gap-2 px-6 py-2 overflow-x-auto" style={{ background: '#292524' }}>
        {adminNav.map(item => {
          const Icon = item.icon;
          const active = item.href === '/admin' ? pathname === '/admin' : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
                active ? 'bg-orange-500 text-white' : 'text-gray-400 hover:text-white hover:bg-white/10'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {item.label}
            </Link>
          );
        })}
      </div>

      {/* Content */}
      <div className="p-6 max-w-7xl mx-auto">
        {children}
      </div>
    </div>
  );
}
