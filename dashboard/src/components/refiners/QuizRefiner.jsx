'use client';
import { useState } from 'react';
import { CheckCircle } from 'lucide-react';
import AccommodationPicker from './AccommodationPicker';

export default function QuizRefiner({ workOrder, onConfirm, classDefaultAccommodations = [] }) {
  const [questionCount, setQuestionCount] = useState(workOrder.config?.question_count || workOrder.question_count || 10);
  const [recall, setRecall] = useState(workOrder.config?.blueprint?.recall ?? 40);
  const [apply, setApply] = useState(workOrder.config?.blueprint?.apply ?? 40);
  const [analyze, setAnalyze] = useState(workOrder.config?.blueprint?.analyze ?? 20);
  const [standards, setStandards] = useState(workOrder.standards || []);
  const [accommodations, setAccommodations] = useState(
    // A work order carries its own accommodations once the teacher
    // confirms it. Before that, fall back to the class-level default
    // (e.g. "ELL-Beginner on every lesson") so teachers don't have to
    // tick the same boxes on every work order.
    (workOrder.accommodations && workOrder.accommodations.length > 0)
      ? workOrder.accommodations
      : classDefaultAccommodations,
  );

  const total = recall + apply + analyze;

  function handleConfirm() {
    onConfirm({
      ...workOrder,
      config: {
        ...(workOrder.config || {}),
        question_count: questionCount,
        blueprint: { recall, apply, analyze },
      },
      standards,
      accommodations,
      confirmed: true,
    });
  }

  function toggleStandard(code) {
    setStandards(prev => prev.includes(code) ? prev.filter(s => s !== code) : [...prev, code]);
  }

  return (
    <div>
      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Question count</label>
        <input type="number" min="1" max="50" value={questionCount}
          onChange={e => setQuestionCount(parseInt(e.target.value) || 10)}
          className="w-full px-3 py-2 rounded-xl text-[13px]"
          style={{ border: '1px solid var(--border)', background: 'white' }} />
      </div>

      <div className="mb-3">
        <label className="block text-[12px] font-bold mb-2" style={{ color: 'var(--text-mid)' }}>
          Blueprint {total !== 100 && <span style={{ color: '#EF4444' }}>({total}% — should total 100)</span>}
        </label>
        <div className="space-y-2">
          {[
            { label: 'Recall', value: recall, set: setRecall },
            { label: 'Apply', value: apply, set: setApply },
            { label: 'Analyze', value: analyze, set: setAnalyze },
          ].map(row => (
            <div key={row.label} className="flex items-center gap-2">
              <span className="text-[12px] w-16" style={{ color: 'var(--text-mid)' }}>{row.label}</span>
              <input type="range" min="0" max="100" value={row.value}
                onChange={e => row.set(parseInt(e.target.value))}
                className="flex-1" style={{ accentColor: 'var(--coral)' }} />
              <span className="text-[12px] font-bold w-10 text-right" style={{ color: 'var(--text-dark)' }}>{row.value}%</span>
            </div>
          ))}
        </div>
      </div>

      {(workOrder.standards_pool || workOrder.standards || []).length > 0 && (
        <div className="mb-3">
          <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Standards covered</label>
          <div className="flex flex-wrap gap-1.5">
            {(workOrder.standards_pool || workOrder.standards).map(code => {
              const on = standards.includes(code);
              return (
                <button key={code} onClick={() => toggleStandard(code)}
                  className="text-[10px] px-2 py-1 rounded-full font-semibold"
                  style={{
                    background: on ? 'rgba(216,108,82,0.12)' : 'var(--cream)',
                    color: on ? 'var(--coral)' : 'var(--text-light)',
                    border: `1px solid ${on ? 'var(--coral)' : 'var(--border)'}`,
                    cursor: 'pointer',
                  }}>
                  {code}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <AccommodationPicker value={accommodations} onChange={setAccommodations} />

      <button onClick={handleConfirm}
        className="mt-4 w-full py-2.5 rounded-xl font-semibold text-[13px] text-white flex items-center justify-center gap-2"
        style={{ background: 'var(--sage)' }}>
        <CheckCircle className="w-4 h-4" /> Confirm Quiz
      </button>
    </div>
  );
}
