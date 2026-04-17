'use client';
import { useEffect, useState } from 'react';
import { Volume2, VolumeX, LogOut } from 'lucide-react';
import { setMuted, isMuted } from '@/lib/gameSounds';

/**
 * CabinetStage — shared in-cabinet arcade chrome for every live game shell.
 *
 * Wraps any student or teacher play view in a dark-neon stage:
 *   - Marquee header with bulb row + game name in Press Start 2P
 *   - HUD band for question counter / streak / timer / player count
 *   - CRT scanlines overlay (via .arcade-stage::after in arcade-hud.css)
 *   - Per-game accent color (drives marquee glow, screen border, buttons)
 *   - Mute toggle + optional exit pill
 *
 * Shells continue to own their interior content (question card, tiles,
 * boards, etc.) — they just render inside <CabinetStage>…</CabinetStage>.
 *
 * Accent colors are resolved from the shell's registry entry (accentColor)
 * in dashboard/src/lib/gameShellConfigs.js and passed in as `accent`.
 */
export default function CabinetStage({
  gameName,
  tagline,
  accent = '#FFBE0B',           // hex — drives --arcade-accent CSS var
  hudLeft = null,               // arbitrary JSX for left side of HUD band
  hudRight = null,              // arbitrary JSX for right side
  showMute = true,
  onExit = null,                // if provided, renders an Exit pill in the top-right
  speedlines = 'idle',          // 'off' | 'idle' | 'fast' | 'urgent'
  children,
}) {
  const [muted, setMutedState] = useState(false);

  useEffect(() => { setMutedState(isMuted()); }, []);

  function toggleMute() {
    const v = !muted;
    setMuted(v);
    setMutedState(v);
  }

  const speedClass =
    speedlines === 'off'    ? ''
  : speedlines === 'fast'   ? 'arcade-speedlines arcade-speedlines--fast'
  : speedlines === 'urgent' ? 'arcade-speedlines arcade-speedlines--urgent'
  :                           'arcade-speedlines';

  return (
    <div className="arcade-stage" style={{ '--arcade-accent': accent }}>
      {speedClass && <div className={speedClass} aria-hidden />}

      {/* ── Marquee header ── */}
      <div className="arcade-marquee">
        <div className="arcade-bulb-row" aria-hidden>
          {Array.from({ length: 18 }).map((_, i) => <span key={i} className="arcade-bulb" />)}
        </div>
        <div className="arcade-marquee-body">
          <div>
            <div className="arcade-title">{gameName || 'LULIA ARCADE'}</div>
            {tagline && <div className="arcade-tagline">{tagline}</div>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {showMute && (
              <button
                className="arcade-pill"
                onClick={toggleMute}
                aria-label={muted ? 'Unmute sound' : 'Mute sound'}
                title={muted ? 'Unmute' : 'Mute'}
              >
                {muted ? <VolumeX style={{ width: 12, height: 12 }} /> : <Volume2 style={{ width: 12, height: 12 }} />}
                {muted ? 'Muted' : 'Sound'}
              </button>
            )}
            {onExit && (
              <button
                className="arcade-pill"
                onClick={onExit}
                aria-label="Exit to arcade"
                title="Exit"
              >
                <LogOut style={{ width: 12, height: 12 }} />
                Exit
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── HUD band (question counter, streak, timer, player count) ── */}
      {(hudLeft || hudRight) && (
        <div className="arcade-hud">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {hudLeft}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {hudRight}
          </div>
        </div>
      )}

      {/* ── Interior: the shell's content ── */}
      <div className="arcade-stage__interior" style={{ maxWidth: 960, margin: '0 auto' }}>
        {children}
      </div>
    </div>
  );
}

/* ============================================================
   Small shared HUD primitives — import and use from any shell.
   ============================================================ */

export function ArcadeChip({ children, variant = 'solid' }) {
  return (
    <span className={variant === 'ghost' ? 'arcade-hud-chip arcade-hud-chip--ghost' : 'arcade-hud-chip'}>
      {children}
    </span>
  );
}

/**
 * Horizontal LED segment timer. `pct` is 0..1 fill, `seconds` optional numeric readout.
 */
export function ArcadeLedTimer({ pct = 1, seconds = null, segments = 20 }) {
  const filled = Math.max(0, Math.min(segments, Math.round(pct * segments)));
  const urgent = pct > 0 && pct <= 0.25;
  const warn = pct > 0.25 && pct <= 0.5;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="arcade-led-bar" role="progressbar" aria-valuenow={Math.round(pct * 100)}>
        {Array.from({ length: segments }).map((_, i) => {
          const lit = i < filled;
          const cls = !lit
            ? 'arcade-led-bar__seg arcade-led-bar__seg--off'
            : urgent ? 'arcade-led-bar__seg arcade-led-bar__seg--urgent'
            : warn   ? 'arcade-led-bar__seg arcade-led-bar__seg--warn'
            :          'arcade-led-bar__seg';
          return <span key={i} className={cls} />;
        })}
      </div>
      {seconds !== null && (
        <span className="arcade-led-num" style={{ fontSize: 14, minWidth: 28, textAlign: 'right' }}>
          {seconds}
        </span>
      )}
    </div>
  );
}
