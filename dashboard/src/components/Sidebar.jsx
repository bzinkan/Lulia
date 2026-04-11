'use client';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { Menu, X } from 'lucide-react';

const navItems = [
  { label: 'Dashboard',   icon: 'dashboard.png',  href: '/' },
  { label: 'Curriculum',  icon: 'book.png',       href: '/curriculum' },
  { label: 'Planner',     icon: 'calendar.png',   href: '/planner' },
  { label: 'Assignments', icon: 'document.png',   href: '/assignments' },
  { label: 'Videos',      icon: 'video-camera.png', href: '/videos' },
  { label: 'Live Games',  icon: 'gamepad.png',    href: '/games' },
  { label: 'Analytics',   icon: 'chart.png',      href: '/analytics' },
  { label: 'Grades',      icon: 'check.png',      href: '/grading' },
  { label: 'Settings',    icon: 'settings.png',   href: '/settings' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Don't show sidebar on admin or join pages
  if (pathname?.startsWith('/admin') || pathname === '/join') return null;

  return (
    <>
      {/* Mobile top bar */}
      <div
        className="md:hidden fixed top-0 left-0 right-0 h-14 flex items-center justify-between px-4 z-30"
        style={{ background: 'var(--warm-card)', borderBottom: '1px solid var(--border)' }}
      >
        <Link href="/" className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded-[10px] flex items-center justify-center font-serif font-bold text-white text-sm"
            style={{ background: 'linear-gradient(135deg, var(--coral), var(--coral-light))' }}
          >
            L
          </div>
          <span className="font-serif text-lg" style={{ color: 'var(--text-dark)' }}>
            Lulia
          </span>
        </Link>
        <button onClick={() => setOpen(!open)} className="p-2" style={{ color: 'var(--text-mid)' }}>
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile overlay */}
      {open && <div className="md:hidden fixed inset-0 bg-black/30 z-30" onClick={() => setOpen(false)} />}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full w-[240px] z-40
          transform transition-transform duration-200
          md:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
        style={{
          background: 'var(--warm-card)',
          borderRight: '1px solid var(--border)',
          boxShadow: '2px 0 20px var(--shadow)',
        }}
      >
        {/* Logo */}
        <div className="px-5 pt-6 pb-5">
          <Link href="/" className="flex items-center gap-3">
            <div
              className="w-[42px] h-[42px] rounded-[12px] flex items-center justify-center font-serif font-extrabold text-white text-[22px]"
              style={{
                background: 'linear-gradient(135deg, var(--coral), var(--coral-light))',
                boxShadow: '0 3px 10px rgba(216, 108, 82, 0.3)',
              }}
            >
              L
            </div>
            <div>
              <span className="font-serif text-[26px] leading-none" style={{ color: 'var(--text-dark)' }}>
                Lulia
              </span>
              <div className="text-[10px] font-semibold tracking-wider uppercase" style={{ color: 'var(--text-light)', marginTop: '-2px' }}>
                Lesson Lab
              </div>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="px-3 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 130px - 80px)' }}>
          <div className="space-y-1">
            {navItems.map((item) => {
              const isActive = item.href === '/'
                ? pathname === '/'
                : pathname?.startsWith(item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="icon-hover hover-slide flex items-center gap-3 px-3 py-2.5 rounded-xl text-[14px] font-semibold"
                  style={isActive
                    ? {
                        background: 'linear-gradient(135deg, var(--coral), var(--coral-light))',
                        color: '#FFFFFF',
                        boxShadow: '0 3px 12px rgba(216, 108, 82, 0.35)',
                      }
                    : {
                        color: 'var(--text-mid)',
                      }
                  }
                >
                  <Image
                    src={`/icons/${item.icon}`}
                    alt=""
                    width={32}
                    height={32}
                    className="nav-icon-img"
                    style={isActive
                      ? { filter: 'brightness(0) invert(1)', opacity: 0.9 }
                      : { opacity: 0.8 }
                    }
                  />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* User profile footer */}
        <div
          className="absolute bottom-0 left-0 right-0 px-4 py-4"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <Link
            href="/settings"
            className="flex items-center gap-3 px-2 py-2 rounded-xl transition-colors"
            style={{ color: 'var(--text-dark)' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--cream)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <Image
              src="/icons/avatar.png"
              alt="Profile"
              width={40}
              height={40}
              className="rounded-full"
              style={{ border: '2px solid var(--border)' }}
            />
            <div>
              <div className="text-sm font-bold" style={{ color: 'var(--text-dark)' }}>
                Teacher
              </div>
              <div className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                Pro Plan
              </div>
            </div>
          </Link>
        </div>
      </aside>
    </>
  );
}
