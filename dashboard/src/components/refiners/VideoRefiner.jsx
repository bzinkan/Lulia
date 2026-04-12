'use client';
import { useState } from 'react';
import { CheckCircle } from 'lucide-react';
import AccommodationPicker from './AccommodationPicker';

export default function VideoRefiner({ workOrder, dayTitle, onConfirm }) {
  const initialTopic = workOrder.config?.topic || workOrder.title || dayTitle || '';
  const initialMin = Math.round(((workOrder.config?.target_length_sec) || 180) / 60);
  const [topic, setTopic] = useState(initialTopic);
  const [lengthMin, setLengthMin] = useState(initialMin);
  const [accommodations, setAccommodations] = useState(workOrder.accommodations || []);

  function handleConfirm() {
    onConfirm({
      ...workOrder,
      config: {
        ...(workOrder.config || {}),
        topic,
        target_length_sec: Math.max(30, lengthMin * 60),
      },
      accommodations,
      confirmed: true,
    });
  }

  return (
    <div>
      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Topic</label>
        <input value={topic} onChange={e => setTopic(e.target.value)}
          placeholder={dayTitle || 'What is this video about?'}
          className="w-full px-3 py-2 rounded-xl text-[13px]"
          style={{ border: '1px solid var(--border)', background: 'white' }} />
      </div>
      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
          Target length (minutes)
        </label>
        <input type="number" min="1" max="15" step="1" value={lengthMin}
          onChange={e => setLengthMin(parseInt(e.target.value) || 3)}
          className="w-full px-3 py-2 rounded-xl text-[13px]"
          style={{ border: '1px solid var(--border)', background: 'white' }} />
        <p className="text-[11px] mt-1" style={{ color: 'var(--text-light)' }}>
          We generate the video from scratch — script, narration, and slides.
        </p>
      </div>

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}>
        <CheckCircle className="w-4 h-4" /> Confirm Video
      </button>
    </div>
  );
}
