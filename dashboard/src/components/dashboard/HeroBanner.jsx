'use client';

export default function HeroBanner() {
  // TODO: fetch teacher name from API
  const greeting = getGreeting();

  return (
    <div
      className="relative overflow-hidden rounded-card p-8"
      style={{
        background: 'linear-gradient(135deg, var(--sage), var(--teal))',
        minHeight: 140,
      }}
    >
      {/* Floating shapes */}
      <div
        className="absolute w-24 h-24 rounded-full"
        style={{
          top: -10, right: 80,
          background: 'rgba(255,255,255,0.08)',
          animation: 'floatY 6s ease-in-out infinite',
        }}
      />
      <div
        className="absolute w-14 h-14"
        style={{
          bottom: 10, right: 200,
          background: 'rgba(255,255,255,0.06)',
          transform: 'rotate(45deg)',
          borderRadius: 8,
          animation: 'floatY-slow 8s ease-in-out infinite',
        }}
      />
      <div
        className="absolute w-10 h-10 rounded-full"
        style={{
          top: 20, right: 30,
          background: 'rgba(255,255,255,0.05)',
          animation: 'floatY 7s ease-in-out infinite 1s',
        }}
      />

      {/* Content */}
      <div className="relative z-10">
        <h1 className="font-serif text-[28px] text-white mb-1">
          {greeting}, Teacher!
        </h1>
        <p className="text-white/90 text-[15px] max-w-lg">
          {/* TODO: wire to real data */}
          You have 4 lessons planned for today and 12 assignments waiting for review.
          Your students&apos; average mastery jumped 6% this week — nice work!
        </p>
      </div>
    </div>
  );
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}
