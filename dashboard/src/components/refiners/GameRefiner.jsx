'use client';
import { useState } from 'react';
import { CheckCircle } from 'lucide-react';
import { GAME_FORMATS, DIFFICULTY_LEVELS } from '@/lib/plannerVariants';
import AccommodationPicker from './AccommodationPicker';

export default function GameRefiner({ workOrder, onConfirm }) {
  const [format, setFormat] = useState(workOrder.config?.format || 'jeopardy');
  const [duration, setDuration] = useState(workOrder.config?.duration_minutes || 15);
  const [difficulty, setDifficulty] = useState(workOrder.config?.difficulty || 'medium');
  const [accommodations, setAccommodations] = useState(workOrder.accommodations || []);

  function handleConfirm() {
    onConfirm({
      ...workOrder,
      variant: format,
      config: { ...(workOrder.config || {}), format, duration_minutes: duration, difficulty },
      accommodations,
      confirmed: true,
    });
  }

  return (
    <div>
      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Format</label>
        <div className="grid grid-cols-3 gap-2">
          {GAME_FORMATS.map(f => (
            <button key={f.id} onClick={() => setFormat(f.id)}
              className="p-2 rounded-lg text-[12px] font-semibold"
              style={{
                background: format === f.id ? 'rgba(216,108,82,0.08)' : 'var(--cream)',
                border: format === f.id ? '2px solid var(--coral)' : '1px solid var(--border)',
                color: 'var(--text-dark)', cursor: 'pointer',
              }}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Duration (min)</label>
          <input type="number" min="5" max="60" value={duration}
            onChange={e => setDuration(parseInt(e.target.value) || 15)}
            className="w-full px-3 py-2 rounded-xl text-[13px]"
            style={{ border: '1px solid var(--border)', background: 'white' }} />
        </div>
        <div>
          <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Difficulty</label>
          <select value={difficulty} onChange={e => setDifficulty(e.target.value)}
            className="w-full px-3 py-2 rounded-xl text-[13px]"
            style={{ border: '1px solid var(--border)', background: 'white' }}>
            {DIFFICULTY_LEVELS.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}
          </select>
        </div>
      </div>

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}>
        <CheckCircle className="w-4 h-4" /> Confirm Game
      </button>
    </div>
  );
}
