'use client';

export default function HeroBanner({ data, loading }) {
  const greeting = getGreeting();
  const firstName = pickFirstName(data?.teacher?.name);
  const planCount = data?.today?.plan_count ?? 0;
  const pendingGrading = data?.today?.pending_grading_count ?? 0;
  const weekDelta = data?.mastery?.week_delta_pct ?? 0;

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
          {greeting}{firstName ? `, ${firstName}` : ''}!
        </h1>
        <p className="text-white/90 text-[15px] max-w-lg min-h-[24px]">
          {loading && !data ? 'Loading…' : buildSubline(planCount, pendingGrading, weekDelta)}
        </p>
      </div>
    </div>
  );
}

/**
 * Build a contextual one-liner for the hero subhead.
 *
 * Why piece it together instead of a single sentence: we want to gracefully
 * hide clauses that are zero — "0 lessons planned" reads worse than just
 * omitting the phrase. Keeps the tone friendly for cold accounts.
 */
function buildSubline(planCount, pendingGrading, weekDelta) {
  const parts = [];
  if (planCount > 0) {
    parts.push(`You have ${planCount} lesson${planCount === 1 ? '' : 's'} planned for today`);
  }
  if (pendingGrading > 0) {
    const verb = parts.length ? 'and' : 'You have';
    parts.push(
      `${verb} ${pendingGrading} assignment${pendingGrading === 1 ? '' : 's'} waiting for review`
    );
  }
  let line = parts.join(' ');
  if (!line) line = "Nothing on deck today — great time to plan ahead";
  // Tack on the mastery delta only when it's genuinely positive; we avoid
  // surfacing negatives in the hero (there's a dedicated dashboard widget
  // where a dip should show up, not in a celebratory banner).
  if (weekDelta > 0) {
    line += `. Your students’ average mastery jumped ${weekDelta}% this week — nice work!`;
  } else if (line && !/\.$/.test(line)) {
    line += '.';
  }
  return line;
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

/**
 * Extract the teacher's first name from whatever the backend stored.
 *
 * The `teachers.name` column is a free-text display name (could be "Ms. Rivera",
 * "Brian Z.", or "Alex"). For a greeting we want something that reads naturally
 * after "Good morning, …" — so take the first whitespace-separated token and
 * strip trailing punctuation. If the result is empty, fall back to no name.
 */
function pickFirstName(name) {
  if (!name) return '';
  const first = String(name).trim().split(/\s+/)[0] || '';
  return first.replace(/[.,]$/, '');
}
