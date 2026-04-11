'use client';

import Image from 'next/image';
import Link from 'next/link';

const actions = [
  { label: 'AI Generate',      icon: 'ai.png',        href: '/assignments/new', accent: 'var(--coral)' },
  { label: 'Create Worksheet', icon: 'document.png',  href: '/assignments/new', accent: 'var(--sage)' },
  { label: 'Start Live Game',  icon: 'gamepad.png',   href: '/games',           accent: 'var(--teal)' },
  { label: 'Record Video',     icon: 'clipboard.png', href: '/videos',          accent: 'var(--mustard)' },
];

export default function QuickActions() {
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
        Quick Actions
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {actions.map(action => (
          <Link
            key={action.label}
            href={action.href}
            className="hover-lift flex flex-col items-center gap-2 p-4 rounded-xl text-center"
            style={{
              background: 'var(--cream)',
              border: '1px solid var(--border)',
            }}
          >
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center"
              style={{ background: `${action.accent}15` }}
            >
              <Image src={`/icons/${action.icon}`} alt="" width={28} height={28} style={{ opacity: 0.85 }} />
            </div>
            <span className="text-[12px] font-bold" style={{ color: 'var(--text-dark)' }}>
              {action.label}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
