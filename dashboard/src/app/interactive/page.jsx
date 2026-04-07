'use client';
import { useEffect, useState } from 'react';
import { Gamepad2, Copy, Users, ExternalLink } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import GenerationTabs from '@/components/GenerationTabs';

const TEMPLATES = [
  { id: 'multiple_choice_quiz', name: 'Multiple Choice Quiz' },
  { id: 'drag_drop_sort', name: 'Drag & Drop Sort' },
  { id: 'matching_pairs', name: 'Matching Pairs' },
  { id: 'fill_in_blank', name: 'Fill in the Blank' },
  { id: 'click_to_reveal', name: 'Click to Reveal' },
  { id: 'flash_cards_interactive', name: 'Flashcards' },
  { id: 'category_sort', name: 'Category Sort' },
  { id: 'word_search_interactive', name: 'Word Search' },
  { id: 'crossword_interactive', name: 'Crossword' },
];

export default function InteractivePage() {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  function load() {
    apiFetch('/api/v1/interactive').then(d => setActivities(d.activities || [])).catch(console.error).finally(() => setLoading(false));
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Interactive Activities</h1>
        <p className="text-sm mt-1" style={{ color: '#78716C' }}>Web-based student activities with instant feedback</p>
      </div>

      <div className="mb-6">
        <GenerationTabs outputType="interactive" templates={TEMPLATES} templateLabel="Activity Type" onResult={load} />
      </div>

      {loading ? (
        <div className="animate-pulse grid grid-cols-2 md:grid-cols-3 gap-4">{[1,2,3].map(i => <div key={i} className="h-32 rounded-[14px]" style={{ background: '#F5F5F4' }} />)}</div>
      ) : activities.length === 0 ? (
        <div className="rounded-[14px] p-8 text-center" style={{ background: 'white', border: '1px solid #E7E5E4' }}>
          <Gamepad2 className="w-10 h-10 mx-auto mb-2" style={{ color: '#E7E5E4' }} />
          <p className="text-sm" style={{ color: '#A8A29E' }}>Activities you create will appear here</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activities.map(a => (
            <div key={a.activity_id} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
              <div className="flex items-start justify-between mb-2">
                <span className="text-xs font-medium uppercase" style={{ color: '#F97316' }}>{a.interactive_template_id?.replace(/_/g, ' ')}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${a.status === 'live' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>{a.status}</span>
              </div>
              <p className="text-sm font-medium mb-2" style={{ color: '#1C1917' }}>{a.content_json?.title || 'Activity'}</p>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-mono px-2 py-1 rounded" style={{ background: '#F5F5F4', color: '#1C1917' }}>{a.access_code}</span>
                <button onClick={() => navigator.clipboard?.writeText(a.access_code)} style={{ color: '#A8A29E' }}><Copy className="w-3.5 h-3.5" /></button>
                {a.access_url && <a href={a.access_url} target="_blank" rel="noopener" style={{ color: '#A8A29E' }}><ExternalLink className="w-3.5 h-3.5" /></a>}
              </div>
              <div className="flex items-center justify-between text-xs" style={{ color: '#A8A29E' }}>
                <span className="flex items-center gap-1"><Users className="w-3 h-3" /> {a.submission_count || 0}</span>
                <span>{a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
