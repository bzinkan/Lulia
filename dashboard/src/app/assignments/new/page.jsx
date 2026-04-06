'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles, ChevronDown } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const TEMPLATES = [
  { id: 'worksheet', label: 'Worksheet', group: 'Standard' },
  { id: 'task_cards', label: 'Task Cards', group: 'Standard' },
  { id: 'quiz_test', label: 'Quiz / Test', group: 'Standard' },
  { id: 'exit_ticket', label: 'Exit Ticket', group: 'Standard' },
  { id: 'flashcards', label: 'Flashcards', group: 'Standard' },
  { id: 'bingo', label: 'BINGO', group: 'Standard' },
  { id: 'morning_work', label: 'Morning Work', group: 'Standard' },
  { id: 'study_guide', label: 'Study Guide', group: 'Standard' },
  { id: 'reading_comprehension', label: 'Reading Comprehension', group: 'Standard' },
  { id: 'graphic_organizer', label: 'Graphic Organizer', group: 'Standard' },
  { id: 'vocab_cards', label: 'Vocabulary Cards', group: 'Standard' },
  { id: 'anchor_chart', label: 'Anchor Chart', group: 'Standard' },
  { id: 'homework_packet', label: 'Homework Packet', group: 'Standard' },
  { id: 'sub_plans', label: 'Sub Plans', group: 'Special' },
  { id: 'parent_newsletter', label: 'Parent Newsletter', group: 'Special' },
  { id: 'lab_activity', label: 'Lab Activity', group: 'Science' },
  { id: 'lab_report', label: 'Lab Report', group: 'Science' },
  { id: 'word_search', label: 'Word Search', group: 'Puzzle' },
  { id: 'crossword', label: 'Crossword', group: 'Puzzle' },
  { id: 'board_game', label: 'Board Game', group: 'Puzzle' },
  { id: 'scavenger_hunt', label: 'Scavenger Hunt', group: 'Puzzle' },
  { id: 'escape_room', label: 'Escape Room', group: 'Puzzle' },
];

const THEMES = [
  { id: 'modern_clean', label: 'Modern Clean', color: '#F97316' },
  { id: 'playful_primary', label: 'Playful Primary', color: '#E11D48' },
  { id: 'bold_bright', label: 'Bold & Bright', color: '#7C3AED' },
  { id: 'nature_earth', label: 'Nature & Earth', color: '#059669' },
];

const SUBJECTS = ['Mathematics', 'ELA', 'Science', 'Social Studies'];
const GRADES = ['K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'];

export default function NewAssignment() {
  const router = useRouter();
  const [form, setForm] = useState({
    subject: 'Mathematics',
    grade_level: '4',
    output_template_id: 'worksheet',
    design_theme: 'modern_clean',
    question_count: 10,
    standards_ids: [],
    has_kb_coverage: true,
    difficulty_distribution: { easy: 3, medium: 4, hard: 3 },
  });
  const [standards, setStandards] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Load standards when subject/grade changes
  useEffect(() => {
    async function loadStandards() {
      try {
        const data = await apiFetch(
          `/api/v1/standards?subject=${form.subject}&grade=${form.grade_level}&limit=50`
        );
        setStandards(data.standards || []);
      } catch (e) {
        console.error('Failed to load standards:', e);
      }
    }
    loadStandards();
  }, [form.subject, form.grade_level]);

  function toggleStandard(code) {
    setForm(f => ({
      ...f,
      standards_ids: f.standards_ids.includes(code)
        ? f.standards_ids.filter(c => c !== code)
        : [...f.standards_ids, code],
    }));
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const data = await apiFetch('/api/v1/assignments/generate', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          work_order_id: `WO-${Date.now()}`,
          class_id: '00000000-0000-0000-0000-000000000010',
          teacher_id: '00000000-0000-0000-0000-000000000001',
        }),
      });
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">New Assignment</h1>
        <p className="text-sm text-gray-500 mt-1">Configure and generate a standards-aligned assignment</p>
      </div>

      {!result ? (
        <div className="max-w-2xl">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
            {/* Subject + Grade row */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                <select
                  value={form.subject}
                  onChange={e => setForm(f => ({ ...f, subject: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                >
                  {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Grade</label>
                <select
                  value={form.grade_level}
                  onChange={e => setForm(f => ({ ...f, grade_level: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                >
                  {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
                </select>
              </div>
            </div>

            {/* Template */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Template</label>
              <select
                value={form.output_template_id}
                onChange={e => setForm(f => ({ ...f, output_template_id: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              >
                {['Standard', 'Special', 'Science', 'Puzzle'].map(group => (
                  <optgroup key={group} label={group}>
                    {TEMPLATES.filter(t => t.group === group).map(t => (
                      <option key={t.id} value={t.id}>{t.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            {/* Design Theme */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Design Theme</label>
              <div className="flex gap-3">
                {THEMES.map(t => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setForm(f => ({ ...f, design_theme: t.id }))}
                    className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-all ${
                      form.design_theme === t.id
                        ? 'border-2 shadow-sm font-medium'
                        : 'border-gray-200 text-gray-600 hover:border-gray-300'
                    }`}
                    style={form.design_theme === t.id ? { borderColor: t.color, color: t.color } : {}}
                  >
                    <span className="w-3 h-3 rounded-full" style={{ background: t.color }} />
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Question Count */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Questions: {form.question_count}
              </label>
              <input
                type="range"
                min="5"
                max="25"
                value={form.question_count}
                onChange={e => setForm(f => ({ ...f, question_count: parseInt(e.target.value) }))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>5</span><span>15</span><span>25</span>
              </div>
            </div>

            {/* Difficulty */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Difficulty Mix</label>
              <div className="flex gap-4">
                {['easy', 'medium', 'hard'].map(level => (
                  <div key={level} className="flex-1">
                    <label className="block text-xs text-gray-500 mb-1 capitalize">{level}</label>
                    <input
                      type="number"
                      min="0"
                      max={form.question_count}
                      value={form.difficulty_distribution[level]}
                      onChange={e => setForm(f => ({
                        ...f,
                        difficulty_distribution: {
                          ...f.difficulty_distribution,
                          [level]: parseInt(e.target.value) || 0,
                        },
                      }))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-center focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Standards selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Standards ({form.standards_ids.length} selected)
              </label>
              <div className="border border-gray-300 rounded-lg max-h-48 overflow-y-auto">
                {standards.length === 0 ? (
                  <p className="text-sm text-gray-400 p-3">No standards found for this subject/grade</p>
                ) : (
                  standards.filter(s => s.code && !s.code.startsWith('[')).slice(0, 30).map(s => (
                    <label
                      key={s.standard_id}
                      className="flex items-start gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm border-b border-gray-100 last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={form.standards_ids.includes(s.code)}
                        onChange={() => toggleStandard(s.code)}
                        className="mt-0.5 accent-indigo-600"
                      />
                      <span>
                        <span className="font-medium text-gray-800">{s.code}</span>
                        <span className="text-gray-500 ml-1">— {s.description?.slice(0, 100)}</span>
                      </span>
                    </label>
                  ))
                )}
              </div>
            </div>

            {/* KB coverage toggle */}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.has_kb_coverage}
                onChange={e => setForm(f => ({ ...f, has_kb_coverage: e.target.checked }))}
                className="accent-indigo-600"
              />
              <span className="text-gray-700">Use Knowledge Base content (RAG grounding)</span>
            </label>

            {/* Error */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white px-4 py-3 rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2"
            >
              {generating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Generating... (15-30 seconds)
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Generate Assignment
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* Results */
        <div className="space-y-6">
          {/* Summary card */}
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
            <div className="flex items-center gap-2 text-emerald-700 mb-2">
              <Sparkles className="w-5 h-5" />
              <span className="font-medium">Assignment Generated</span>
            </div>
            <p className="text-sm text-emerald-600">
              {result.title} — {result.question_count} questions, QA score: {result.qa_score}/100
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => router.push(`/assignments/${result.assignment_id}`)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors"
            >
              View Full Assignment
            </button>
            <button
              onClick={() => { setResult(null); setError(null); }}
              className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 px-4 py-2 rounded-lg font-medium text-sm transition-colors"
            >
              Generate Another
            </button>
          </div>

          {/* Student version preview */}
          <div>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">Student Version</h2>
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-1">
              <iframe
                srcDoc={result.student_html}
                className="w-full min-h-[600px] rounded-lg"
                title="Student Version"
              />
            </div>
          </div>

          {/* Answer key preview */}
          <div>
            <h2 className="text-xl font-semibold text-gray-900 mb-3">Answer Key</h2>
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-1">
              <iframe
                srcDoc={result.answer_key_html}
                className="w-full min-h-[600px] rounded-lg"
                title="Answer Key"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
