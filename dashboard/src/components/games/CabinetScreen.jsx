'use client';

/**
 * Per-shell arcade screens — pure CSS/SVG pixel art that runs on the CRT
 * inside each cabinet tile on /games. One unique look per game so the
 * grid doesn't look like 12 copies of the same thing.
 *
 * Palette uses the arcade-room neon tokens (neon-coral, neon-sage,
 * neon-mustard, plus a few neon blues/purples for variety).
 */

export default function CabinetScreen({ shell }) {
  const Render = SCREENS[shell.id] || DefaultScreen;
  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'radial-gradient(circle at center, rgba(78,140,150,0.15), transparent 70%)',
    }}>
      <Render />
    </div>
  );
}

// ═══════════════ 1. Quiz Race — circuit path + racer chevrons
function QuizRace() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%" style={{ filter: 'drop-shadow(0 0 6px rgba(255,138,110,0.4))' }}>
      {/* Track */}
      <path d="M10,70 Q40,30 80,50 T150,30" stroke="#4E8C96" strokeWidth="3" fill="none" strokeDasharray="4 3" />
      {/* Pit marker */}
      <circle cx="10" cy="70" r="4" fill="#FFD87A" />
      <circle cx="150" cy="30" r="4" fill="#FF8A6E" />
      {/* 3 racer chevrons */}
      <polygon points="40,65 50,68 40,71" fill="#FF8A6E" />
      <polygon points="60,55 70,58 60,61" fill="#FFD87A" />
      <polygon points="85,47 95,50 85,53" fill="#9ED4BC" />
      <PixelText x="50" y="15" text="QUIZ RACE" color="#FF8A6E" />
      <PixelText x="62" y="90" text="GO! GO!" color="#FFD87A" size="6" />
    </svg>
  );
}

// ═══════════════ 2. Jeopardy — 5x5 blue board with $ amounts
function Jeopardy() {
  const amounts = ['$100','$200','$300','$400','$500'];
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <rect x="8" y="12" width="144" height="76" fill="#1a1a5e" stroke="#FFD87A" strokeWidth="1.5" />
      {[0,1,2,3,4].map(r => [0,1,2,3,4].map(c => (
        <g key={`${r}-${c}`}>
          <rect
            x={10 + c * 28.4} y={14 + r * 14.8}
            width="27" height="13.8"
            fill={r === 2 && c === 2 ? '#FFD87A' : '#2a2a7e'}
            stroke="#1a1a5e" strokeWidth="0.5"
          />
          {r === 2 && c === 2
            ? <text x={23 + c * 28.4} y={24 + r * 14.8} fontFamily="monospace" fontSize="6" fill="#1a1a5e" fontWeight="bold">DD</text>
            : <text x={14 + c * 28.4} y={24 + r * 14.8} fontFamily="monospace" fontSize="6" fill="#FFD87A" fontWeight="bold">{amounts[r]}</text>
          }
        </g>
      )))}
      <PixelText x="54" y="8" text="JEOPARDY" color="#FFD87A" size="6" />
    </svg>
  );
}

// ═══════════════ 3. Bingo Blitz — 5x5 card with marks
function Bingo() {
  const marked = new Set(['0-2', '1-1', '2-2', '3-3', '4-0']);
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      {['B','I','N','G','O'].map((l, i) => (
        <text key={i} x={20 + i * 26} y="12" fontFamily="monospace" fontSize="10" fill="#FF8A6E" fontWeight="bold">{l}</text>
      ))}
      {[0,1,2,3,4].map(r => [0,1,2,3,4].map(c => {
        const free = r === 2 && c === 2;
        const mark = marked.has(`${r}-${c}`) || free;
        return (
          <g key={`${r}-${c}`}>
            <rect
              x={10 + c * 28.4} y={18 + r * 14.4}
              width="27" height="13"
              fill={mark ? '#9ED4BC' : '#1A1416'}
              stroke="#4E8C96" strokeWidth="0.8"
            />
            {free && <text x={21 + c * 28.4} y={28 + r * 14.4} fontFamily="monospace" fontSize="5" fill="#1A1416" fontWeight="bold">FREE</text>}
            {mark && !free && <text x={21 + c * 28.4} y={29 + r * 14.4} fontFamily="monospace" fontSize="10" fill="#1A1416" fontWeight="bold">✓</text>}
          </g>
        );
      }))}
    </svg>
  );
}

// ═══════════════ 4. Millionaire — escalating ladder
function Millionaire() {
  const tiers = [
    { y: 88, label: '$100',    active: false, final: false },
    { y: 80, label: '$500',    active: false, final: false },
    { y: 72, label: '$1K',     active: false, final: false },
    { y: 64, label: '$5K',     active: true,  final: false },
    { y: 56, label: '$25K',    active: false, final: false },
    { y: 48, label: '$100K',   active: false, final: false },
    { y: 40, label: '$500K',   active: false, final: true },
  ];
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="32" y="12" text="MILLIONAIRE" color="#FFD87A" size="6" />
      {tiers.map((t, i) => (
        <g key={i}>
          <rect
            x="40" y={t.y}
            width="80" height="6"
            fill={t.active ? '#FFD87A' : t.final ? '#FF8A6E' : '#2a2a4e'}
            stroke="#4E8C96" strokeWidth="0.5"
          />
          <text x="80" y={t.y + 4.5} fontFamily="monospace" fontSize="5" fill={t.active ? '#1A1416' : t.final ? '#1A1416' : '#9ED4BC'} fontWeight="bold" textAnchor="middle">
            {t.label}
          </text>
        </g>
      ))}
      {/* 3 lifeline dots */}
      <circle cx="18" cy="55" r="3" fill="#9ED4BC" />
      <circle cx="18" cy="65" r="3" fill="#9ED4BC" />
      <circle cx="18" cy="75" r="3" fill="#9ED4BC" />
    </svg>
  );
}

// ═══════════════ 5. Battle Royale — crosshair + HP bars
function BattleRoyale() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="28" y="14" text="BATTLE ROYALE" color="#FF8A6E" size="6" />
      {/* Crosshair */}
      <circle cx="80" cy="52" r="22" fill="none" stroke="#FF8A6E" strokeWidth="1.5" strokeDasharray="3 2" />
      <line x1="80" y1="40" x2="80" y2="64" stroke="#FF8A6E" strokeWidth="1.5" />
      <line x1="68" y1="52" x2="92" y2="52" stroke="#FF8A6E" strokeWidth="1.5" />
      <circle cx="80" cy="52" r="2" fill="#FFD87A" />
      {/* Player pips bottom */}
      {[0,1,2,3,4,5,6,7].map(i => (
        <rect key={i}
          x={20 + i * 16} y="84"
          width="10" height="5"
          fill={i < 3 ? '#9ED4BC' : '#444'}
        />
      ))}
      <PixelText x="62" y="94" text="3 LEFT" color="#9ED4BC" size="5" />
    </svg>
  );
}

// ═══════════════ 6. Tug of War — rope + team arrows
function TugOfWar() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="44" y="14" text="TUG OF WAR" color="#9ED4BC" size="7" />
      {/* Rope */}
      <line x1="16" y1="50" x2="144" y2="50" stroke="#8B6F5E" strokeWidth="4" strokeLinecap="round" />
      {/* Flag in middle (slightly left = red winning) */}
      <line x1="66" y1="40" x2="66" y2="60" stroke="#FFD87A" strokeWidth="1.5" />
      <polygon points="66,40 80,44 66,48" fill="#FFD87A" />
      {/* Team A (coral) */}
      <g fill="#FF8A6E">
        <circle cx="20" cy="50" r="5" />
        <circle cx="32" cy="50" r="5" />
        <circle cx="44" cy="50" r="5" />
      </g>
      {/* Team B (sage) */}
      <g fill="#9ED4BC">
        <circle cx="116" cy="50" r="5" />
        <circle cx="128" cy="50" r="5" />
        <circle cx="140" cy="50" r="5" />
      </g>
      <PixelText x="20" y="82" text="TEAM A" color="#FF8A6E" size="5" />
      <PixelText x="108" y="82" text="TEAM B" color="#9ED4BC" size="5" />
    </svg>
  );
}

// ═══════════════ 7. Memory Match — 4x3 flipping cards, some matched
function MemoryMatch() {
  const matched = new Set([0, 1, 5, 6]);
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="40" y="12" text="MEMORY MATCH" color="#C5A8E8" size="6" />
      {[0,1,2].map(r => [0,1,2,3].map(c => {
        const i = r * 4 + c;
        const isMatched = matched.has(i);
        return (
          <g key={i}>
            <rect
              x={16 + c * 34} y={20 + r * 22}
              width="30" height="18"
              rx="2"
              fill={isMatched ? '#9ED4BC' : '#8B5A82'}
              stroke="#1A1416" strokeWidth="1"
            />
            {isMatched && <text x={31 + c * 34} y={33 + r * 22} fontFamily="monospace" fontSize="10" fill="#1A1416" fontWeight="bold" textAnchor="middle">✓</text>}
            {!isMatched && <text x={31 + c * 34} y={33 + r * 22} fontFamily="monospace" fontSize="11" fill="#FFD87A" fontWeight="bold" textAnchor="middle">?</text>}
          </g>
        );
      }))}
    </svg>
  );
}

// ═══════════════ 8. Speed Rush — stopwatch + lightning
function SpeedRush() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="48" y="14" text="SPEED RUSH" color="#FFD87A" size="7" />
      {/* Stopwatch */}
      <circle cx="80" cy="56" r="26" fill="#1A1416" stroke="#FFD87A" strokeWidth="2" />
      <rect x="76" y="26" width="8" height="4" fill="#FFD87A" />
      {/* Tick marks */}
      {[0, 90, 180, 270].map(deg => (
        <line key={deg}
          x1="80" y1="32" x2="80" y2="36"
          stroke="#FFD87A" strokeWidth="1.5"
          transform={`rotate(${deg} 80 56)`}
        />
      ))}
      {/* Hand (urgent — pointing to ~10 o'clock) */}
      <line x1="80" y1="56" x2="64" y2="44" stroke="#FF8A6E" strokeWidth="2" strokeLinecap="round" />
      <circle cx="80" cy="56" r="2" fill="#FF8A6E" />
      {/* Lightning bolts on sides */}
      <polygon points="22,40 30,52 26,52 32,68 20,54 24,54" fill="#FFD87A" />
      <polygon points="138,40 130,52 134,52 128,68 140,54 136,54" fill="#FFD87A" />
      <PixelText x="60" y="94" text="GO!" color="#FF8A6E" size="6" />
    </svg>
  );
}

// ═══════════════ 9. Escape Room — door + key + chain
function EscapeRoom() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="44" y="14" text="ESCAPE ROOM" color="#A7C9E8" size="6" />
      {/* Door */}
      <rect x="60" y="24" width="40" height="64" fill="#5C3E34" stroke="#8B6F5E" strokeWidth="2" />
      <rect x="64" y="28" width="32" height="56" fill="#3D2C2E" stroke="#8B6F5E" strokeWidth="0.5" />
      {/* Keyhole */}
      <circle cx="90" cy="54" r="2" fill="#FFD87A" />
      <rect x="89" y="54" width="2" height="5" fill="#FFD87A" />
      {/* Key icon top-left */}
      <circle cx="24" cy="40" r="6" fill="none" stroke="#FFD87A" strokeWidth="2" />
      <rect x="30" y="38" width="12" height="4" fill="#FFD87A" />
      <rect x="38" y="42" width="2" height="4" fill="#FFD87A" />
      {/* Progress nodes (3 rooms) */}
      <circle cx="124" cy="34" r="5" fill="#9ED4BC" />
      <circle cx="124" cy="50" r="5" fill="#9ED4BC" />
      <circle cx="124" cy="66" r="5" fill="none" stroke="#9ED4BC" strokeWidth="1.5" />
      <line x1="124" y1="39" x2="124" y2="45" stroke="#9ED4BC" strokeWidth="2" />
      <line x1="124" y1="55" x2="124" y2="61" stroke="#4E8C96" strokeWidth="2" strokeDasharray="1 1" />
    </svg>
  );
}

// ═══════════════ 10. Card Duel — two dueling cards + lightning
function CardDuel() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="52" y="14" text="CARD DUEL" color="#FF8A6E" size="7" />
      {/* Card A — coral, tilted left */}
      <g transform="rotate(-8 46 58)">
        <rect x="28" y="34" width="36" height="50" rx="3" fill="#FF8A6E" stroke="#1A1416" strokeWidth="1.5" />
        <text x="34" y="45" fontFamily="monospace" fontSize="8" fill="#1A1416" fontWeight="bold">A</text>
        <text x="54" y="80" fontFamily="monospace" fontSize="8" fill="#1A1416" fontWeight="bold" transform="rotate(180 54 80)">A</text>
      </g>
      {/* Card B — sage, tilted right */}
      <g transform="rotate(8 114 58)">
        <rect x="96" y="34" width="36" height="50" rx="3" fill="#9ED4BC" stroke="#1A1416" strokeWidth="1.5" />
        <text x="102" y="45" fontFamily="monospace" fontSize="8" fill="#1A1416" fontWeight="bold">B</text>
        <text x="122" y="80" fontFamily="monospace" fontSize="8" fill="#1A1416" fontWeight="bold" transform="rotate(180 122 80)">B</text>
      </g>
      {/* Clash lightning in middle */}
      <polygon points="74,50 86,50 78,58 84,58 72,70 80,62 74,62" fill="#FFD87A" />
      <text x="80" y="28" fontFamily="monospace" fontSize="8" fill="#FFD87A" fontWeight="bold" textAnchor="middle">VS</text>
    </svg>
  );
}

// ═══════════════ 11. Wheel Spin — 6-slice wheel + pointer
function WheelSpin() {
  const colors = ['#FF8A6E', '#9ED4BC', '#FFD87A', '#A7C9E8', '#C5A8E8', '#4E8C96'];
  const cx = 80, cy = 54, r = 28;
  const slices = colors.map((color, i) => {
    const a1 = (i * 60 - 90) * Math.PI / 180;
    const a2 = ((i + 1) * 60 - 90) * Math.PI / 180;
    const x1 = cx + r * Math.cos(a1);
    const y1 = cy + r * Math.sin(a1);
    const x2 = cx + r * Math.cos(a2);
    const y2 = cy + r * Math.sin(a2);
    return <path key={i} d={`M${cx},${cy} L${x1},${y1} A${r},${r} 0 0,1 ${x2},${y2} Z`} fill={color} stroke="#1A1416" strokeWidth="0.8" />;
  });
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="46" y="14" text="WHEEL SPIN" color="#C5A8E8" size="7" />
      {slices}
      <circle cx={cx} cy={cy} r="4" fill="#FFD87A" stroke="#1A1416" strokeWidth="1" />
      {/* Pointer */}
      <polygon points="80,20 76,28 84,28" fill="#FFD87A" stroke="#1A1416" strokeWidth="1" />
    </svg>
  );
}

// ═══════════════ 12. Tournament — 8-player bracket
function Tournament() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <PixelText x="44" y="12" text="TOURNAMENT" color="#FFD87A" size="7" />
      {/* Round 1 — 4 matchups */}
      {[0,1,2,3].map(i => {
        const y = 22 + i * 18;
        return <g key={i}>
          <rect x="10" y={y} width="24" height="6" fill="#4E8C96" />
          <rect x="10" y={y + 8} width="24" height="6" fill={i === 0 ? '#FFD87A' : '#2a2a4e'} />
          <line x1="34" y1={y + 3} x2="50" y2={y + 3} stroke="#4E8C96" />
          <line x1="34" y1={y + 11} x2="50" y2={y + 11} stroke="#4E8C96" />
          <line x1="50" y1={y + 3} x2="50" y2={y + 11} stroke="#4E8C96" />
        </g>;
      })}
      {/* Round 2 — 2 matchups */}
      {[0,1].map(i => {
        const y = 30 + i * 36;
        return <g key={i}>
          <rect x="60" y={y} width="24" height="6" fill={i === 0 ? '#FFD87A' : '#2a2a4e'} />
          <rect x="60" y={y + 8} width="24" height="6" fill="#2a2a4e" />
          <line x1="84" y1={y + 3} x2="100" y2={y + 3} stroke="#4E8C96" />
          <line x1="84" y1={y + 11} x2="100" y2={y + 11} stroke="#4E8C96" />
          <line x1="100" y1={y + 3} x2="100" y2={y + 11} stroke="#4E8C96" />
        </g>;
      })}
      {/* Final */}
      <rect x="110" y="48" width="24" height="6" fill="#FF8A6E" />
      <rect x="110" y="56" width="24" height="6" fill="#2a2a4e" />
      {/* Trophy */}
      <text x="145" y="58" fontFamily="monospace" fontSize="12" fill="#FFD87A">🏆</text>
    </svg>
  );
}

// ═══════════════ Default — used for any shell id we don't explicitly design
function DefaultScreen() {
  return (
    <svg viewBox="0 0 160 100" width="100%" height="100%">
      <text x="80" y="56" fontFamily="'Press Start 2P', monospace" fontSize="10" fill="#9ED4BC" textAnchor="middle"
        style={{ filter: 'drop-shadow(0 0 6px #6BA08A)' }}>
        READY
      </text>
    </svg>
  );
}

// Tiny pixel-text helper (Press Start 2P at small sizes)
function PixelText({ x, y, text, color, size = 8 }) {
  return (
    <text x={x} y={y}
      fontFamily="'Press Start 2P', monospace"
      fontSize={size}
      fill={color}
      style={{ filter: `drop-shadow(0 0 4px ${color})` }}>
      {text}
    </text>
  );
}

// Registry — maps shell.id to its screen component
const SCREENS = {
  quiz_race: QuizRace,
  jeopardy: Jeopardy,
  bingo_blitz: Bingo,
  millionaire: Millionaire,
  battle_royale: BattleRoyale,
  team_tug_of_war: TugOfWar,
  memory_match: MemoryMatch,
  speed_rush: SpeedRush,
  escape_room: EscapeRoom,
  card_duel: CardDuel,
  wheel_spin: WheelSpin,
  tournament: Tournament,
};
