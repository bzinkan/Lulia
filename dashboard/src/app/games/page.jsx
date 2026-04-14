'use client';
import { useEffect, useMemo, useState } from 'react';
import { useClassContext } from '@/components/ClassContext';
import { apiFetch } from '@/lib/api';
import { ARCADE_CATEGORIES, GAME_SHELLS } from '@/lib/gameShellConfigs';
import GameSetupModal from '@/components/games/GameSetupModal';
import CabinetScreen from '@/components/games/CabinetScreen';

/**
 * Lulia Arcade — /games route.
 * CRT-style cabinet grid, neon marquee, Press Start 2P retro typography.
 * Data layer (shells, sessions, launch, replay) is the same as Phase 1.
 * Only the visual treatment is bespoke to this room.
 */
export default function GamesPage() {
  const { activeClassId, teacherId } = useClassContext();
  const [sessions, setSessions] = useState([]);
  const [selectedShell, setSelectedShell] = useState(null);
  const [replayingId, setReplayingId] = useState(null);
  const [activeCat, setActiveCat] = useState('ALL');

  useEffect(() => { loadSessions(); }, [teacherId]);

  async function loadSessions() {
    try {
      const data = await apiFetch(`/api/v1/games/sessions?teacher_id=${teacherId}`);
      setSessions(data.sessions || []);
    } catch {}
  }

  async function handleReplay(sessionId) {
    setReplayingId(sessionId);
    try {
      const result = await apiFetch(`/api/v1/games/${sessionId}/replay`, {
        method: 'POST',
        body: JSON.stringify({ teacher_id: teacherId }),
      });
      if (result.pin) {
        window.open(`/play/${result.pin}`, '_blank');
        loadSessions();
      } else {
        alert(result.error || 'Replay failed');
      }
    } catch (e) {
      alert(e.message);
    } finally {
      setReplayingId(null);
    }
  }

  function handleLaunched(result) {
    setSelectedShell(null);
    if (result?.pin) window.open(`/play/${result.pin}`, '_blank');
    loadSessions();
  }

  const filtered = useMemo(() => {
    if (activeCat === 'ALL') return GAME_SHELLS;
    return GAME_SHELLS.filter(s => s.arcade_category === activeCat);
  }, [activeCat]);

  const totalCabinets = GAME_SHELLS.filter(s => s.phase === 1).length;
  const totalPlayed = sessions.length;

  return (
    <div className="arcade-room">
      {/* Press Start 2P font — scoped to this page via <link> */}
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap"
        rel="stylesheet"
      />

      {/* ── Marquee header ── */}
      <div className="arcade-header">
        <div className="bulb-row">
          {Array.from({ length: 18 }).map((_, i) => <span key={i} className="bulb" />)}
        </div>
        <div className="header-content">
          <h1 className="arcade-title">LULIA ARCADE</h1>
          <div className="arcade-subtitle">★ INSERT COIN TO PLAY ★</div>
          <div className="header-stats">
            <div className="h-stat"><div className="n">{totalCabinets}</div><div className="l">CABINETS</div></div>
            <div className="h-stat"><div className="n">{totalPlayed}</div><div className="l">GAMES PLAYED</div></div>
            <div className="h-stat"><div className="n">{GAME_SHELLS.length}</div><div className="l">HIGH SCORES</div></div>
          </div>
        </div>
        <div className="bulb-row">
          {Array.from({ length: 18 }).map((_, i) => <span key={i} className="bulb" />)}
        </div>
      </div>

      {/* ── Filter row ── */}
      <div className="filters">
        {ARCADE_CATEGORIES.map(c => (
          <button key={c.id}
            onClick={() => setActiveCat(c.id)}
            className={`filter-btn ${activeCat === c.id ? 'active' : ''}`}>
            {c.label}
          </button>
        ))}
      </div>

      {/* ── Cabinet grid ── */}
      <div className="cabinet-grid">
        {filtered.map(shell => {
          const comingSoon = shell.phase !== 1;
          return (
            <div key={shell.id} className={`cabinet ${comingSoon ? 'coming-soon' : ''}`} data-cat={shell.arcade_category}>
              {/* Marquee */}
              <div className="marquee">
                <span className="bulb sm" /><span className="bulb sm" /><span className="bulb sm" /><span className="bulb sm" /><span className="bulb sm" />
                <div className="marquee-title">{shell.marquee_name || shell.name.toUpperCase()}</div>
                <span className="bulb sm" /><span className="bulb sm" /><span className="bulb sm" /><span className="bulb sm" /><span className="bulb sm" />
              </div>

              {/* CRT screen */}
              <div className="screen-bezel">
                <div className="screen">
                  <div className="screen-inner">
                    <CabinetScreen shell={shell} />
                  </div>
                  <div className="scanlines" />
                  <div className="screen-glow" />
                  <span className="cab-badge" data-cat={shell.arcade_category}>{shell.arcade_category}</span>
                  {comingSoon && <span className="cab-soon">COMING SOON</span>}
                </div>
              </div>

              {/* Control panel */}
              <div className="control-panel">
                <div className="game-desc">{shell.arcade_tagline}</div>
                <div className="cabinet-meta">
                  <div className="meta-pill">{shell.min_players}+ PLAYERS</div>
                  <div className="meta-pill">{shell.play_time_min} MIN</div>
                </div>
                <button
                  className="coin-btn"
                  disabled={comingSoon}
                  onClick={() => !comingSoon && setSelectedShell(shell)}>
                  <span className="coin-icon">◎</span>
                  {comingSoon ? 'SOON' : 'INSERT COIN'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Recent sessions ── */}
      <div className="sessions-panel">
        <h2 className="sessions-title">▶ RECENT GAMES</h2>
        {sessions.length === 0 ? (
          <p className="sessions-empty">No games yet. Drop a coin above to get started.</p>
        ) : (
          <div className="sessions-table">
            {sessions.map(s => {
              const shell = GAME_SHELLS.find(g => g.id === s.game_shell_id);
              return (
                <div key={s.session_id} className="session-row">
                  <div className="session-name">{shell?.marquee_name || s.game_shell_id}</div>
                  <div className="session-pin">{s.pin}</div>
                  <div className={`session-status status-${s.status}`}>{s.status}</div>
                  <div className="session-date">{s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}</div>
                  <button
                    className="session-replay"
                    disabled={replayingId === s.session_id}
                    onClick={() => handleReplay(s.session_id)}>
                    {replayingId === s.session_id ? '…' : 'REPLAY (FREE)'}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedShell && (
        <GameSetupModal
          shell={selectedShell}
          teacherId={teacherId}
          classId={activeClassId}
          onLaunched={handleLaunched}
          onClose={() => setSelectedShell(null)}
        />
      )}

      <style jsx>{`
        .arcade-room {
          --cabinet: #3D2C2E;
          --cabinet-dark: #2A1D1F;
          --cabinet-wood: #5C3E34;
          --screen-bg: #1A1416;
          --bulb-on: #F4D465;
          --bulb-off: #8B6F5E;
          --neon-coral: #FF8A6E;
          --neon-sage: #9ED4BC;
          --neon-mustard: #FFD87A;

          max-width: 1400px;
          margin: 0 auto;
          padding: 28px 24px 48px;
          background:
            radial-gradient(circle at 20% 10%, rgba(216,108,82,0.06), transparent 40%),
            radial-gradient(circle at 80% 90%, rgba(78,140,150,0.06), transparent 40%),
            var(--cream, #FAF5ED);
          min-height: 100vh;
          font-family: 'Nunito', sans-serif;
        }

        /* ── Header ── */
        .arcade-header {
          background: linear-gradient(180deg, var(--cabinet) 0%, var(--cabinet-dark) 100%);
          border-radius: 16px 16px 8px 8px;
          padding: 0;
          margin-bottom: 32px;
          box-shadow: 0 8px 24px rgba(61,44,46,0.35);
          overflow: hidden;
        }
        .bulb-row {
          display: flex;
          justify-content: space-between;
          padding: 10px 16px;
          background: var(--cabinet-dark);
          border-bottom: 2px solid var(--cabinet-wood);
        }
        .bulb {
          width: 10px; height: 10px;
          border-radius: 50%;
          background: var(--bulb-on);
          box-shadow: 0 0 8px var(--bulb-on), 0 0 16px rgba(244,212,101,0.5);
          animation: bulbFlicker 1.2s infinite;
        }
        .bulb.sm { width: 6px; height: 6px; box-shadow: 0 0 4px var(--bulb-on); }
        .bulb-row .bulb:nth-child(even) { animation-delay: 0.6s; }
        @keyframes bulbFlicker {
          0%, 100% { background: var(--bulb-on); box-shadow: 0 0 8px var(--bulb-on), 0 0 16px rgba(244,212,101,0.6); }
          50% { background: var(--bulb-off); box-shadow: 0 0 2px var(--bulb-off); }
        }
        .header-content {
          padding: 32px 40px 28px;
          text-align: center;
        }
        .arcade-title {
          font-family: 'Press Start 2P', monospace;
          font-size: 42px;
          color: var(--neon-coral);
          text-shadow: 0 0 10px #D86C52, 0 0 20px #D86C52, 3px 3px 0 var(--cabinet-dark);
          letter-spacing: 4px;
          margin-bottom: 10px;
        }
        .arcade-subtitle {
          font-family: 'Press Start 2P', monospace;
          font-size: 11px;
          color: var(--neon-mustard);
          letter-spacing: 3px;
          text-shadow: 0 0 8px #DAB04E;
          animation: blink 1.4s infinite;
        }
        @keyframes blink {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0.3; }
        }
        .header-stats {
          display: flex;
          justify-content: center;
          gap: 48px;
          margin-top: 20px;
        }
        .h-stat .n {
          font-family: 'Press Start 2P', monospace;
          font-size: 18px;
          color: var(--neon-sage);
          text-shadow: 0 0 8px #6BA08A;
        }
        .h-stat .l {
          font-family: 'Press Start 2P', monospace;
          font-size: 8px;
          color: rgba(255,255,255,0.5);
          letter-spacing: 2px;
          margin-top: 6px;
        }

        /* ── Filter row ── */
        .filters {
          display: flex;
          gap: 8px;
          margin-bottom: 28px;
          flex-wrap: wrap;
          padding: 12px;
          background: var(--warm-card, white);
          border-radius: 10px;
          border: 1px solid var(--border, #E8DDD0);
        }
        .filter-btn {
          padding: 8px 16px;
          border-radius: 6px;
          border: 2px solid var(--cabinet);
          background: var(--warm-bg, #F5EDE0);
          color: var(--cabinet);
          font-family: 'Press Start 2P', monospace;
          font-size: 9px;
          letter-spacing: 1px;
          cursor: pointer;
          transition: all 0.15s;
        }
        .filter-btn:hover { background: #DAB04E; }
        .filter-btn.active {
          background: #D86C52;
          color: white;
          border-color: var(--cabinet-dark);
          box-shadow: 0 0 0 2px rgba(216,108,82,0.2), 2px 2px 0 var(--cabinet-dark);
          transform: translate(-1px, -1px);
        }

        /* ── Cabinet grid ── */
        .cabinet-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 24px;
        }
        @media (max-width: 1200px) { .cabinet-grid { grid-template-columns: repeat(3, 1fr); } }
        @media (max-width: 900px)  { .cabinet-grid { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 600px)  { .cabinet-grid { grid-template-columns: 1fr; } }

        .cabinet {
          background: linear-gradient(180deg, var(--cabinet-wood) 0%, var(--cabinet) 60%, var(--cabinet-dark) 100%);
          border-radius: 10px 10px 6px 6px;
          overflow: hidden;
          box-shadow:
            0 12px 24px rgba(61,44,46,0.35),
            inset 0 -3px 0 rgba(0,0,0,0.3),
            inset 3px 0 0 rgba(255,255,255,0.05),
            inset -3px 0 0 rgba(0,0,0,0.2);
          transition: all 0.25s;
          display: flex;
          flex-direction: column;
          opacity: 0;
          transform: translateY(20px);
          animation: cabIn 0.5s ease-out forwards;
        }
        @keyframes cabIn { to { opacity: 1; transform: translateY(0); } }
        .cabinet:nth-child(1)  { animation-delay: 0.05s; }
        .cabinet:nth-child(2)  { animation-delay: 0.12s; }
        .cabinet:nth-child(3)  { animation-delay: 0.19s; }
        .cabinet:nth-child(4)  { animation-delay: 0.26s; }
        .cabinet:nth-child(5)  { animation-delay: 0.33s; }
        .cabinet:nth-child(6)  { animation-delay: 0.40s; }
        .cabinet:nth-child(7)  { animation-delay: 0.47s; }
        .cabinet:nth-child(8)  { animation-delay: 0.54s; }
        .cabinet:nth-child(9)  { animation-delay: 0.61s; }
        .cabinet:nth-child(10) { animation-delay: 0.68s; }
        .cabinet:nth-child(11) { animation-delay: 0.75s; }
        .cabinet:nth-child(12) { animation-delay: 0.82s; }

        .cabinet:hover {
          transform: translateY(-6px);
          box-shadow: 0 20px 36px rgba(61,44,46,0.45), 0 0 0 2px #DAB04E, inset 0 -3px 0 rgba(0,0,0,0.3);
        }
        .cabinet.coming-soon { opacity: 0.6; }

        .marquee {
          background: linear-gradient(180deg, var(--cabinet-dark), #000);
          padding: 10px 12px 8px;
          display: flex;
          align-items: center;
          gap: 4px;
          border-bottom: 2px solid var(--cabinet-wood);
        }
        .marquee-title {
          flex: 1;
          text-align: center;
          font-family: 'Press Start 2P', monospace;
          font-size: 10px;
          color: var(--neon-mustard);
          text-shadow: 0 0 4px #DAB04E, 0 0 8px rgba(218,176,78,0.5);
          letter-spacing: 1px;
          padding: 0 4px;
        }

        .screen-bezel { padding: 12px; background: var(--cabinet-dark); }
        .screen {
          position: relative;
          aspect-ratio: 16 / 10;
          background: var(--screen-bg);
          border-radius: 14px;
          overflow: hidden;
          border: 4px solid #000;
          box-shadow: inset 0 0 20px rgba(0,0,0,0.8), inset 0 0 40px rgba(78,140,150,0.15);
        }
        .screen-inner {
          position: absolute; inset: 0;
          display: flex; align-items: center; justify-content: center;
          background: radial-gradient(circle at center, rgba(78,140,150,0.12), transparent 70%);
        }
        .scanlines {
          position: absolute; inset: 0;
          background: repeating-linear-gradient(0deg, rgba(0,0,0,0.15) 0px, rgba(0,0,0,0.15) 1px, transparent 1px, transparent 3px);
          pointer-events: none;
        }
        .screen-glow {
          position: absolute; inset: 0;
          background: radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.4) 100%);
          pointer-events: none;
        }
        .cab-badge {
          position: absolute;
          top: 8px; left: 8px;
          padding: 3px 8px;
          background: rgba(0,0,0,0.6);
          font-family: 'Press Start 2P', monospace;
          font-size: 7px;
          letter-spacing: 1px;
          border-radius: 3px;
          z-index: 2;
          text-shadow: 0 0 4px currentColor;
        }
        .cab-badge[data-cat="TRIVIA"] { color: var(--neon-coral); border: 1px solid var(--neon-coral); }
        .cab-badge[data-cat="TEAM"]   { color: var(--neon-sage);  border: 1px solid var(--neon-sage); }
        .cab-badge[data-cat="SOLO"]   { color: var(--neon-mustard); border: 1px solid var(--neon-mustard); }
        .cab-badge[data-cat="COOP"]   { color: #A7C9E8; border: 1px solid #A7C9E8; }
        .cab-badge[data-cat="REVIEW"] { color: #C5A8E8; border: 1px solid #C5A8E8; }
        .cab-soon {
          position: absolute;
          top: 8px; right: 8px;
          padding: 3px 8px;
          background: rgba(218,176,78,0.85);
          color: #2A1D1F;
          font-family: 'Press Start 2P', monospace;
          font-size: 7px;
          letter-spacing: 1px;
          border-radius: 3px;
          z-index: 2;
        }

        .control-panel {
          padding: 14px 16px 18px;
          background: linear-gradient(180deg, var(--cabinet) 0%, var(--cabinet-dark) 100%);
          display: flex;
          flex-direction: column;
          gap: 10px;
          border-top: 2px solid var(--cabinet-wood);
        }
        .game-desc {
          font-family: 'Press Start 2P', monospace;
          font-size: 8px;
          color: rgba(255,255,255,0.65);
          line-height: 1.6;
          letter-spacing: 0.5px;
          text-align: center;
        }
        .cabinet-meta {
          display: flex;
          justify-content: space-between;
          gap: 6px;
        }
        .meta-pill {
          flex: 1;
          text-align: center;
          padding: 4px 6px;
          border-radius: 4px;
          background: rgba(255,255,255,0.08);
          border: 1px solid rgba(255,255,255,0.12);
          font-family: 'Press Start 2P', monospace;
          font-size: 7px;
          color: var(--neon-sage);
          letter-spacing: 1px;
        }

        .coin-btn {
          margin-top: 4px;
          padding: 10px 8px;
          border: none;
          border-radius: 6px;
          background: linear-gradient(180deg, #D86C52 0%, #b85540 100%);
          color: white;
          font-family: 'Press Start 2P', monospace;
          font-size: 10px;
          letter-spacing: 1.5px;
          cursor: pointer;
          box-shadow: 0 3px 0 #8B3E2C, 0 0 12px rgba(216,108,82,0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: all 0.1s;
          text-shadow: 1px 1px 0 rgba(0,0,0,0.3);
        }
        .coin-btn:hover:not(:disabled) {
          background: linear-gradient(180deg, #E8956E 0%, #D86C52 100%);
          transform: translateY(1px);
          box-shadow: 0 2px 0 #8B3E2C, 0 0 16px rgba(216,108,82,0.6);
        }
        .coin-btn:active:not(:disabled) {
          transform: translateY(3px);
          box-shadow: 0 0 0 #8B3E2C;
        }
        .coin-btn:disabled {
          background: linear-gradient(180deg, #555 0%, #333 100%);
          color: rgba(255,255,255,0.5);
          box-shadow: 0 3px 0 #222;
          cursor: not-allowed;
        }
        .coin-icon {
          font-size: 14px;
          color: var(--bulb-on);
          text-shadow: 0 0 6px var(--bulb-on);
          animation: coinSpin 2s infinite;
        }
        .coin-btn:disabled .coin-icon { color: #777; text-shadow: none; animation: none; }
        @keyframes coinSpin {
          0%, 100% { transform: scaleX(1); }
          50% { transform: scaleX(0.3); }
        }

        /* ── Sessions ── */
        .sessions-panel {
          margin-top: 36px;
          padding: 20px;
          background: var(--warm-card, white);
          border: 1px solid var(--border, #E8DDD0);
          border-radius: 12px;
        }
        .sessions-title {
          font-family: 'Press Start 2P', monospace;
          font-size: 11px;
          color: #D86C52;
          letter-spacing: 2px;
          margin-bottom: 16px;
        }
        .sessions-empty {
          text-align: center;
          font-size: 13px;
          color: var(--text-light, #9B8B8E);
          padding: 24px 0;
        }
        .sessions-table { display: flex; flex-direction: column; gap: 6px; }
        .session-row {
          display: grid;
          grid-template-columns: 2fr 120px 100px 120px 140px;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          background: var(--cream, #FAF5ED);
          border: 1px solid var(--border, #E8DDD0);
          border-radius: 8px;
          font-size: 12px;
        }
        .session-name { font-weight: 700; color: var(--text-dark, #3D2C2E); }
        .session-pin {
          font-family: 'Press Start 2P', monospace;
          font-size: 11px;
          color: #D86C52;
          letter-spacing: 2px;
        }
        .session-status {
          font-family: 'Press Start 2P', monospace;
          font-size: 8px;
          text-transform: uppercase;
          padding: 4px 8px;
          border-radius: 4px;
          text-align: center;
          letter-spacing: 1px;
        }
        .session-status.status-lobby    { background: rgba(59,130,246,0.1); color: #3B82F6; border: 1px solid #3B82F6; }
        .session-status.status-playing  { background: rgba(216,108,82,0.1); color: #D86C52; border: 1px solid #D86C52; }
        .session-status.status-finished { background: rgba(22,163,74,0.1); color: #16A34A; border: 1px solid #16A34A; }
        .session-date { color: var(--text-light, #9B8B8E); font-size: 11px; }
        .session-replay {
          font-family: 'Press Start 2P', monospace;
          font-size: 8px;
          letter-spacing: 1px;
          padding: 6px 10px;
          border: 2px solid #6BA08A;
          background: rgba(107,160,138,0.08);
          color: #6BA08A;
          border-radius: 4px;
          cursor: pointer;
        }
        .session-replay:hover:not(:disabled) {
          background: #6BA08A;
          color: white;
        }
        .session-replay:disabled { opacity: 0.5; cursor: not-allowed; }

        @media (max-width: 700px) {
          .arcade-title { font-size: 24px; }
          .session-row { grid-template-columns: 1fr; text-align: left; }
        }
      `}</style>
    </div>
  );
}

