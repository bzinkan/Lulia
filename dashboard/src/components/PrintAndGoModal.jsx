'use client';
import { useState, useEffect, useRef } from 'react';
import { X, Loader2, Printer, Sparkles, CheckCircle, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api';
import { worksheetVariantsFor } from '@/lib/plannerVariants';

/**
 * Print & Go — single-shot assignment generator.
 *
 * Defaults pulled from the active class. Teacher provides:
 *   - Template (worksheet / quiz / exit_ticket / etc.)
 *   - Topic (free text — debounced standard auto-match)
 *   - Question count
 *
 * No accommodations, no preview, no scheduling — just generate now.
 * For depth, teachers should use the Planner.
 */
export default function PrintAndGoModal({ activeClass, onClose, onCreated }) {
  const groups = worksheetVariantsFor(activeClass?.subject || '');
  const [template, setTemplate] = useState('worksheet');
  const [topic, setTopic] = useState('');
  const [questionCount, setQuestionCount] = useState(10);
  const [matched, setMatched] = useState([]);
  const [matching, setMatching] = useState(false);
  const [matchMethod, setMatchMethod] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);

  // Debounced live standards match as the teacher types
  useEffect(() => {
    if (!topic.trim() || topic.trim().length < 3) {
      setMatched([]); setMatchMethod(null); return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setMatching(true);
      try {
        const params = new URLSearchParams({ topic, limit: '3' });
        if (activeClass?.subject) params.set('subject', activeClass.subject);
        if (activeClass?.grade_level) params.set('grade', activeClass.grade_level);
        if (activeClass?.state_code) params.set('state_code', activeClass.state_code);
        const data = await apiFetch(`/api/v1/standards/match?${params.toString()}`);
        setMatched(data.matches || []);
        setMatchMethod(data.method);
      } catch (e) {
        setMatched([]);
      } finally {
        setMatching(false);
      }
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [topic, activeClass?.subject, activeClass?.grade_level, activeClass?.state_code]);

  function toggleMatched(code) {
    setMatched(prev => prev.map(m => m.code === code ? { ...m, _excluded: !m._excluded } : m));
  }

  async function handleGenerate() {
    if (!topic.trim()) { setError('Topic is required.'); return; }
    setGenerating(true); setError(null);
    try {
      const standards_ids = matched.filter(m => !m._excluded).map(m => m.code);
      const data = await apiFetch('/api/v1/assignments/generate', {
        method: 'POST',
        body: JSON.stringify({
          work_order_id: `PG-${Date.now()}`,
          class_id: activeClass?.class_id,
          teacher_id: activeClass?.teacher_id,
          subject: activeClass?.subject || 'General',
          grade_level: activeClass?.grade_level || '4',
          output_template_id: template,
          design_theme: activeClass?.design_theme || 'modern_clean',
          question_count: questionCount,
          standards_ids,
          difficulty_distribution: { easy: 3, medium: 4, hard: 3 },
          has_kb_coverage: true,
          // Pass topic as a content hint
          topic_hint: topic,
        }),
      });
      setResult(data);
      onCreated?.(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-lg mx-4"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2">
            <Printer className="w-5 h-5" style={{ color: 'var(--coral)' }} />
            <div>
              <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>Print &amp; Go</h3>
              <p className="text-[12px]" style={{ color: 'var(--text-light)' }}>
                {activeClass ? `${activeClass.name} · Grade ${activeClass.grade_level} ${activeClass.subject}` : 'Quick one-off assignment'}
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-light)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        {!result ? (
          <div className="p-5 space-y-4">
            <div>
              <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Template</label>
              <select value={template} onChange={e => setTemplate(e.target.value)}
                className="w-full px-3 py-2 rounded-xl text-[13px]"
                style={{ border: '1px solid var(--border)', background: 'white' }}>
                {groups.map(g => (
                  <optgroup key={g.group} label={g.group}>
                    {g.items.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
                  </optgroup>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
                Topic
              </label>
              <input value={topic} onChange={e => setTopic(e.target.value)} autoFocus
                placeholder="e.g. Multiplication facts 6×7 to 9×9"
                className="w-full px-3 py-2 rounded-xl text-[13px]"
                style={{ border: '1px solid var(--border)', background: 'white' }} />

              {/* Live standards chips */}
              {(matching || matched.length > 0) && (
                <div className="mt-2 flex items-center gap-2 flex-wrap">
                  {matching && (
                    <span className="text-[11px] flex items-center gap-1" style={{ color: 'var(--text-light)' }}>
                      <Loader2 className="w-3 h-3 animate-spin" /> Matching standards…
                    </span>
                  )}
                  {!matching && matched.length === 0 && topic.trim().length >= 3 && (
                    <span className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                      No matching standards — assignment will generate without alignment.
                    </span>
                  )}
                  {matched.map(m => (
                    <button key={m.code} onClick={() => toggleMatched(m.code)} title={m.description}
                      className="text-[10px] px-2 py-1 rounded-full font-semibold flex items-center gap-1"
                      style={{
                        background: m._excluded ? 'var(--cream)' : 'rgba(216,108,82,0.12)',
                        color: m._excluded ? 'var(--text-light)' : 'var(--coral)',
                        border: `1px solid ${m._excluded ? 'var(--border)' : 'var(--coral)'}`,
                        textDecoration: m._excluded ? 'line-through' : 'none',
                        cursor: 'pointer',
                      }}>
                      {!m._excluded && <CheckCircle className="w-2.5 h-2.5" />}
                      {m.code}
                    </button>
                  ))}
                  {matched.length > 0 && matchMethod === 'haiku' && (
                    <span className="text-[10px] flex items-center gap-1" style={{ color: 'var(--text-light)' }}>
                      <Sparkles className="w-2.5 h-2.5" /> AI-matched
                    </span>
                  )}
                </div>
              )}
            </div>

            <div>
              <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>Question count</label>
              <input type="number" min="1" max="50" value={questionCount}
                onChange={e => setQuestionCount(parseInt(e.target.value) || 10)}
                className="w-full px-3 py-2 rounded-xl text-[13px]"
                style={{ border: '1px solid var(--border)', background: 'white' }} />
            </div>

            {error && (
              <div className="p-2.5 rounded-lg text-[12px]"
                style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#EF4444' }}>
                {error}
              </div>
            )}

            <p className="text-[11px]" style={{ color: 'var(--text-light)' }}>
              Need to plan a whole week or set accommodations? Use <Link href="/planner" className="font-semibold" style={{ color: 'var(--coral)' }}>Planner</Link> instead.
            </p>
          </div>
        ) : (
          <div className="p-5">
            <div className="rounded-xl p-4 mb-3 flex items-center gap-3"
              style={{ background: 'rgba(22,163,74,0.08)', border: '1px solid #16A34A' }}>
              <CheckCircle className="w-5 h-5" style={{ color: '#16A34A' }} />
              <div>
                <p className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
                  {result.title || 'Assignment created'}
                </p>
                <p className="text-[11px]" style={{ color: 'var(--text-mid)' }}>
                  Ready to print or assign.
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Link href={`/assignments/${result.assignment_id}`}
                className="flex-1 py-2.5 rounded-xl text-[13px] font-semibold text-white text-center flex items-center justify-center gap-2"
                style={{ background: 'var(--coral)' }}>
                <ExternalLink className="w-4 h-4" /> Open Assignment
              </Link>
              <button onClick={() => { setResult(null); setTopic(''); setMatched([]); }}
                className="px-4 py-2.5 rounded-xl text-[13px] font-semibold"
                style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
                Make Another
              </button>
            </div>
          </div>
        )}

        {/* Footer */}
        {!result && (
          <div className="p-5 flex justify-end gap-2" style={{ borderTop: '1px solid var(--border)' }}>
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold"
              style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
              Cancel
            </button>
            <button onClick={handleGenerate} disabled={generating || !topic.trim()}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2 disabled:opacity-50"
              style={{ background: 'var(--coral)' }}>
              {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</> : <><Printer className="w-4 h-4" /> Generate</>}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
