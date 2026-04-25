'use client';
import { useState } from 'react';
import { CheckCircle, Sparkles } from 'lucide-react';
import { INTERACTIVE_TYPES } from '@/lib/plannerVariants';
import AccommodationPicker from './AccommodationPicker';

export default function InteractiveRefiner({ workOrder, onConfirm, classDefaultAccommodations = [] }) {
  const aiSuggested = workOrder.config?.activity_type || workOrder.variant || 'matching';
  const [mode, setMode] = useState('ai'); // 'ai' | 'pick' | 'custom'
  const [activityType, setActivityType] = useState(aiSuggested);
  const [prompt, setPrompt] = useState(workOrder.config?.prompt || '');
  const [accommodations, setAccommodations] = useState(
    // A work order carries its own accommodations once the teacher
    // confirms it. Before that, fall back to the class-level default
    // (e.g. "ELL-Beginner on every lesson") so teachers don't have to
    // tick the same boxes on every work order.
    (workOrder.accommodations && workOrder.accommodations.length > 0)
      ? workOrder.accommodations
      : classDefaultAccommodations,
  );

  function handleConfirm() {
    let type = activityType;
    let p = prompt;
    if (mode === 'ai') { type = aiSuggested; p = workOrder.config?.prompt || ''; }
    onConfirm({
      ...workOrder,
      variant: type,
      config: { ...(workOrder.config || {}), activity_type: type, prompt: p },
      accommodations,
      confirmed: true,
    });
  }

  const tabStyle = (active) => ({
    flex: 1, padding: '8px 12px', borderRadius: '10px',
    background: active ? 'var(--sage)' : 'var(--cream)',
    color: active ? 'white' : 'var(--text-mid)',
    border: '1px solid var(--border)', cursor: 'pointer',
    fontSize: '12px', fontWeight: 600,
  });

  const suggestedLabel = INTERACTIVE_TYPES.find(t => t.id === aiSuggested)?.label || aiSuggested;

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <button onClick={() => setMode('ai')} style={tabStyle(mode === 'ai')}>Accept AI pick</button>
        <button onClick={() => setMode('pick')} style={tabStyle(mode === 'pick')}>Pick different</button>
        <button onClick={() => setMode('custom')} style={tabStyle(mode === 'custom')}>Describe it</button>
      </div>

      {mode === 'ai' && (
        <div className="p-3 rounded-xl flex items-start gap-3"
          style={{ background: 'rgba(107,160,138,0.08)', border: '1px solid var(--sage)' }}>
          <Sparkles className="w-4 h-4 mt-0.5" style={{ color: 'var(--sage)' }} />
          <div>
            <p className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
              AI suggests: {suggestedLabel}
            </p>
            {workOrder.config?.prompt && (
              <p className="text-[12px] mt-1" style={{ color: 'var(--text-mid)' }}>
                {workOrder.config.prompt}
              </p>
            )}
          </div>
        </div>
      )}

      {mode === 'pick' && (
        <div className="grid grid-cols-2 gap-2">
          {INTERACTIVE_TYPES.map(t => (
            <button key={t.id} onClick={() => setActivityType(t.id)}
              className="p-2.5 rounded-lg text-[12px] font-semibold text-left"
              style={{
                background: activityType === t.id ? 'rgba(216,108,82,0.08)' : 'var(--cream)',
                border: activityType === t.id ? '2px solid var(--coral)' : '1px solid var(--border)',
                color: 'var(--text-dark)', cursor: 'pointer',
              }}>
              {t.label}
            </button>
          ))}
        </div>
      )}

      {mode === 'custom' && (
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          rows={4}
          placeholder="Describe the activity you want..."
          className="w-full px-3 py-2 rounded-xl text-[13px]"
          style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
        />
      )}

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}>
        <CheckCircle className="w-4 h-4" /> Confirm
      </button>
    </div>
  );
}
