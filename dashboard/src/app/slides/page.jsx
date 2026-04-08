'use client';
import { useState } from 'react';
import { Presentation, Sparkles, Loader2, ExternalLink, AlertCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import GenerationTabs from '@/components/GenerationTabs';

export default function SlidesPage() {
  const [slides, setSlides] = useState([]);
  const [loading, setLoading] = useState(false);

  function handleResult(result) {
    if (result?.slides) {
      setSlides(prev => [result.slides, ...prev]);
    }
    // Refresh any list if needed
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Google Slides</h1>
        <p className="text-sm mt-1" style={{ color: '#78716C' }}>AI-generated presentations pushed to Google Slides</p>
      </div>

      {/* Quick generate */}
      <div style={{ background: 'white', borderRadius: 14, padding: 20, border: '1px solid #E7E5E4', marginBottom: 24 }}>
        <QuickSlideGenerator />
      </div>

      {/* Recent slides */}
      {slides.length > 0 && (
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: '#1C1917', marginBottom: 12 }}>Recent</h2>
          {slides.map((s, i) => (
            <div key={i} style={{ background: 'white', borderRadius: 12, padding: 16, border: '1px solid #E7E5E4', marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#1C1917' }}>{s.title || 'Presentation'}</div>
                <div style={{ fontSize: 11, color: '#A8A29E' }}>{s.slide_count || 0} slides</div>
              </div>
              {s.slides_url && (
                <a href={s.slides_url} target="_blank" rel="noopener noreferrer"
                  style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#F97316', textDecoration: 'none' }}>
                  <ExternalLink style={{ width: 14, height: 14 }} /> Open in Slides
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QuickSlideGenerator() {
  const [topic, setTopic] = useState('');
  const [grade, setGrade] = useState('4');
  const [subject, setSubject] = useState('Mathematics');
  const [slideCount, setSlideCount] = useState(8);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const GRADES = ['K','1','2','3','4','5','6','7','8','9','10','11','12'];
  const SUBJECTS = ['Mathematics', 'English Language Arts', 'Science', 'Social Studies', 'World Languages', 'Fine Arts', 'Health & PE', 'General'];

  async function handleGenerate() {
    if (!topic.trim()) return;
    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiFetch('/api/v1/google/slides/generate', {
        method: 'POST',
        body: JSON.stringify({ topic, grade, subject, slide_count: slideCount }),
      });
      setResult(res);
    } catch (e) {
      setError(e.message || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Topic</label>
        <input value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g., The Water Cycle, Equivalent Fractions, Causes of WWI"
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
          <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Slides</label>
          <input type="number" value={slideCount} onChange={e => setSlideCount(parseInt(e.target.value) || 8)} min={3} max={20}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }} />
        </div>
      </div>

      {error && (
        <div style={{ padding: '10px 14px', borderRadius: 10, background: '#FEF2F2', border: '1px solid #FECACA', marginBottom: 12, fontSize: 12, color: '#DC2626', display: 'flex', alignItems: 'center', gap: 6 }}>
          <AlertCircle style={{ width: 14, height: 14 }} /> {error}
        </div>
      )}

      {result && (
        <div style={{ padding: '12px 16px', borderRadius: 10, background: '#F0FDF4', border: '1px solid #BBF7D0', marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#166534', marginBottom: 4 }}>Presentation created!</div>
          {result.slides_url && (
            <a href={result.slides_url} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 12, color: '#F97316', display: 'flex', alignItems: 'center', gap: 4 }}>
              <ExternalLink style={{ width: 14, height: 14 }} /> Open in Google Slides
            </a>
          )}
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
        {generating ? 'Generating slides...' : 'Generate Slides'}
      </button>
    </div>
  );
}
