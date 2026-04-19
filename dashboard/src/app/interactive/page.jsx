'use client';
import { useEffect, useMemo, useState } from 'react';
import { Gamepad2, Copy, ExternalLink, Loader2, CheckCircle, Target, FileText, ChevronDown, Sparkles, Lightbulb } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';
import { useTopicSuggestions } from '@/lib/useTopicSuggestions';
import StandardsPickerModal from '@/components/StandardsPickerModal';
import AssignmentPicker from '@/components/AssignmentPicker';
import InteractiveResult from '@/components/InteractiveResult';

// All 15 interactive activity templates, grouped by pedagogical purpose.
const TEMPLATE_GROUPS = [
  {
    group: 'Quick Assessment',
    templates: [
      { id: 'multiple_choice_quiz',    name: 'Multiple Choice Quiz',  desc: 'Click-to-answer with instant feedback' },
      { id: 'fill_in_blank',           name: 'Fill in the Blank',     desc: 'Type or click-from-word-bank answers' },
    ],
  },
  {
    group: 'Drag & Drop',
    templates: [
      { id: 'drag_drop_sort',          name: 'Drag & Drop Sort',      desc: 'Drag items into categories' },
      { id: 'drag_drop_sequence',      name: 'Sequence Order',        desc: 'Drag items into correct order' },
      { id: 'category_sort',           name: 'Category Sort',         desc: 'Drop items into buckets' },
      { id: 'matching_pairs',          name: 'Matching Pairs',        desc: 'Match items across two columns' },
    ],
  },
  {
    group: 'Study Tools',
    templates: [
      { id: 'click_to_reveal',         name: 'Click to Reveal',       desc: 'Click cards to reveal answers' },
      { id: 'flash_cards_interactive', name: 'Flashcards',            desc: 'Swipe to flip cards' },
    ],
  },
  {
    group: 'Puzzles',
    templates: [
      { id: 'word_search_interactive', name: 'Word Search',           desc: 'Find hidden words' },
      { id: 'crossword_interactive',   name: 'Crossword',             desc: 'Type answers into grid' },
    ],
  },
  {
    group: 'Subject-Specific',
    templates: [
      { id: 'number_line',             name: 'Number Line',           desc: 'Place values on a number line' },
      { id: 'slider_estimation',       name: 'Estimation Slider',     desc: 'Slide to estimate values' },
      { id: 'timeline_builder',        name: 'Timeline Builder',      desc: 'Drag events chronologically' },
      { id: 'hotspot_labeling',        name: 'Hotspot Labeling',      desc: 'Click to label diagram parts' },
      { id: 'whiteboard_response',     name: 'Whiteboard Response',   desc: 'Free-text or drawing open response' },
    ],
  },
];
const FLAT_TEMPLATES = TEMPLATE_GROUPS.flatMap(g => g.templates);

// Activity-aware topic placeholders — what kind of input each type needs.
const TOPIC_PLACEHOLDERS = {
  multiple_choice_quiz:    'e.g. adding fractions with unlike denominators',
  fill_in_blank:           'e.g. past-tense verb conjugations',
  drag_drop_sort:          "e.g. sort nouns vs verbs, or rocks by type",
  drag_drop_sequence:      'e.g. steps of the water cycle',
  category_sort:           'e.g. solids, liquids, gases',
  matching_pairs:          'e.g. countries to capitals, terms to definitions',
  click_to_reveal:         'e.g. multiplication facts 1 to 12',
  flash_cards_interactive: 'e.g. Civil War key vocabulary',
  word_search_interactive: "Words or topic — e.g. 'igneous, sedimentary, metamorphic' or 'rock types'",
  crossword_interactive:   "Topic or word list — e.g. 'state capitals' or 'photosynthesis vocabulary'",
  number_line:             'e.g. fractions between 0 and 1',
  slider_estimation:       'e.g. classroom object lengths in cm',
  timeline_builder:        'e.g. Civil War battles 1861 to 1865',
  whiteboard_response:     "Open prompt — e.g. 'Explain how plants make food'",
  hotspot_labeling:        'e.g. parts of a plant cell',
};

const DEFAULT_TEACHER_ID = '00000000-0000-0000-0000-000000000001';

export default function InteractivePage() {
  const { classes, activeClassId } = useClassContext();
  const activeClass = classes.find(c => c.class_id === activeClassId);

  // Core state
  const [selectedTemplate, setSelectedTemplate] = useState(FLAT_TEMPLATES[0].id);
  const [topic, setTopic] = useState('');
  const [standardsCodes, setStandardsCodes] = useState([]);
  const [selectedAssignment, setSelectedAssignment] = useState(null);

  // UI state
  const [showStandardsPicker, setShowStandardsPicker] = useState(false);
  const [showAssignmentPicker, setShowAssignmentPicker] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  // Library
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);
  function load() {
    apiFetch('/api/v1/interactive')
      .then(d => setActivities(d.activities || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  const selectedTemplateMeta = FLAT_TEMPLATES.find(t => t.id === selectedTemplate);
  const { suggestions } = useTopicSuggestions({
    activityType: selectedTemplate,
    topic,
    classId: activeClass?.class_id,
    teacherId: DEFAULT_TEACHER_ID,
  });

  const canGenerate = useMemo(() => {
    if (generating) return false;
    if (selectedAssignment) return true;          // From-existing path
    if (standardsCodes.length > 0) return true;   // Standards are a valid anchor on their own
    return topic.trim().length >= 3;
  }, [generating, selectedAssignment, topic, standardsCodes]);

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    setLastResult(null);

    try {
      let result;
      if (selectedAssignment) {
        // From Existing path — unchanged backend call
        result = await apiFetch('/api/v1/interactive/generate', {
          method: 'POST',
          body: JSON.stringify({
            assignment_id: selectedAssignment.assignment_id,
            interactive_template_id: selectedTemplate,
            teacher_id: DEFAULT_TEACHER_ID,
            class_id: activeClass?.class_id,
          }),
        });
      } else {
        // Unified prompt-style generation. Synthesize a single prompt from
        // tile + topic + optional standards + class context.
        const subject = activeClass?.subject || 'General';
        const grade = activeClass?.grade_level || '4';
        const stateClause = activeClass?.state_code ? ` (${activeClass.state_code} standards)` : '';
        const standardsClause = standardsCodes.length
          ? ` aligned to standards: ${standardsCodes.join(', ')}.`
          : '';
        const trimmedTopic = topic.trim();
        // Drop '(from assignment)' prefix if it leaked through
        const cleanTopic = trimmedTopic.startsWith('(from assignment)') ? '' : trimmedTopic;
        const topicClause = cleanTopic ? ` Topic: ${cleanTopic}.` : '';
        const synthPrompt =
          `Create a ${selectedTemplate} for Grade ${grade} ${subject}${stateClause}.${standardsClause}${topicClause} ` +
          `10 items, medium difficulty, standards-aligned.`;
        result = await apiFetch('/api/v1/assistant/generate-from-prompt', {
          method: 'POST',
          body: JSON.stringify({
            prompt: synthPrompt,
            output_type: 'interactive',
            teacher_id: DEFAULT_TEACHER_ID,
            class_id: activeClass?.class_id,
          }),
        });
      }

      // Extract the interactive bit out of whichever shape we got back
      const activity = result?.interactive || result;
      if (activity?.error) {
        setGenerateError(activity.error);
      } else if (activity?.activity_id) {
        setLastResult(activity);
        load(); // refresh library in background
      } else {
        setGenerateError('Generation returned an unexpected response. Try again?');
      }
    } catch (e) {
      setGenerateError(e?.message || 'Generation failed. Try again?');
    } finally {
      setGenerating(false);
    }
  }

  const pickAssignment = (a) => {
    setSelectedAssignment(a);
    setShowAssignmentPicker(false);
    // When using an existing assignment, the topic is implied by the assignment
    if (a?.title) setTopic(`(from assignment) ${a.title}`);
  };

  const clearAssignment = () => {
    setSelectedAssignment(null);
    setTopic('');
  };

  return (
    <div className="max-w-[1100px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-[14px] flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, var(--coral), var(--coral-light))',
              boxShadow: '0 4px 14px rgba(216,108,82,0.3)',
            }}>
            <Gamepad2 className="w-6 h-6 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="font-serif text-[28px] leading-tight" style={{ color: 'var(--text-dark)' }}>
              Interactive Activities
            </h1>
            <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
              Web-based student activities with instant feedback. Pick a type, type a topic, refine until it's right.
            </p>
          </div>
        </div>
      </div>

      {/* Class context banner */}
      {activeClass && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-xl text-[12px] flex-wrap"
          style={{
            background: 'rgba(107,160,138,0.1)',
            border: '1px solid rgba(107,160,138,0.3)',
            color: 'var(--text-dark)',
          }}>
          <span className="font-bold uppercase tracking-wider text-[10px]" style={{ color: 'var(--sage)' }}>
            Generating for
          </span>
          <span className="font-semibold">{activeClass.name}</span>
          <span style={{ color: 'var(--text-light)' }}>·</span>
          <span style={{ color: 'var(--text-mid)' }}>
            Grade {activeClass.grade_level} {activeClass.subject}
          </span>
          {activeClass.state_code && (
            <>
              <span style={{ color: 'var(--text-light)' }}>·</span>
              <span style={{ color: 'var(--text-mid)' }}>{activeClass.state_code} standards</span>
            </>
          )}
        </div>
      )}

      {/* STEP 1 — Tile gallery */}
      <div className="rounded-card p-5 mb-4"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
            style={{ background: 'var(--coral)', color: 'white' }}>
            Step 1
          </span>
          <h2 className="font-serif text-[18px]" style={{ color: 'var(--text-dark)' }}>
            Pick an activity type
          </h2>
        </div>
        <p className="text-[12px] mb-4" style={{ color: 'var(--text-mid)' }}>
          15 types grouped by purpose. Click any tile to select it.
        </p>

        <div className="space-y-4">
          {TEMPLATE_GROUPS.map(group => (
            <div key={group.group}>
              <div className="text-[10px] font-bold uppercase tracking-wider mb-2"
                style={{ color: 'var(--text-light)' }}>
                {group.group}
              </div>
              <div className="grid gap-2"
                style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
                {group.templates.map(t => {
                  const active = selectedTemplate === t.id;
                  return (
                    <button key={t.id}
                      onClick={() => setSelectedTemplate(t.id)}
                      className="rounded-xl p-3 text-left relative transition-all"
                      style={{
                        background: active ? 'rgba(216,108,82,0.08)' : 'var(--cream)',
                        border: active ? '2px solid var(--coral)' : '2px solid transparent',
                        cursor: 'pointer',
                        boxShadow: active ? '0 2px 8px rgba(216,108,82,0.2)' : 'none',
                      }}>
                      {active && (
                        <div className="absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center"
                          style={{ background: 'var(--coral)' }}>
                          <CheckCircle className="w-3 h-3" style={{ color: 'white' }} strokeWidth={3} />
                        </div>
                      )}
                      <div className="text-[13px] font-bold mb-0.5 pr-6"
                        style={{ color: active ? 'var(--coral)' : 'var(--text-dark)' }}>
                        {t.name}
                      </div>
                      <div className="text-[11px]" style={{ color: 'var(--text-mid)' }}>
                        {t.desc}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* STEP 2 — Topic + generate */}
      <div className="rounded-card p-5 mb-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
            style={{ background: 'var(--coral)', color: 'white' }}>
            Step 2
          </span>
          <h2 className="font-serif text-[18px]" style={{ color: 'var(--text-dark)' }}>
            What should it cover?
          </h2>
        </div>
        <p className="text-[12px] mb-3" style={{ color: 'var(--text-mid)' }}>
          {standardsCodes.length > 0
            ? 'Topic is optional when aligned to a standard — the standard itself defines what to cover.'
            : 'Describe the topic. Suggestions appear below to help you get specific.'}
        </p>

        {/* From-existing shortcut — shows when an assignment is selected */}
        {selectedAssignment && (
          <div className="mb-3 px-3 py-2 rounded-xl flex items-center gap-2 flex-wrap"
            style={{ background: 'rgba(78,140,150,0.1)', border: '1px solid rgba(78,140,150,0.3)' }}>
            <FileText className="w-4 h-4" style={{ color: 'var(--teal, #4E8C96)' }} />
            <span className="text-[12px] font-semibold" style={{ color: 'var(--text-dark)' }}>
              Using assignment: {selectedAssignment.title}
            </span>
            <button onClick={clearAssignment}
              className="ml-auto text-[11px] underline"
              style={{ color: 'var(--teal)', cursor: 'pointer' }}>
              Remove
            </button>
          </div>
        )}

        {/* Topic textarea — hidden when using an existing assignment */}
        {!selectedAssignment && (
          <>
            <textarea value={topic} onChange={e => setTopic(e.target.value)}
              placeholder={TOPIC_PLACEHOLDERS[selectedTemplate] || 'Describe the topic...'}
              rows={2}
              className="w-full rounded-xl p-3 text-[14px] outline-none resize-none"
              style={{
                border: '1px solid var(--border)', background: 'white',
                color: 'var(--text-dark)', fontFamily: "'Nunito', sans-serif",
              }} />

            {/* Inline suggestion pills (Pattern A) */}
            {suggestions.length > 0 && (
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <span className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider"
                  style={{ color: 'var(--sage)' }}>
                  <Lightbulb className="w-3 h-3" /> Get specific:
                </span>
                {suggestions.map(s => (
                  <button key={s} onClick={() => setTopic(s)}
                    className="text-[12px] px-3 py-1 rounded-full transition-all"
                    style={{
                      background: 'rgba(107,160,138,0.12)',
                      border: '1px solid rgba(107,160,138,0.4)',
                      color: 'var(--sage)',
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(107,160,138,0.2)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'rgba(107,160,138,0.12)'; }}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        {/* Secondary affordances — standards + existing */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {standardsCodes.map(code => (
            <span key={code} className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full font-bold"
              style={{ background: 'rgba(78,140,150,0.12)', color: 'var(--teal, #4E8C96)' }}>
              {code}
              <button onClick={() => setStandardsCodes(prev => prev.filter(c => c !== code))}
                style={{ color: 'var(--teal)', fontSize: 14, lineHeight: 1, cursor: 'pointer' }}>
                ×
              </button>
            </span>
          ))}
          {!selectedAssignment && (
            <button onClick={() => setShowStandardsPicker(true)}
              className="flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-full"
              style={{ border: '1px dashed var(--border)', background: 'white', color: 'var(--text-mid)', cursor: 'pointer' }}>
              <Target className="w-3 h-3" />
              {standardsCodes.length ? 'Add another standard' : 'Align to standard'}
            </button>
          )}
          {!selectedAssignment && (
            <button onClick={() => setShowAssignmentPicker(true)}
              className="flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-full"
              style={{ border: '1px dashed var(--border)', background: 'white', color: 'var(--text-mid)', cursor: 'pointer' }}>
              <FileText className="w-3 h-3" /> Use existing assignment
            </button>
          )}
        </div>

        {/* Generate button */}
        <button onClick={handleGenerate} disabled={!canGenerate}
          className="w-full mt-4 py-3 rounded-xl text-[14px] font-bold flex items-center justify-center gap-2"
          style={{
            background: canGenerate ? 'var(--coral)' : 'var(--coral-light)',
            color: 'white',
            cursor: canGenerate ? 'pointer' : 'not-allowed',
            opacity: canGenerate ? 1 : 0.6,
            boxShadow: canGenerate ? '0 4px 14px rgba(216,108,82,0.3)' : 'none',
          }}>
          {generating ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
          ) : (
            <><Sparkles className="w-4 h-4" /> Generate {selectedTemplateMeta?.name || 'activity'}</>
          )}
        </button>

        {generateError && (
          <div className="mt-3 p-3 rounded-xl text-[12px]"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #FECACA', color: '#B91C1C' }}>
            {generateError}
          </div>
        )}
      </div>

      {/* Current result — live iframe preview + refinement chips */}
      {lastResult && (
        <InteractiveResult
          activity={lastResult}
          onResult={(newActivity) => { setLastResult(newActivity); load(); }}
        />
      )}

      {/* Recent activities */}
      <div className="rounded-card p-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
          Your recent activities
        </h2>
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-28 rounded-xl animate-pulse" style={{ background: 'var(--cream)' }} />
            ))}
          </div>
        ) : activities.length === 0 ? (
          <div className="text-center py-8">
            <Gamepad2 className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-light)' }} />
            <p className="text-[13px]" style={{ color: 'var(--text-mid)' }}>
              No activities yet. Pick a type and topic above to get started.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {activities.map(a => <ActivityCard key={a.activity_id} activity={a} />)}
          </div>
        )}
      </div>

      {/* Modals */}
      {showStandardsPicker && (
        <StandardsPickerModal
          subject={activeClass?.subject}
          gradeLevel={activeClass?.grade_level}
          stateCode={activeClass?.state_code}
          initialSelected={standardsCodes}
          onConfirm={(codes) => { setStandardsCodes(codes); setShowStandardsPicker(false); }}
          onClose={() => setShowStandardsPicker(false)} />
      )}

      {showAssignmentPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6"
          style={{ background: 'rgba(60,40,20,0.6)', backdropFilter: 'blur(4px)' }}
          onClick={() => setShowAssignmentPicker(false)}>
          <div className="rounded-card p-5 max-w-lg w-full"
            style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
            onClick={e => e.stopPropagation()}>
            <h3 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
              Pick an existing assignment
            </h3>
            <AssignmentPicker onSelect={pickAssignment} selected={selectedAssignment?.assignment_id} />
          </div>
        </div>
      )}
    </div>
  );
}


function ActivityCard({ activity: a }) {
  const [copied, setCopied] = useState(false);
  const templateLabel = FLAT_TEMPLATES.find(t => t.id === a.interactive_template_id)?.name
    || (a.interactive_template_id || '').replace(/_/g, ' ');

  function copyCode() {
    navigator.clipboard?.writeText(a.access_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const status = a.status || 'draft';
  const statusColors = {
    live:   { bg: 'rgba(107,160,138,0.12)', fg: 'var(--sage)' },
    draft:  { bg: 'rgba(218,176,78,0.12)',  fg: 'var(--mustard, #DAB04E)' },
    failed: { bg: 'rgba(239,68,68,0.08)',   fg: '#B91C1C' },
  }[status] || { bg: 'var(--cream)', fg: 'var(--text-mid)' };

  return (
    <div className="rounded-xl p-3"
      style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
      <div className="flex items-start justify-between mb-1.5 gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wider truncate"
          style={{ color: 'var(--coral)' }}>
          {templateLabel}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold uppercase flex-shrink-0"
          style={{ background: statusColors.bg, color: statusColors.fg }}>
          {status}
        </span>
      </div>
      <p className="text-[13px] font-bold mb-2 line-clamp-2" style={{ color: 'var(--text-dark)' }}>
        {a.content_json?.title || 'Activity'}
      </p>
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-mono font-bold px-2 py-1 rounded-md"
          style={{ background: 'white', color: 'var(--coral)', border: '1px solid var(--border)' }}>
          {a.access_code}
        </span>
        <button onClick={copyCode} title="Copy code"
          className="p-1 rounded-md" style={{ color: 'var(--text-mid)', cursor: 'pointer' }}>
          {copied ? <CheckCircle className="w-3.5 h-3.5" style={{ color: 'var(--sage)' }} /> : <Copy className="w-3.5 h-3.5" />}
        </button>
        {a.access_url && (
          <a href={a.access_url} target="_blank" rel="noopener" title="Open activity"
            className="p-1 rounded-md ml-auto" style={{ color: 'var(--text-mid)' }}>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}
