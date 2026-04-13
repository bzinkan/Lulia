/**
 * Confetti helpers for game celebration moments.
 * Uses canvas-confetti — small, zero React coupling.
 */
import confetti from 'canvas-confetti';

const RETRO_EARTH_COLORS = ['#D86C52', '#E8927A', '#6BA08A', '#E9B44C', '#F5EDE0'];

export function burst(origin = { x: 0.5, y: 0.6 }) {
  confetti({
    particleCount: 60,
    spread: 70,
    origin,
    colors: RETRO_EARTH_COLORS,
  });
}

export function correctAnswer(origin = { x: 0.5, y: 0.6 }) {
  confetti({
    particleCount: 40,
    spread: 55,
    startVelocity: 35,
    origin,
    colors: ['#6BA08A', '#E9B44C', '#D86C52'],
    ticks: 80,
  });
}

export function winnerCelebration() {
  // Two-sided burst that lasts ~2 seconds
  const end = Date.now() + 2000;
  const frame = () => {
    confetti({
      particleCount: 7,
      angle: 60,
      spread: 55,
      origin: { x: 0, y: 0.7 },
      colors: RETRO_EARTH_COLORS,
    });
    confetti({
      particleCount: 7,
      angle: 120,
      spread: 55,
      origin: { x: 1, y: 0.7 },
      colors: RETRO_EARTH_COLORS,
    });
    if (Date.now() < end) requestAnimationFrame(frame);
  };
  frame();
}
