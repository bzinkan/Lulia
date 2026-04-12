'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { Loader2, Printer, Sparkles, CheckCircle, ExternalLink, Plus } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';
import { worksheetVariantsFor } from '@/lib/plannerVariants';

export default function PrintAndGoPage() {
  const { activeClassId, classes } = useClassContext();
  const activeClass = classes.find(c => c.class_id === activeClassId);
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
      } catch (e) { setMatched([]); }
      finally { setMatching(false); }
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
          topic_hint: topic,
        }),
      });
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setGenerating(false); }
  }

  function reset() {
    setResult(null); setTopic(''); setMatched([]); setError(null);
  }

  return (
    <div className="max-w-[720px] mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <div
          className="w-12 h-12 rounded-[14px] flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, var(--coral), var(--coral-light))', boxShadow: '0 4px 14px rgba(216, 108, 82, 0.3)' }}
        >
          <Printer className="w-6 h-6 text-white" strokeWidth={2.5} />
        </div>
        <div>
          <h1 className="font-serif text-[28px] leading-tight" style={{ color: 'var(--text-dark)' }}>
            Print &amp; Go
          </h1>
          <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
            One worksheet, one minute. No planning required.
          </p>
        </div>
      </div>

      {/* Class context bar */}
      {activeClass && (
        <div className="rounded-card p-3 mb-5 flex items-center justify-between"
          style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
          <span className="text-[12px]" style={{ color: 'var(--text-mid)' }}>
            Generating for <strong style={{ color: 'var(--text-dark)' }}>{activeClass.name}</strong>
            {' '}· Grade {activeClass.grade_level} {activeClass.subject}
          </span>
          <Link href="/planner" className="text-[11px] font-semibold" style={{ color: 'var(--coral)' }}>
            Need a full week? Use Planner →
          </Link>
        </div>
      )}

      {!result ? (
        <div className="rounded-card p-6 space-y-5"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          {/* Template */}
          <div>
            <label className="block text-[13px] font-bold mb-2" style={{ color: 'var(--text-dark)' }}>
              What kind?
            </label>
            <select value={template} onChange={e => setTemplate(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl text-[14px]"
              style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}>
              {groups.map(g => (
                <optgroup key={g.group} label={g.group}>
                  {g.items.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
                </optgroup>
              ))}
            </select>
          </div>

          {/* Topic */}
          <div>
            <label className="block text-[13px] font-bold mb-2" style={{ color: 'var(--text-dark)' }}>
              What's it about?
            </label>
            <input value={topic} onChange={e => setTopic(e.target.value)} autoFocus
              placeholder="e.g. Multiplication facts 6×7 to 9×9"
              className="w-full px-3 py-2.5 rounded-xl text-[14px]"
              style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }} />

            {(matching || matched.length > 0 || (!matching && topic.trim().length >= 3 && matched.length === 0)) && (
              <div className="mt-3 flex items-center gap-2 flex-wrap">
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
                    className="text-[11px] px-2.5 py-1 rounded-full font-semibold flex items-center gap-1.5"
                    style={{
                      background: m._excluded ? 'var(--cream)' : 'rgba(216,108,82,0.12)',
                      color: m._excluded ? 'var(--text-light)' : 'var(--coral)',
                      border: `1px solid ${m._excluded ? 'var(--border)' : 'var(--coral)'}`,
                      textDecoration: m._excluded ? 'line-through' : 'none',
                      cursor: 'pointer',
                    }}>
                    {!m._excluded && <CheckCircle className="w-3 h-3" />}
                    {m.code}
                  </button>
                ))}
                {matched.length > 0 && matchMethod === 'haiku' && (
                  <span className="text-[10px] flex items-center gap-1 px-2 py-0.5 rounded-full"
                    style={{ background: 'rgba(107,160,138,0.1)', color: 'var(--sage)' }}>
                    <Sparkles className="w-2.5 h-2.5" /> AI-matched
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Question count */}
          <div>
            <label className="block text-[13px] font-bold mb-2" style={{ color: 'var(--text-dark)' }}>
              How many questions?
            </label>
            <input type="number" min="1" max="50" value={questionCount}
              onChange={e => setQuestionCount(parseInt(e.target.value) || 10)}
              className="w-full px-3 py-2.5 rounded-xl text-[14px]"
              style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }} />
          </div>

          {error && (
            <div className="p-3 rounded-xl text-[13px]"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#EF4444' }}>
              {error}
            </div>
          )}

          {/* Generate */}
          <button onClick={handleGenerate} disabled={generating || !topic.trim()}
            className="w-full py-3 rounded-xl text-[15px] font-bold text-white flex items-center justify-center gap-2 disabled:opacity-50"
            style={{ background: 'var(--coral)', boxShadow: '0 4px 14px rgba(216, 108, 82, 0.3)' }}>
            {generating
              ? <><Loader2 className="w-5 h-5 animate-spin" /> Generating…</>
              : <><Printer className="w-5 h-5" /> Generate &amp; Print</>}
          </button>
        </div>
      ) : (
        // Success state
        <div className="rounded-card p-8 text-center"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
            style={{ background: 'rgba(22,163,74,0.12)' }}>
            <CheckCircle className="w-8 h-8" style={{ color: '#16A34A' }} />
          </div>
          <h2 className="font-serif text-[22px] mb-1" style={{ color: 'var(--text-dark)' }}>
            {result.title || 'Assignment ready!'}
          </h2>
          <p className="text-[13px] mb-5" style={{ color: 'var(--text-mid)' }}>
            Your {template.replace(/_/g, ' ')} is generated and ready to print or assign.
          </p>
          <div className="flex gap-2 justify-center">
            <Link href={`/assignments/${result.assignment_id}`}
              className="px-5 py-2.5 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2"
              style={{ background: 'var(--coral)' }}>
              <ExternalLink className="w-4 h-4" /> Open Assignment
            </Link>
            <button onClick={reset}
              className="px-5 py-2.5 rounded-xl text-[13px] font-semibold flex items-center gap-2"
              style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
              <Plus className="w-4 h-4" /> Make Another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
