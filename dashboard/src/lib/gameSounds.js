/**
 * Game sound effects using the Web Audio API (no external files required).
 *
 * Howler.js is installed and imported so teachers can drop MP3s into
 * /public/sounds/ later and flip USE_SYNTH=false. For now everything is
 * synthesized — keeps the bundle lean and works without any assets.
 *
 * Design:
 *   - correct()    — bright major third, feels rewarding
 *   - incorrect()  — short descending minor, soft thud (not harsh)
 *   - tick()       — quick sub-100ms blip for countdown
 *   - tickUrgent() — louder sharper tick for last 3 seconds
 *   - whoosh()     — question appears
 *   - drumroll()   — leaderboard reveal
 *   - fanfare()    — game end / winner
 *
 * All tones use short envelopes (attack 5ms, release 80-200ms) so they
 * feel snappy and never drone. Volumes are calibrated to sit under
 * narration/chatter.
 */

let audioCtx = null;

function ctx() {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch {
      return null;
    }
  }
  // Resume on first user gesture — browsers auto-suspend otherwise
  if (audioCtx.state === 'suspended') audioCtx.resume();
  return audioCtx;
}

function tone({ freq, start = 0, duration = 0.2, type = 'sine', gain = 0.3, attack = 0.005, release = 0.08 }) {
  const ac = ctx();
  if (!ac) return;
  const now = ac.currentTime + start;
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, now);
  g.gain.setValueAtTime(0, now);
  g.gain.linearRampToValueAtTime(gain, now + attack);
  g.gain.linearRampToValueAtTime(0, now + duration - release + 0.001);
  g.gain.linearRampToValueAtTime(0, now + duration);
  osc.connect(g); g.connect(ac.destination);
  osc.start(now);
  osc.stop(now + duration + 0.05);
}

function sweep({ fromFreq, toFreq, start = 0, duration = 0.2, type = 'sine', gain = 0.25 }) {
  const ac = ctx();
  if (!ac) return;
  const now = ac.currentTime + start;
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(fromFreq, now);
  osc.frequency.exponentialRampToValueAtTime(toFreq, now + duration);
  g.gain.setValueAtTime(0, now);
  g.gain.linearRampToValueAtTime(gain, now + 0.01);
  g.gain.linearRampToValueAtTime(0, now + duration);
  osc.connect(g); g.connect(ac.destination);
  osc.start(now);
  osc.stop(now + duration + 0.05);
}

export const sounds = {
  correct() {
    // C5 E5 G5 arpeggio — quick, bright, rewarding
    tone({ freq: 523, start: 0,    duration: 0.12, type: 'triangle', gain: 0.3 });
    tone({ freq: 659, start: 0.08, duration: 0.12, type: 'triangle', gain: 0.3 });
    tone({ freq: 784, start: 0.16, duration: 0.20, type: 'triangle', gain: 0.35 });
  },
  incorrect() {
    // Soft descending minor third — not harsh
    tone({ freq: 330, start: 0,    duration: 0.10, type: 'sine',   gain: 0.25 });
    tone({ freq: 262, start: 0.08, duration: 0.20, type: 'sine',   gain: 0.25 });
  },
  tick() {
    tone({ freq: 600, duration: 0.05, type: 'square', gain: 0.08, release: 0.02 });
  },
  tickUrgent() {
    tone({ freq: 900, duration: 0.08, type: 'square', gain: 0.18, release: 0.02 });
  },
  whoosh() {
    sweep({ fromFreq: 200, toFreq: 800, duration: 0.18, type: 'sine', gain: 0.2 });
  },
  drumroll() {
    // Quick rumble — 8 low hits rapid fire
    for (let i = 0; i < 10; i++) {
      tone({ freq: 100 + Math.random() * 40, start: i * 0.05, duration: 0.04, type: 'square', gain: 0.15, release: 0.02 });
    }
  },
  fanfare() {
    // C-E-G-C ascending with a triumphant hold
    tone({ freq: 523, start: 0.00, duration: 0.15, type: 'triangle', gain: 0.3 });
    tone({ freq: 659, start: 0.10, duration: 0.15, type: 'triangle', gain: 0.3 });
    tone({ freq: 784, start: 0.20, duration: 0.15, type: 'triangle', gain: 0.3 });
    tone({ freq: 1046, start: 0.30, duration: 0.45, type: 'triangle', gain: 0.4 });
    tone({ freq: 1318, start: 0.30, duration: 0.45, type: 'triangle', gain: 0.25 }); // E6 harmony
  },
  bingo() {
    // 5-note ascending "B-I-N-G-O" chant — square wave for retro diner-hall bite.
    // G4-B4-D5-G5-D6 then a held chord for the final "O".
    tone({ freq: 392, start: 0.00, duration: 0.12, type: 'square', gain: 0.22 });
    tone({ freq: 494, start: 0.13, duration: 0.12, type: 'square', gain: 0.22 });
    tone({ freq: 587, start: 0.26, duration: 0.12, type: 'square', gain: 0.22 });
    tone({ freq: 784, start: 0.39, duration: 0.12, type: 'square', gain: 0.22 });
    tone({ freq: 1175, start: 0.52, duration: 0.50, type: 'triangle', gain: 0.30 });
    tone({ freq: 784, start: 0.52, duration: 0.50, type: 'triangle', gain: 0.20 });
    tone({ freq: 587, start: 0.52, duration: 0.50, type: 'triangle', gain: 0.18 });
  },
  ringIn() {
    // Buzzer ring-in for teacher when a student claims bingo — two rapid trills.
    sweep({ fromFreq: 700, toFreq: 1200, start: 0.00, duration: 0.10, type: 'square', gain: 0.22 });
    sweep({ fromFreq: 700, toFreq: 1200, start: 0.14, duration: 0.10, type: 'square', gain: 0.22 });
    tone({ freq: 1400, start: 0.28, duration: 0.18, type: 'triangle', gain: 0.28 });
  },
  ddReveal() {
    // Daily Double reveal: dramatic rising sweep + a gold-hit chord.
    sweep({ fromFreq: 150, toFreq: 900, start: 0.00, duration: 0.45, type: 'sawtooth', gain: 0.22 });
    tone({ freq: 988, start: 0.45, duration: 0.18, type: 'triangle', gain: 0.3 });   // B5
    tone({ freq: 1319, start: 0.45, duration: 0.30, type: 'triangle', gain: 0.3 });  // E6
    tone({ freq: 1568, start: 0.55, duration: 0.50, type: 'triangle', gain: 0.32 }); // G6
  },
};

// Muted state — lets UI toggle sound globally
let muted = false;
export function setMuted(v) { muted = !!v; }
export function isMuted() { return muted; }

// Wrapped API — respects mute
export function play(name) {
  if (muted) return;
  if (sounds[name]) sounds[name]();
}
