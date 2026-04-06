'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Calendar, PlusCircle, FileText, Upload, BookOpen, Settings, Zap, Menu, X } from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { label: 'Dashboard', icon: Home, href: '/' },
  { label: 'Weekly Planner', icon: Calendar, href: '/planner' },
  { label: 'New Assignment', icon: PlusCircle, href: '/assignments/new' },
  { label: 'Assignments', icon: FileText, href: '/assignments' },
  { label: 'Content Library', icon: Upload, href: '/library' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 z-30">
        <span className="text-lg font-semibold text-indigo-600">Lulia</span>
        <button onClick={() => setOpen(!open)} className="p-2 text-gray-600">
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile overlay */}
      {open && (
        <div className="md:hidden fixed inset-0 bg-black/30 z-30" onClick={() => setOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-white border-r border-gray-200 z-40
        transform transition-transform duration-200
        md:translate-x-0
        ${open ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-white" />
            </div>
            <span className="text-xl font-semibold text-gray-900">Lulia</span>
          </Link>
        </div>

        {/* Nav */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const isActive = item.href === '/'
              ? pathname === '/'
              : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                  ${isActive
                    ? 'bg-indigo-50 text-indigo-700 border-r-2 border-indigo-700'
                    : 'text-gray-600 hover:bg-gray-50'
                  }
                `}
              >
                <Icon className="w-5 h-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Credit meter */}
        <div className="absolute bottom-4 left-3 right-3">
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg">
            <Zap className="w-4 h-4 text-indigo-600" />
            <span className="text-sm font-medium text-gray-700">50 credits</span>
          </div>
        </div>
      </aside>
    </>
  );
}
