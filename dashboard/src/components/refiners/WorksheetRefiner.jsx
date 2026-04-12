'use client';
import { useState } from 'react';
import { CheckCircle } from 'lucide-react';
import { worksheetVariantsFor } from '@/lib/plannerVariants';
import AccommodationPicker from './AccommodationPicker';

export default function WorksheetRefiner({ workOrder, subject, onConfirm }) {
  const groups = worksheetVariantsFor(subject);
  const [variant, setVariant] = useState(workOrder.variant || groups[0].items[0].id);
  const [questionCount, setQuestionCount] = useState(workOrder.config?.question_count || workOrder.question_count || 10);
  const [includeAnswerKey, setIncludeAnswerKey] = useState(workOrder.config?.include_answer_key ?? true);
  const [accommodations, setAccommodations] = useState(workOrder.accommodations || []);

  function handleConfirm() {
    onConfirm({
      ...workOrder,
      variant,
      config: { ...(workOrder.config || {}), question_count: questionCount, include_answer_key: includeAnswerKey },
      accommodations,
      confirmed: true,
    });
  }

  return (
    <div>
      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
          Worksheet Type
        </label>
        <select
          value={variant}
          onChange={e => setVariant(e.target.value)}
          className="w-full px-3 py-2 rounded-xl text-[13px]"
          style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
        >
          {groups.map(g => (
            <optgroup key={g.group} label={g.group}>
              {g.items.map(opt => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
            Question count
          </label>
          <input
            type="number"
            min="1"
            max="50"
            value={questionCount}
            onChange={e => setQuestionCount(parseInt(e.target.value) || 10)}
            className="w-full px-3 py-2 rounded-xl text-[13px]"
            style={{ border: '1px solid var(--border)', background: 'white' }}
          />
        </div>
        <label className="flex items-end gap-2 pb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={includeAnswerKey}
            onChange={e => setIncludeAnswerKey(e.target.checked)}
            style={{ accentColor: 'var(--coral)' }}
          />
          <span className="text-[12px] font-semibold" style={{ color: 'var(--text-dark)' }}>
            Include answer key
          </span>
        </label>
      </div>

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button
        onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}
      >
        <CheckCircle className="w-4 h-4" /> Confirm
      </button>
    </div>
  );
}
