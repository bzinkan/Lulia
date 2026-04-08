'use client';
import { useState } from 'react';
import { ClipboardList, Sparkles, Loader2, ExternalLink, AlertCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function FormsPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Google Forms</h1>
        <p className="text-sm mt-1" style={{ color: '#78716C' }}>AI-generated quizzes pushed to Google Forms with auto-grading</p>
      </div>

      <div style={{ background: 'white', borderRadius: 14, padding: 20, border: '1px solid #E7E5E4', marginBottom: 24 }}>
        <QuickFormGenerator />
      </div>
    </div>
  );
}

function QuickFormGenerator() {
  const [topic, setTopic] = useState('');
  const [grade, setGrade] = useState('4');
  const [subject, setSubject] = useState('Mathematics');
  const [questionCount, setQuestionCount] = useState(10);
  const [questionTypes, setQuestionTypes] = useState(['multiple_choice', 'short_answer']);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const GRADES = ['K','1','2','3','4','5','6','7','8','9','10','11','12'];
  const SUBJECTS = ['Mathematics', 'English Language Arts', 'Science', 'Social Studies', 'World Languages', 'Fine Arts', 'Health & PE', 'General'];
  const Q_TYPES = [
    { id: 'multiple_choice', label: 'Multiple Choice' },
    { id: 'short_answer', label: 'Short Answer' },
  ];

  async function handleGenerate() {
    if (!topic.trim()) return;
    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiFetch('/api/v1/google/forms/generate', {
        method: 'POST',
        body: JSON.stringify({ topic, grade, subject, question_count: questionCount, question_types: questionTypes }),
      });
      if (res.error) {
        setError(res.error);
      } else {
        setResult(res);
      }
    } catch (e) {
      setError(e.message || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Quiz Topic</label>
        <input value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g., Fractions Review, Cell Division Test, Vocabulary Quiz"
          onKeyDown={e => e.key === 'Enter' && handleGenerate()}
          style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 14, fontFamily: "'DM Sans'", outline: 'none' }} />
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Grade</label>
          <select value={grade} onChange={e => setGrade(e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }}>
            {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
          </select>
        </div>
        <div style={{ flex: 2 }}>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Subject</label>
          <select value={subject} onChange={e => setSubject(e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }}>
            {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Questions</label>
          <input type="number" value={questionCount} onChange={e => setQuestionCount(parseInt(e.target.value) || 10)} min={3} max={30}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }} />
        </div>
      </div>

      {/* Question types */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Question Types</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {Q_TYPES.map(t => (
            <label key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#1C1917', cursor: 'pointer' }}>
              <input type="checkbox" checked={questionTypes.includes(t.id)}
                onChange={e => {
                  if (e.target.checked) setQuestionTypes(prev => [...prev, t.id]);
                  else setQuestionTypes(prev => prev.filter(x => x !== t.id));
                }} />
              {t.label}
            </label>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ padding: '10px 14px', borderRadius: 10, background: '#FEF2F2', border: '1px solid #FECACA', marginBottom: 12, fontSize: 12, color: '#DC2626', display: 'flex', alignItems: 'center', gap: 6 }}>
          <AlertCircle style={{ width: 14, height: 14 }} /> {error}
        </div>
      )}

      {result && (
        <div style={{ padding: '12px 16px', borderRadius: 10, background: '#F0FDF4', border: '1px solid #BBF7D0', marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#166534', marginBottom: 4 }}>
            Quiz created! ({result.question_count || 0} questions)
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            {result.form_url && (
              <a href={result.form_url} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 12, color: '#F97316', display: 'flex', alignItems: 'center', gap: 4 }}>
                <ExternalLink style={{ width: 14, height: 14 }} /> Edit Form
              </a>
            )}
            {result.responder_url && (
              <a href={result.responder_url} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 12, color: '#2563EB', display: 'flex', alignItems: 'center', gap: 4 }}>
                <ExternalLink style={{ width: 14, height: 14 }} /> Student Link
              </a>
            )}
          </div>
        </div>
      )}

      <button onClick={handleGenerate} disabled={generating || !topic.trim()}
        style={{
          width: '100%', padding: '12px 0', borderRadius: 10, border: 'none',
          background: generating ? '#FDBA74' : '#F97316', color: 'white',
          cursor: 'pointer', fontSize: 14, fontWeight: 600, fontFamily: "'DM Sans'",
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
        {generating ? <Loader2 style={{ width: 16, height: 16 }} className="animate-spin" /> : <Sparkles style={{ width: 16, height: 16 }} />}
        {generating ? 'Creating quiz...' : 'Generate Quiz Form'}
      </button>
    </div>
  );
}
