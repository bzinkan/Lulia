'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  Home, Calendar, PlusCircle, FileText, Gamepad2, Joystick, Video,
  Palette, Upload, Shield, CheckSquare, BookOpen, Users, CreditCard,
  Settings, Zap, Menu, X, Presentation, ClipboardList,
} from 'lucide-react';

const navGroups = [
  {
    label: null, // No label for first group
    items: [
      { label: 'Dashboard', icon: Home, href: '/' },
      { label: 'Weekly Planner', icon: Calendar, href: '/planner' },
      { label: 'New Assignment', icon: PlusCircle, href: '/assignments/new' },
      { label: 'Assignments', icon: FileText, href: '/assignments' },
    ],
  },
  {
    label: 'Generate',
    items: [
      { label: 'Interactive Activities', icon: Gamepad2, href: '/interactive' },
      { label: 'Live Games', icon: Joystick, href: '/games' },
      { label: 'Videos', icon: Video, href: '/videos' },
      { label: 'Google Slides', icon: Presentation, href: '/slides' },
      { label: 'Google Forms', icon: ClipboardList, href: '/forms' },
    ],
  },
  {
    label: 'Tools',
    items: [
      { label: 'Content Library', icon: Upload, href: '/library' },
      { label: 'Accommodations', icon: Shield, href: '/accommodations' },
      { label: 'Grading', icon: CheckSquare, href: '/grading' },
      { label: 'Analytics', icon: BookOpen, href: '/analytics' },
    ],
  },
  {
    label: 'Account',
    items: [
      { label: 'Community', icon: Users, href: '/community' },
      { label: 'Billing', icon: CreditCard, href: '/billing' },
      { label: 'Settings', icon: Settings, href: '/settings' },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [credits, setCredits] = useState(null);

  useEffect(() => {
    fetch((process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/v1/billing/me')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setCredits({ balance: d.credit_balance, monthly: d.credits_per_month }); })
      .catch(() => {});
  }, []);

  // Don't show sidebar on admin or join pages
  if (pathname?.startsWith('/admin') || pathname === '/join') return null;

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-white border-b flex items-center justify-between px-4 z-30" style={{ borderColor: '#E7E5E4' }}>
        <span className="text-lg font-semibold" style={{ color: '#F97316', fontFamily: "'DM Serif Display', serif" }}>Lulia</span>
        <button onClick={() => setOpen(!open)} className="p-2 text-gray-600">
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile overlay */}
      {open && <div className="md:hidden fixed inset-0 bg-black/30 z-30" onClick={() => setOpen(false)} />}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-white z-40
        transform transition-transform duration-200
        md:translate-x-0
        ${open ? 'translate-x-0' : '-translate-x-full'}
      `} style={{ borderRight: '1px solid #E7E5E4' }}>

        {/* Logo */}
        <div className="h-16 flex items-center px-6" style={{ borderBottom: '1px solid #E7E5E4' }}>
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#F97316' }}>
              <BookOpen className="w-4 h-4 text-white" />
            </div>
            <span className="text-xl font-semibold" style={{ color: '#1C1917', fontFamily: "'DM Serif Display', serif" }}>Lulia</span>
          </Link>
        </div>

        {/* Nav groups */}
        <nav className="p-3 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 64px - 80px)' }}>
          {navGroups.map((group, gi) => (
            <div key={gi}>
              {group.label && (
                <div className="mt-3 mb-1 px-3">
                  <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#A8A29E' }}>
                    {group.label}
                  </span>
                </div>
              )}
              {gi > 0 && !group.label && <div style={{ borderTop: '0.5px solid #E7E5E4', margin: '6px 12px' }} />}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive = item.href === '/'
                    ? pathname === '/'
                    : pathname?.startsWith(item.href);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setOpen(false)}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                      style={isActive
                        ? { background: '#FFF7ED', color: '#78350F', borderRight: '2px solid #F97316' }
                        : { color: '#78716C' }
                      }
                      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#FEF9F2'; }}
                      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                    >
                      <Icon className="w-[18px] h-[18px]" style={{ color: isActive ? '#F97316' : '#A8A29E' }} />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Credit meter */}
        <div className="absolute bottom-3 left-3 right-3">
          <Link href="/billing" className="block px-3 py-2 rounded-lg transition-colors" style={{ background: '#FFF7ED', border: '1px solid #FDBA74' }}
            onMouseEnter={e => e.currentTarget.style.background = '#FEF3C7'}
            onMouseLeave={e => e.currentTarget.style.background = '#FFF7ED'}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4" style={{ color: '#F97316' }} />
                <span className="text-sm font-semibold" style={{ color: '#78350F' }}>
                  {credits ? credits.balance : '—'} credits
                </span>
              </div>
              {credits && credits.monthly > 0 && (
                <span style={{ fontSize: 10, color: '#A8A29E' }}>/ {credits.monthly}</span>
              )}
            </div>
            {credits && credits.monthly > 0 && (
              <div className="mt-1.5 h-1.5 rounded-full overflow-hidden" style={{ background: '#FED7AA' }}>
                <div className="h-full rounded-full" style={{
                  width: `${Math.min((credits.balance / credits.monthly) * 100, 100)}%`,
                  background: '#F97316',
                }} />
              </div>
            )}
          </Link>
        </div>
      </aside>
    </>
  );
}
