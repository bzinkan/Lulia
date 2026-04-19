'use client';
import { useEffect, useState } from 'react';
import Image from 'next/image';
import { Gamepad2, Copy, ExternalLink, Loader2, CheckCircle, AlertTriangle } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import GenerationTabs from '@/components/GenerationTabs';
import { useClassContext } from '@/components/ClassContext';

// All 15 interactive activity templates, grouped by pedagogical purpose.
// Order matches tools/interactive_generator.py INTERACTIVE_TEMPLATES.
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

export default function InteractivePage() {
  const { classes, activeClassId } = useClassContext();
  const activeClass = classes.find(c => c.class_id === activeClassId);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState(FLAT_TEMPLATES[0].id);

  useEffect(() => { load(); }, []);

  function load() {
    apiFetch('/api/v1/interactive')
      .then(d => setActivities(d.activities || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  return (
    <div className="max-w-[1100px] mx-auto">
      {/* Header — matches Short Clips page pattern */}
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
              Web-based student activities with instant feedback. 15 formats across quiz, drag-drop, study tools, puzzles, and subject-specific.
            </p>
          </div>
        </div>
      </div>

      {/* Generation card */}
      <div className="mb-5">
        <GenerationTabs
          outputType="interactive"
          templates={FLAT_TEMPLATES}
          templateLabel="Activity Type"
          activeClass={activeClass}
          selectedTemplate={selectedTemplate}
          onTemplateChange={setSelectedTemplate}
          onResult={load}
        />
      </div>

      {/* Template gallery — tiles are the primary picker. Click to select. */}
      <div className="rounded-card p-5 mb-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-1" style={{ color: 'var(--text-dark)' }}>
          Pick an activity type
        </h2>
        <p className="text-[12px] mb-4" style={{ color: 'var(--text-mid)' }}>
          Click any tile to select it, then generate above. All 15 types are grouped by purpose.
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

      {/* Recent activities */}
      <div className="rounded-card p-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
          Your recent activities
        </h2>
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-28 rounded-xl animate-pulse"
                style={{ background: 'var(--cream)' }} />
            ))}
          </div>
        ) : activities.length === 0 ? (
          <div className="text-center py-8">
            <Gamepad2 className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-light)' }} />
            <p className="text-[13px]" style={{ color: 'var(--text-mid)' }}>
              No activities yet. Generate one above to get started.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {activities.map(a => (
              <ActivityCard key={a.activity_id} activity={a} />
            ))}
          </div>
        )}
      </div>
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
    live:    { bg: 'rgba(107,160,138,0.12)', fg: 'var(--sage)' },
    draft:   { bg: 'rgba(218,176,78,0.12)',  fg: 'var(--mustard, #DAB04E)' },
    failed:  { bg: 'rgba(239,68,68,0.08)',    fg: '#B91C1C' },
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
