'use client';
import { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Film, Play, Sparkles, Zap, BookOpen, Clock, AlertTriangle, Plus } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';
import ClipCostModal from '@/components/ClipCostModal';

const USE_CASES = [
  { icon: Zap,       title: 'Lesson hooks',      desc: '10-15 sec attention grabbers at the start of class.' },
  { icon: Sparkles,  title: 'Concept demos',     desc: '30-45 sec visual demos of abstract ideas.' },
  { icon: BookOpen,  title: 'Vocabulary intros', desc: '15-30 sec quick-cut definitions that stick.' },
  { icon: Clock,     title: 'End-of-unit recap', desc: '45-60 sec highlights of what you covered.' },
];

export default function ClipsPage() {
  const { activeClassId, classes, teacherId } = useClassContext();
  const activeClass = classes.find(c => c.class_id === activeClassId);

  const [balance, setBalance] = useState(null);
  const [clips, setClips] = useState([]);
  const [prompt, setPrompt] = useState('');
  const [topicLabel, setTopicLabel] = useState('');
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    apiFetch(`/api/v1/clips/balance?teacher_id=${teacherId}`).then(setBalance).catch(() => {});
    apiFetch(`/api/v1/clips?teacher_id=${teacherId}&limit=20`).then(d => setClips(d.clips || [])).catch(() => {});
  }, [teacherId]);

  function onGenerated(clip) {
    setClips([clip, ...clips]);
    apiFetch(`/api/v1/clips/balance?teacher_id=${teacherId}`).then(setBalance).catch(() => {});
    setPrompt('');
    setTopicLabel('');
  }

  const canOpenModal = prompt.trim().length >= 10;

  return (
    <div className="max-w-[1100px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-[14px] flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, var(--coral), var(--coral-light))', boxShadow: '0 4px 14px rgba(216,108,82,0.3)' }}>
            <Film className="w-6 h-6 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="font-serif text-[28px] leading-tight" style={{ color: 'var(--text-dark)' }}>
              Short Clips
            </h1>
            <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
              AI-generated video clips for your lessons.
            </p>
          </div>
        </div>

        {/* Balance chip */}
        {balance && (
          <div className="rounded-xl p-3 min-w-[200px]"
            style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-light)' }}>
                Credit balance
              </span>
              <span className="text-[16px] font-bold" style={{ color: 'var(--coral)' }}>
                {balance.total}
              </span>
            </div>
            <div className="text-[10px] mt-1" style={{ color: 'var(--text-light)' }}>
              {balance.monthly} monthly · {balance.purchased} purchased
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-mid)' }}>
              Up to <strong>{balance.max_seconds_affordable} sec</strong> of clip time
            </div>
          </div>
        )}
      </div>

      {/* Education section */}
      <div className="rounded-card p-5 mb-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
          What are Short Clips good for?
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {USE_CASES.map(u => (
            <div key={u.title} className="p-3 rounded-xl"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
              <u.icon className="w-5 h-5 mb-2" style={{ color: 'var(--coral)' }} />
              <h4 className="text-[12px] font-bold mb-1" style={{ color: 'var(--text-dark)' }}>{u.title}</h4>
              <p className="text-[11px]" style={{ color: 'var(--text-mid)' }}>{u.desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 p-2.5 rounded-lg flex items-start gap-2 text-[11px]"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)', color: 'var(--text-mid)' }}>
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#F59E0B' }} />
          <span>
            Clips use significant credits — 3 per second. A 30-second clip costs 90 credits.
            Save them for moments that really matter.
          </span>
        </div>
      </div>

      {/* Generator */}
      <div className="rounded-card p-5 mb-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
          Create a clip
        </h2>
        <div className="space-y-3">
          <div>
            <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
              Describe the clip
            </label>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
              rows={3}
              placeholder="e.g. A young student watching a volcano erupt in slow motion, with lava flowing into the ocean. Bright, dramatic, educational."
              className="w-full px-3 py-2 rounded-xl text-[13px]"
              style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }} />
            <p className="text-[10px] mt-1" style={{ color: 'var(--text-light)' }}>
              Be specific — describe the subject, setting, mood, and any motion.
              {prompt.trim().length < 10 && ' (At least 10 characters.)'}
            </p>
          </div>
          <div>
            <label className="block text-[12px] font-bold mb-1" style={{ color: 'var(--text-mid)' }}>
              Topic label <span style={{ color: 'var(--text-light)', fontWeight: 400 }}>(optional — helps you find it later)</span>
            </label>
            <input value={topicLabel} onChange={e => setTopicLabel(e.target.value)}
              placeholder="e.g. Volcano eruption demo"
              className="w-full px-3 py-2 rounded-xl text-[13px]"
              style={{ border: '1px solid var(--border)', background: 'white' }} />
          </div>
          <button onClick={() => setShowModal(true)} disabled={!canOpenModal}
            className="w-full py-3 rounded-xl text-[14px] font-bold text-white flex items-center justify-center gap-2 disabled:opacity-50"
            style={{ background: 'var(--coral)', boxShadow: '0 4px 14px rgba(216,108,82,0.3)' }}>
            <Play className="w-4 h-4" /> Preview &amp; Generate
          </button>
        </div>
      </div>

      {/* Recent clips */}
      <div className="rounded-card p-5"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <h2 className="font-serif text-[18px] mb-3" style={{ color: 'var(--text-dark)' }}>
          Your recent clips
        </h2>
        {clips.length === 0 ? (
          <p className="text-[13px] text-center py-6" style={{ color: 'var(--text-light)' }}>
            No clips yet. Generate one above to get started.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {clips.map(c => (
              <div key={c.clip_id} className="rounded-xl overflow-hidden"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                <div className="aspect-video flex items-center justify-center"
                  style={{ background: '#1F1B17' }}>
                  {c.primary_uri ? (
                    <video src={c.primary_uri} controls className="w-full h-full" />
                  ) : (
                    <Film className="w-8 h-8" style={{ color: 'var(--text-light)' }} />
                  )}
                </div>
                <div className="p-3">
                  <p className="text-[12px] font-bold mb-0.5" style={{ color: 'var(--text-dark)' }}>
                    {c.topic_label || (c.prompt || '').slice(0, 48)}
                  </p>
                  <div className="flex items-center justify-between text-[10px]" style={{ color: 'var(--text-light)' }}>
                    <span>{c.duration_sec}s · {c.credits_charged} credits</span>
                    <span>{c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showModal && (
        <ClipCostModal
          prompt={prompt}
          initialDuration={30}
          teacherId={teacherId}
          classId={activeClassId}
          topicLabel={topicLabel}
          onGenerated={onGenerated}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
