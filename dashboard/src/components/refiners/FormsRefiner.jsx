'use client';
import { useState } from 'react';
import { CheckCircle, Plus, X, Info } from 'lucide-react';
import { FORM_QUESTION_TYPES } from '@/lib/plannerVariants';
import AccommodationPicker from './AccommodationPicker';

function blankQ() {
  return { stem: '', type: 'mcq', choices: ['', '', '', ''], points: 1 };
}

export default function FormsRefiner({ workOrder, onConfirm }) {
  const [questions, setQuestions] = useState(
    workOrder.config?.questions?.length ? workOrder.config.questions : Array.from({ length: 5 }, blankQ)
  );
  const [shuffle, setShuffle] = useState(workOrder.config?.shuffle ?? true);
  const [accommodations, setAccommodations] = useState(workOrder.accommodations || []);

  function update(i, patch) {
    const next = [...questions]; next[i] = { ...next[i], ...patch }; setQuestions(next);
  }
  function updateChoice(qi, ci, val) {
    const next = [...questions];
    const choices = [...(next[qi].choices || [])];
    choices[ci] = val;
    next[qi] = { ...next[qi], choices };
    setQuestions(next);
  }
  function remove(i) { setQuestions(questions.filter((_, idx) => idx !== i)); }
  function add() { setQuestions([...questions, blankQ()]); }

  function handleConfirm() {
    onConfirm({
      ...workOrder,
      config: { ...(workOrder.config || {}), questions, shuffle },
      accommodations,
      confirmed: true,
    });
  }

  return (
    <div>
      {accommodations.length > 0 && (
        <div className="mb-3 p-2.5 rounded-lg flex items-start gap-2"
          style={{ background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)' }}>
          <Info className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#3B82F6' }} />
          <p className="text-[11px]" style={{ color: 'var(--text-mid)' }}>
            Forms can't be modified per student — each accommodation you tick will be generated as a separate parallel Form linked to this assignment.
          </p>
        </div>
      )}

      <div className="mb-2 flex items-center justify-between">
        <label className="text-[12px] font-bold" style={{ color: 'var(--text-mid)' }}>Questions</label>
        <button onClick={add} className="text-[12px] font-semibold flex items-center gap-1"
          style={{ color: 'var(--coral)', background: 'none', border: 'none', cursor: 'pointer' }}>
          <Plus className="w-3.5 h-3.5" /> Add question
        </button>
      </div>

      <div className="space-y-2 max-h-[320px] overflow-y-auto">
        {questions.map((q, i) => (
          <div key={i} className="p-3 rounded-lg space-y-2"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold w-6" style={{ color: 'var(--text-light)' }}>Q{i + 1}</span>
              <select value={q.type} onChange={e => update(i, { type: e.target.value })}
                className="px-2 py-1 rounded-md text-[11px]"
                style={{ border: '1px solid var(--border)', background: 'white' }}>
                {FORM_QUESTION_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              <input type="number" min="1" value={q.points}
                onChange={e => update(i, { points: parseInt(e.target.value) || 1 })}
                className="w-14 px-2 py-1 rounded-md text-[11px]"
                style={{ border: '1px solid var(--border)', background: 'white' }}
                title="Points" />
              <button onClick={() => remove(i)} className="ml-auto"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444' }}>
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <input value={q.stem} onChange={e => update(i, { stem: e.target.value })}
              placeholder="Question stem..."
              className="w-full px-2 py-1.5 rounded-md text-[12px]"
              style={{ border: '1px solid var(--border)', background: 'white' }} />
            {(q.type === 'mcq' || q.type === 'checkbox') && (
              <div className="grid grid-cols-2 gap-1.5">
                {(q.choices || []).map((c, ci) => (
                  <input key={ci} value={c} onChange={e => updateChoice(i, ci, e.target.value)}
                    placeholder={`Choice ${ci + 1}`}
                    className="px-2 py-1 rounded-md text-[11px]"
                    style={{ border: '1px solid var(--border)', background: 'white' }} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <label className="mt-3 flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={shuffle} onChange={e => setShuffle(e.target.checked)}
          style={{ accentColor: 'var(--coral)' }} />
        <span className="text-[12px] font-semibold" style={{ color: 'var(--text-dark)' }}>
          Shuffle questions
        </span>
      </label>

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}>
        <CheckCircle className="w-4 h-4" /> Confirm Form
      </button>
    </div>
  );
}
