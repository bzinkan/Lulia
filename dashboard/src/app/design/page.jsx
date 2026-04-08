'use client';
import { useState, useEffect } from 'react';
import { Sparkles, FileText, Download, ExternalLink, Loader2, ChevronDown, Wand2, BookOpen, X, Search, Palette } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const GRADES = ['K','1','2','3','4','5','6','7','8','9','10','11','12'];
const SUBJECTS = ['Mathematics', 'English Language Arts', 'Science', 'Social Studies', 'World Languages', 'Fine Arts', 'Health & PE', 'General'];
const OUTPUT_TYPES = [
  { id: 'worksheet', label: 'Worksheet', desc: 'Questions, word bank, answer key' },
  { id: 'infographic', label: 'Infographic', desc: 'Visual summary of a topic' },
  { id: 'poster', label: 'Poster', desc: 'Classroom display or anchor chart' },
  { id: 'flashcards', label: 'Flashcards', desc: 'Term/definition cards' },
  { id: 'presentation', label: 'Presentation', desc: 'Slide deck for a lesson' },
];
const DIFFICULTIES = ['easy', 'medium', 'hard', 'mixed'];
const THEMES = [
  { id: 'modern_clean', name: 'Modern Clean', color: '#F97316' },
  { id: 'ocean_blue', name: 'Ocean Blue', color: '#2563EB' },
  { id: 'forest_green', name: 'Forest Green', color: '#059669' },
  { id: 'royal_purple', name: 'Royal Purple', color: '#7C3AED' },
];

export default function DesignStudio() {
  // Step tracking
  const [step, setStep] = useState(1); // 1=configure, 2=preview content, 3=pick design, 4=export

  // Step 1: Configuration
  const [topic, setTopic] = useState('');
  const [grade, setGrade] = useState('4');
  const [subject, setSubject] = useState('Mathematics');
  const [outputType, setOutputType] = useState('worksheet');
  const [questionCount, setQuestionCount] = useState(10);
  const [difficulty, setDifficulty] = useState('medium');
  const [standards, setStandards] = useState([]);
  const [standardSearch, setStandardSearch] = useState('');
  const [standardResults, setStandardResults] = useState([]);
  const [suggestingStandards, setSuggestingStandards] = useState(false);

  // Step 2: Generated content
  const [generatedContent, setGeneratedContent] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);

  // Step 3: Design previews
  const [selectedTheme, setSelectedTheme] = useState('modern_clean');
  const [previewHtml, setPreviewHtml] = useState({});
  const [loadingPreviews, setLoadingPreviews] = useState(false);

  // Step 4: Export
  const [exporting, setExporting] = useState(null); // 'pdf' | 'google' | 'canva' | null

  // Try to auto-fill from class context
  useEffect(() => {
    try {
      const stored = localStorage.getItem('lulia_active_class_id');
      if (stored) {
        apiFetch(`/api/v1/classes/${stored}`).then(cls => {
          if (cls.grade_level) setGrade(cls.grade_level);
          if (cls.subject) setSubject(cls.subject);
        }).catch(() => {});
      }
    } catch {}
  }, []);

  // ── Standards ───────────────────────────────────────────────────────
  async function suggestStandards() {
    setSuggestingStandards(true);
    try {
      const res = await apiFetch('/api/v1/standards/suggest', {
        method: 'POST',
        body: JSON.stringify({ description: topic, subject, grade, worksheet_content: [] }),
      });
      setStandardResults(res.standards || []);
    } catch { setStandardResults([]); }
    finally { setSuggestingStandards(false); }
  }

  function addStandard(std) {
    if (!standards.some(s => s.standard_id === std.standard_id)) {
      setStandards(prev => [...prev, std]);
    }
  }

  function removeStandard(id) {
    setStandards(prev => prev.filter(s => s.standard_id !== id));
  }

  // ── Step 2: Generate Content ────────────────────────────────────────
  async function handleGenerate() {
    if (!topic.trim()) return;
    setGenerating(true);
    setGenError(null);
    try {
      const res = await apiFetch('/api/v1/design/generate-content', {
        method: 'POST',
        body: JSON.stringify({
          topic, grade, subject, output_type: outputType,
          question_count: questionCount, difficulty,
          standards: standards.map(s => s.code),
        }),
      });
      setGeneratedContent(res.content || res);
      setStep(2);
    } catch (e) {
      setGenError(e.message || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  }

  // ── Step 3: Generate Theme Previews ─────────────────────────────────
  async function generatePreviews() {
    if (!generatedContent) return;
    setLoadingPreviews(true);
    const previews = {};
    for (const theme of THEMES) {
      try {
        const res = await apiFetch('/api/v1/design/export-pdf', {
          method: 'POST',
          body: JSON.stringify({ content: generatedContent, theme: theme.id }),
        });
        previews[theme.id] = res.html || res.preview_html || '';
      } catch {
        previews[theme.id] = '';
      }
    }
    setPreviewHtml(previews);
    setLoadingPreviews(false);
    setStep(3);
  }

  // ── Step 4: Export ──────────────────────────────────────────────────
  async function exportPDF() {
    setExporting('pdf');
    try {
      const res = await apiFetch('/api/v1/design/export-pdf', {
        method: 'POST',
        body: JSON.stringify({ content: generatedContent, theme: selectedTheme }),
      });
      // Open print preview in new window
      const win = window.open('', '_blank');
      win.document.write(res.html || res.preview_html || '<p>No content</p>');
      win.document.close();
    } catch (e) { alert('PDF export failed: ' + e.message); }
    finally { setExporting(null); }
  }

  async function exportGoogle() {
    setExporting('google');
    try {
      const res = await apiFetch('/api/v1/design/export-google', {
        method: 'POST',
        body: JSON.stringify({ content: generatedContent, export_type: outputType === 'presentation' ? 'slides' : 'doc' }),
      });
      if (res.url) window.open(res.url, '_blank');
      else alert('Google export completed');
    } catch (e) { alert('Google export failed: ' + e.message); }
    finally { setExporting(null); }
  }

  // ── Render ──────────────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 24, color: '#1C1917' }}>Design Studio</h1>
        <p style={{ fontSize: 13, color: '#78716C', marginTop: 4 }}>Generate professional worksheets, infographics, and more</p>
      </div>

      {/* Step indicator */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24 }}>
        {['Configure', 'Review Content', 'Pick Design', 'Export'].map((label, i) => (
          <button key={i} onClick={() => { if (i + 1 <= step) setStep(i + 1); }}
            style={{
              flex: 1, padding: '8px 0', borderRadius: 8, border: 'none', fontSize: 11, fontWeight: 600,
              fontFamily: "'DM Sans'", cursor: i + 1 <= step ? 'pointer' : 'default',
              background: step === i + 1 ? '#F97316' : i + 1 < step ? '#FFF7ED' : '#F5F5F4',
              color: step === i + 1 ? 'white' : i + 1 < step ? '#F97316' : '#A8A29E',
            }}>
            {i + 1}. {label}
          </button>
        ))}
      </div>

      {/* ── STEP 1: Configure ────────────────────────────────────────── */}
      {step === 1 && (
        <div style={{ background: 'white', borderRadius: 14, padding: 24, border: '1px solid #E7E5E4' }}>
          {/* Topic */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>What are you teaching?</label>
            <input value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g., equivalent fractions, the water cycle, causes of the Civil War"
              style={{ width: '100%', padding: '10px 14px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 14, fontFamily: "'DM Sans'", outline: 'none' }}
              onKeyDown={e => e.key === 'Enter' && handleGenerate()} />
          </div>

          {/* Grade + Subject + Output Type row */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
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
            <div style={{ flex: 2 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Output Type</label>
              <select value={outputType} onChange={e => setOutputType(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }}>
                {OUTPUT_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </div>
          </div>

          {/* Questions + Difficulty row */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Questions</label>
              <input type="number" value={questionCount} onChange={e => setQuestionCount(parseInt(e.target.value) || 10)} min={1} max={30}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Difficulty</label>
              <select value={difficulty} onChange={e => setDifficulty(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }}>
                {DIFFICULTIES.map(d => <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>)}
              </select>
            </div>
          </div>

          {/* Standards */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>
              <BookOpen style={{ width: 12, height: 12, display: 'inline', marginRight: 4 }} />
              Standards (optional — AI will suggest if left empty)
            </label>
            {standards.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                {standards.map(s => (
                  <span key={s.standard_id} title={s.description}
                    style={{ fontSize: 10, padding: '2px 6px', background: '#FFF7ED', border: '1px solid #FDBA74', borderRadius: 6, color: '#78350F', display: 'flex', alignItems: 'center', gap: 3 }}>
                    <strong>{s.code}</strong>
                    <button onClick={() => removeStandard(s.standard_id)} style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0, color: '#A8A29E', lineHeight: 1 }}>
                      <X style={{ width: 10, height: 10 }} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <button onClick={suggestStandards} disabled={suggestingStandards || !topic.trim()}
              style={{ fontSize: 11, padding: '6px 12px', borderRadius: 8, border: '1px dashed #FDBA74', background: '#FFF7ED', cursor: 'pointer', color: '#78350F', fontFamily: "'DM Sans'", display: 'flex', alignItems: 'center', gap: 6 }}>
              {suggestingStandards ? <Loader2 style={{ width: 12, height: 12 }} className="animate-spin" /> : <Wand2 style={{ width: 12, height: 12 }} />}
              {suggestingStandards ? 'Finding standards...' : 'AI Suggest Standards'}
            </button>
            {standardResults.length > 0 && (
              <div style={{ maxHeight: 120, overflowY: 'auto', border: '1px solid #E7E5E4', borderRadius: 8, marginTop: 6, background: '#FAFAF9' }}>
                {standardResults.map(s => {
                  const added = standards.some(a => a.standard_id === s.standard_id);
                  return (
                    <button key={s.standard_id} onClick={() => !added && addStandard(s)} disabled={added}
                      style={{ display: 'block', width: '100%', textAlign: 'left', padding: '5px 8px', border: 'none', borderBottom: '1px solid #F5F5F4', background: added ? '#F5F5F4' : 'transparent', cursor: added ? 'default' : 'pointer', fontSize: 10 }}
                      onMouseEnter={e => { if (!added) e.currentTarget.style.background = '#FFF7ED'; }}
                      onMouseLeave={e => { if (!added) e.currentTarget.style.background = 'transparent'; }}>
                      <strong style={{ color: added ? '#A8A29E' : '#78350F' }}>{s.code} {added && '(added)'}</strong>
                      <div style={{ color: '#78716C', marginTop: 1, lineHeight: 1.3 }}>{(s.description || '').slice(0, 100)}</div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Error */}
          {genError && (
            <div style={{ padding: '10px 14px', borderRadius: 10, background: '#FEF2F2', border: '1px solid #FECACA', marginBottom: 12, fontSize: 12, color: '#DC2626' }}>
              {genError}
            </div>
          )}

          {/* Generate button */}
          <button onClick={handleGenerate} disabled={generating || !topic.trim()}
            style={{
              width: '100%', padding: '14px 0', borderRadius: 12, border: 'none',
              background: generating ? '#FDBA74' : '#F97316', color: 'white',
              cursor: 'pointer', fontSize: 15, fontWeight: 600, fontFamily: "'DM Sans'",
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
            {generating ? <Loader2 style={{ width: 18, height: 18 }} className="animate-spin" /> : <Sparkles style={{ width: 18, height: 18 }} />}
            {generating ? 'Generating content...' : 'Generate'}
          </button>
        </div>
      )}

      {/* ── STEP 2: Review Content ───────────────────────────────────── */}
      {step === 2 && generatedContent && (
        <div style={{ background: 'white', borderRadius: 14, padding: 24, border: '1px solid #E7E5E4' }}>
          <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 20, color: '#1C1917', marginBottom: 4 }}>
            {generatedContent.title || 'Generated Content'}
          </h2>
          <p style={{ fontSize: 12, color: '#78716C', marginBottom: 16 }}>{generatedContent.instructions}</p>

          {/* Questions */}
          <div style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Questions ({(generatedContent.questions || []).length})</h3>
            {(generatedContent.questions || []).map((q, i) => (
              <div key={i} style={{ padding: '8px 12px', background: i % 2 === 0 ? '#FAFAF9' : 'white', borderRadius: 8, marginBottom: 4, fontSize: 12 }}>
                <div style={{ fontWeight: 600, color: '#1C1917' }}>{q.number || i + 1}. {q.question_text}</div>
                {q.options && (
                  <div style={{ marginLeft: 16, marginTop: 4 }}>
                    {q.options.map((opt, j) => (
                      <div key={j} style={{ color: opt === q.correct_answer ? '#059669' : '#78716C', fontSize: 11 }}>
                        {String.fromCharCode(65 + j)}. {opt} {opt === q.correct_answer && ' ✓'}
                      </div>
                    ))}
                  </div>
                )}
                {q.type !== 'multiple_choice' && q.correct_answer && (
                  <div style={{ marginTop: 4, fontSize: 11, color: '#059669' }}>Answer: {q.correct_answer}</div>
                )}
                <div style={{ fontSize: 9, color: '#A8A29E', marginTop: 2 }}>{q.standard_code} · {q.difficulty} · {q.type} · {q.points}pts</div>
              </div>
            ))}
          </div>

          {/* Word Bank */}
          {generatedContent.word_bank?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Word Bank</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {generatedContent.word_bank.map((w, i) => (
                  <span key={i} style={{ fontSize: 12, padding: '3px 10px', background: '#FFF7ED', border: '1px solid #FDBA74', borderRadius: 6 }}>{w}</span>
                ))}
              </div>
            </div>
          )}

          {/* Vocabulary */}
          {generatedContent.vocabulary?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Vocabulary</h3>
              {generatedContent.vocabulary.map((v, i) => (
                <div key={i} style={{ fontSize: 12, marginBottom: 4 }}>
                  <strong>{v.term}:</strong> {v.definition}
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            <button onClick={() => setStep(1)}
              style={{ flex: 1, padding: '10px 0', borderRadius: 10, border: '1px solid #E7E5E4', background: 'white', cursor: 'pointer', fontSize: 13, fontFamily: "'DM Sans'", color: '#78716C' }}>
              Back to Edit
            </button>
            <button onClick={generatePreviews}
              disabled={loadingPreviews}
              style={{
                flex: 2, padding: '10px 0', borderRadius: 10, border: 'none',
                background: loadingPreviews ? '#FDBA74' : '#F97316', color: 'white',
                cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: "'DM Sans'",
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              {loadingPreviews ? <Loader2 style={{ width: 14, height: 14 }} className="animate-spin" /> : <Palette style={{ width: 14, height: 14 }} />}
              {loadingPreviews ? 'Generating designs...' : 'Pick a Design'}
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Pick Design ──────────────────────────────────────── */}
      {step === 3 && (
        <div style={{ background: 'white', borderRadius: 14, padding: 24, border: '1px solid #E7E5E4' }}>
          <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 18, color: '#1C1917', marginBottom: 16 }}>Choose a design</h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
            {THEMES.map(theme => (
              <button key={theme.id} onClick={() => setSelectedTheme(theme.id)}
                style={{
                  border: selectedTheme === theme.id ? `3px solid ${theme.color}` : '2px solid #E7E5E4',
                  borderRadius: 12, overflow: 'hidden', cursor: 'pointer', background: 'white',
                  padding: 0, textAlign: 'left',
                }}>
                {/* Preview */}
                <div style={{ height: 180, overflow: 'hidden', background: '#FAFAF9', position: 'relative' }}>
                  {previewHtml[theme.id] ? (
                    <iframe srcDoc={previewHtml[theme.id]} style={{ width: '200%', height: '400%', border: 'none', transform: 'scale(0.5)', transformOrigin: 'top left', pointerEvents: 'none' }} />
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                      <Loader2 style={{ width: 20, height: 20, color: theme.color }} className="animate-spin" />
                    </div>
                  )}
                </div>
                {/* Label */}
                <div style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 16, height: 16, borderRadius: '50%', background: theme.color }} />
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#1C1917', fontFamily: "'DM Sans'" }}>{theme.name}</span>
                  {selectedTheme === theme.id && <span style={{ fontSize: 9, color: theme.color, fontWeight: 600, marginLeft: 'auto' }}>Selected</span>}
                </div>
              </button>
            ))}
          </div>

          {/* Export buttons */}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setStep(2)}
              style={{ padding: '10px 16px', borderRadius: 10, border: '1px solid #E7E5E4', background: 'white', cursor: 'pointer', fontSize: 12, fontFamily: "'DM Sans'", color: '#78716C' }}>
              Back
            </button>
            <button onClick={exportPDF} disabled={exporting === 'pdf'}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 10, border: 'none',
                background: '#1C1917', color: 'white', cursor: 'pointer',
                fontSize: 12, fontWeight: 600, fontFamily: "'DM Sans'",
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              {exporting === 'pdf' ? <Loader2 style={{ width: 14, height: 14 }} className="animate-spin" /> : <Download style={{ width: 14, height: 14 }} />}
              Download PDF
            </button>
            <button onClick={exportGoogle} disabled={exporting === 'google'}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 10, border: 'none',
                background: '#2563EB', color: 'white', cursor: 'pointer',
                fontSize: 12, fontWeight: 600, fontFamily: "'DM Sans'",
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              {exporting === 'google' ? <Loader2 style={{ width: 14, height: 14 }} className="animate-spin" /> : <ExternalLink style={{ width: 14, height: 14 }} />}
              Google Docs
            </button>
            <button onClick={() => { setExporting('canva'); /* Canva MCP handled by chat sidebar */ }}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 10, border: 'none',
                background: '#7C3AED', color: 'white', cursor: 'pointer',
                fontSize: 12, fontWeight: 600, fontFamily: "'DM Sans'",
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              <Sparkles style={{ width: 14, height: 14 }} />
              Send to Canva
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
