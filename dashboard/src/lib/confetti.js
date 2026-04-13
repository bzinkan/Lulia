/**
 * Confetti helpers for game celebration moments.
 * Lazy-imports canvas-confetti so SSR never evaluates its window references.
 */

const RETRO_EARTH_COLORS = ['#D86C52', '#E8927A', '#6BA08A', '#E9B44C', '#F5EDE0'];

async function confetti() {
  if (typeof window === 'undefined') return null;
  const mod = await import('canvas-confetti');
  return mod.default;
}

export async function burst(origin = { x: 0.5, y: 0.6 }) {
  const c = await confetti();
  if (!c) return;
  c({ particleCount: 60, spread: 70, origin, colors: RETRO_EARTH_COLORS });
}

export async function correctAnswer(origin = { x: 0.5, y: 0.6 }) {
  const c = await confetti();
  if (!c) return;
  c({
    particleCount: 40, spread: 55, startVelocity: 35, origin,
    colors: ['#6BA08A', '#E9B44C', '#D86C52'], ticks: 80,
  });
}

export async function winnerCelebration() {
  const c = await confetti();
  if (!c) return;
  const end = Date.now() + 2000;
  const frame = () => {
    c({ particleCount: 7, angle: 60,  spread: 55, origin: { x: 0, y: 0.7 }, colors: RETRO_EARTH_COLORS });
    c({ particleCount: 7, angle: 120, spread: 55, origin: { x: 1, y: 0.7 }, colors: RETRO_EARTH_COLORS });
    if (Date.now() < end) requestAnimationFrame(frame);
  };
  frame();
}
