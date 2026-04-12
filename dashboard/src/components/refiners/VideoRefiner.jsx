'use client';
import { useEffect, useState } from 'react';
import { CheckCircle, Film, AlertTriangle } from 'lucide-react';
import AccommodationPicker from './AccommodationPicker';
import { apiFetch } from '@/lib/api';

/**
 * Short Clip refiner for Planner work orders.
 *
 * Teacher sets topic + duration, sees live credit cost based on duration
 * (fetched from /clips/cost). Confirming stores everything on the work
 * order; the actual Veo generation + credit charge happens during
 * approve_plan() on the backend so the teacher isn't double-charged.
 */
export default function VideoRefiner({ workOrder, dayTitle, onConfirm }) {
  const initialTopic = workOrder.config?.topic || workOrder.title || dayTitle || '';
  const initialSec = workOrder.config?.duration_sec || 30;
  const teacherId = '00000000-0000-0000-0000-000000000001';

  const [topic, setTopic] = useState(initialTopic);
  const [duration, setDuration] = useState(initialSec);
  const [accommodations, setAccommodations] = useState(workOrder.accommodations || []);
  const [cost, setCost] = useState(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch(`/api/v1/clips/cost?duration_sec=${duration}&teacher_id=${teacherId}`)
      .then(d => { if (!cancelled) setCost(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [duration]);

  function handleConfirm() {
    onConfirm({
      ...workOrder,
      output_template_id: 'short_clip',  // swap from 'video' → 'short_clip' so dispatcher routes to Veo
      config: {
        ...(workOrder.config || {}),
        topic,
        duration_sec: duration,
      },
      accommodations,
      confirmed: true,
    });
  }

  const warning = cost?.warning;
  const warnColor = warning?.level === 'red' ? '#B91C1C'
                  : warning?.level === 'yellow' ? '#B45309'
                  : 'var(--sage)';
  const warnBg = warning?.level === 'red' ? 'rgba(239,68,68,0.08)'
               : warning?.level === 'yellow' ? 'rgba(245,158,11,0.08)'
               : 'rgba(107,160,138,0.08)';

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 p-2.5 rounded-lg"
        style={{ background: 'rgba(216,108,82,0.06)', border: '1px solid rgba(216,108,82,0.25)' }}>
        <Film className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--coral)' }} />
        <span className="text-[11px]" style={{ color: 'var(--text-mid)' }}>
          Short Clip — AI-generated video via Veo 3 Fast. Charges credits at generation time.
        </span>
      </div>

      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Topic</label>
        <input value={topic} onChange={e => setTopic(e.target.value)}
          placeholder={dayTitle || 'What is this clip about?'}
          className="w-full px-3 py-2 rounded-xl text-[13px]"
          style={{ border: '1px solid var(--border)', background: 'white' }} />
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <label className="text-[12px] font-bold" style={{ color: 'var(--text-mid)' }}>Duration</label>
          <span className="text-[13px] font-bold" style={{ color: 'var(--coral)' }}>{duration} sec</span>
        </div>
        <input type="range" min="5" max="120" step="5" value={duration}
          onChange={e => setDuration(parseInt(e.target.value))}
          className="w-full" style={{ accentColor: 'var(--coral)' }} />
        <div className="flex justify-between text-[9px]" style={{ color: 'var(--text-light)' }}>
          <span>5s</span><span>30s</span><span>60s</span><span>120s</span>
        </div>
      </div>

      {cost && (
        <div className="p-3 rounded-xl mb-3"
          style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
          <div className="flex justify-between text-[12px]">
            <span style={{ color: 'var(--text-mid)' }}>Credits to generate</span>
            <span className="font-bold" style={{ color: 'var(--coral)' }}>{cost.credits_needed}</span>
          </div>
          <div className="flex justify-between text-[11px] mt-1">
            <span style={{ color: 'var(--text-light)' }}>Your balance</span>
            <span style={{ color: 'var(--text-light)' }}>{cost.balance.total} credits</span>
          </div>
        </div>
      )}

      {warning && (
        <div className="p-2 rounded-lg flex items-start gap-2 text-[11px] mb-3"
          style={{ background: warnBg, border: `1px solid ${warnColor}`, color: warnColor }}>
          <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
          <span>{warning.label}</span>
        </div>
      )}

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}>
        <CheckCircle className="w-4 h-4" /> Confirm Clip
      </button>
    </div>
  );
}
