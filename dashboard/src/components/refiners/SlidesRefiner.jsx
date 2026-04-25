'use client';
import { useState } from 'react';
import { CheckCircle, Plus, X, ArrowUp, ArrowDown } from 'lucide-react';
import { SLIDES_LAYOUTS } from '@/lib/plannerVariants';
import AccommodationPicker from './AccommodationPicker';

export default function SlidesRefiner({ workOrder, onConfirm, classDefaultAccommodations = [] }) {
  const [layout, setLayout] = useState(workOrder.config?.layout_style || 'lecture');
  const [outline, setOutline] = useState(
    workOrder.config?.outline?.length
      ? workOrder.config.outline
      : [
          { title: 'Warm-up' },
          { title: 'Introduce concept' },
          { title: 'Guided example' },
          { title: 'Student practice' },
          { title: 'Wrap-up & exit' },
        ]
  );
  const [accommodations, setAccommodations] = useState(
    // A work order carries its own accommodations once the teacher
    // confirms it. Before that, fall back to the class-level default
    // (e.g. "ELL-Beginner on every lesson") so teachers don't have to
    // tick the same boxes on every work order.
    (workOrder.accommodations && workOrder.accommodations.length > 0)
      ? workOrder.accommodations
      : classDefaultAccommodations,
  );

  function updateSlide(i, title) {
    const next = [...outline]; next[i] = { ...next[i], title }; setOutline(next);
  }
  function removeSlide(i) { setOutline(outline.filter((_, idx) => idx !== i)); }
  function addSlide() { setOutline([...outline, { title: 'New slide' }]); }
  function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= outline.length) return;
    const next = [...outline];
    [next[i], next[j]] = [next[j], next[i]];
    setOutline(next);
  }

  function handleConfirm() {
    onConfirm({
      ...workOrder,
      variant: layout,
      config: { ...(workOrder.config || {}), outline, layout_style: layout },
      accommodations,
      confirmed: true,
    });
  }

  return (
    <div>
      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
          Layout style
        </label>
        <select
          value={layout}
          onChange={e => setLayout(e.target.value)}
          className="w-full px-3 py-2 rounded-xl text-[13px]"
          style={{ border: '1px solid var(--border)', background: 'white' }}
        >
          {SLIDES_LAYOUTS.map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
        </select>
      </div>

      <div className="mb-2 flex items-center justify-between">
        <label className="text-[12px] font-bold" style={{ color: 'var(--text-mid)' }}>Slide outline</label>
        <button onClick={addSlide} className="text-[12px] font-semibold flex items-center gap-1"
          style={{ color: 'var(--coral)', background: 'none', border: 'none', cursor: 'pointer' }}>
          <Plus className="w-3.5 h-3.5" /> Add slide
        </button>
      </div>
      <div className="space-y-1.5 max-h-[240px] overflow-y-auto">
        {outline.map((s, i) => (
          <div key={i} className="flex items-center gap-2 p-2 rounded-lg"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
            <span className="text-[11px] font-bold w-5" style={{ color: 'var(--text-light)' }}>{i + 1}</span>
            <input
              value={s.title}
              onChange={e => updateSlide(i, e.target.value)}
              className="flex-1 px-2 py-1 rounded-md text-[12px]"
              style={{ border: '1px solid var(--border)', background: 'white' }}
            />
            <button onClick={() => move(i, -1)} disabled={i === 0}
              style={{ background: 'none', border: 'none', cursor: 'pointer', opacity: i === 0 ? 0.3 : 0.7 }}>
              <ArrowUp className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => move(i, 1)} disabled={i === outline.length - 1}
              style={{ background: 'none', border: 'none', cursor: 'pointer', opacity: i === outline.length - 1 ? 0.3 : 0.7 }}>
              <ArrowDown className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => removeSlide(i)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444' }}>
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}>
        <CheckCircle className="w-4 h-4" /> Confirm Slide Outline
      </button>
    </div>
  );
}
