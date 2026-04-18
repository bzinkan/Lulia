'use client';
import { useEffect, useState } from 'react';
import { X, Play, Check, Loader2, Video, Sparkles } from 'lucide-react';
import { apiFetch } from '@/lib/api';

/**
 * In-lesson video picker.
 *
 * Props:
 *   teacherId, classId — scope the library query
 *   standardCodes  — array of standard codes from the lesson (pre-filters results)
 *   gradeLevel     — optional grade hint for filtering
 *   subject        — optional subject hint
 *   onPick(video)  — callback when teacher selects a video
 *   onGenerate()   — callback for "Generate with Lulia" fallback (optional)
 *   onClose()      — dismiss modal
 *
 * Design: shows a grid of library matches, prioritized by "strong" alignment
 * to the lesson's standards. If no matches, offers a fallback to generate
 * via the existing video_crew pipeline.
 */
export default function VideoPickerModal({
  teacherId = '00000000-0000-0000-0000-000000000001',
  classId,
  standardCodes = [],
  gradeLevel,
  subject,
  onPick,
  onGenerate,
  onClose,
}) {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeStandard, setActiveStandard] = useState(standardCodes[0] || '');
  const [selected, setSelected] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams({ teacher_id: teacherId, limit: '24' });
      if (classId) params.set('class_id', classId);
      if (subject) params.set('subject', subject);
      if (activeStandard) params.set('standard_code', activeStandard);
      const res = await apiFetch(`/api/v1/videos/library?${params.toString()}`);
      setVideos(res.videos || []);
    } catch (e) {
      console.error('Picker load failed:', e);
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [activeStandard, subject, classId, teacherId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(60,40,20,0.55)', backdropFilter: 'blur(4px)' }}>
      <div className="rounded-card w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>

        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <div>
            <h2 className="font-serif text-[22px]" style={{ color: 'var(--text-dark)' }}>
              Pick a video
            </h2>
            <p className="text-[13px] mt-0.5" style={{ color: 'var(--text-mid)' }}>
              Library videos aligned to your lesson's standards.
            </p>
          </div>
          <button onClick={onClose}
            className="p-1 rounded-full hover:opacity-70"
            style={{ color: 'var(--text-mid)', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {standardCodes.length > 0 && (
          <div className="px-6 pb-3 flex items-center gap-2 flex-wrap">
            <span className="text-[12px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-mid)' }}>
              Standard:
            </span>
            {standardCodes.map(code => (
              <button key={code} onClick={() => setActiveStandard(code)}
                className="px-3 py-1 rounded-full text-[12px] font-bold"
                style={{
                  background: activeStandard === code ? 'var(--coral)' : 'var(--cream)',
                  color: activeStandard === code ? 'white' : 'var(--text-dark)',
                  border: activeStandard === code ? 'none' : '1px solid var(--border)',
                  cursor: 'pointer',
                }}>
                {code}
              </button>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-6 pb-4">
          {loading ? (
            <div className="text-center py-12">
              <Loader2 className="w-8 h-8 mx-auto animate-spin" style={{ color: 'var(--coral)' }} />
            </div>
          ) : videos.length === 0 ? (
            <div className="rounded-card p-8 text-center"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
              <Video className="w-10 h-10 mx-auto mb-2" style={{ color: 'var(--text-mid)' }} />
              <p className="font-serif text-[16px] mb-1" style={{ color: 'var(--text-dark)' }}>
                No library match for this standard yet
              </p>
              <p className="text-[13px] mb-4" style={{ color: 'var(--text-mid)' }}>
                Generate a Lulia video for this lesson instead.
              </p>
              {onGenerate && (
                <button onClick={onGenerate}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-[14px]"
                  style={{ background: 'var(--coral)', color: 'white', border: 'none', cursor: 'pointer' }}>
                  <Sparkles className="w-4 h-4" /> Generate with Lulia
                </button>
              )}
            </div>
          ) : (
            <div className="grid gap-3"
              style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
              {videos.map(v => (
                <PickCard key={v.video_id} video={v}
                  selected={selected?.video_id === v.video_id}
                  onClick={() => setSelected(v)} />
              ))}
            </div>
          )}
        </div>

        <div className="border-t px-6 py-3 flex items-center justify-between"
          style={{ borderColor: 'var(--border)' }}>
          <div className="text-[13px]" style={{ color: 'var(--text-mid)' }}>
            {selected ? (
              <span>
                Selected: <strong style={{ color: 'var(--text-dark)' }}>{selected.title}</strong>
              </span>
            ) : 'Click a card to select, then Add to lesson.'}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[14px]"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
              Cancel
            </button>
            <button onClick={() => selected && onPick?.(selected)}
              disabled={!selected}
              className="px-4 py-2 rounded-xl text-[14px] font-bold"
              style={{
                background: selected ? 'var(--coral)' : 'var(--cream)',
                color: selected ? 'white' : 'var(--text-mid)',
                border: 'none',
                cursor: selected ? 'pointer' : 'not-allowed',
                opacity: selected ? 1 : 0.6,
              }}>
              Add to lesson
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


function PickCard({ video, selected, onClick }) {
  const thumbSrc = video.thumbnail_url
    ? (video.thumbnail_url.startsWith('http')
        ? video.thumbnail_url
        : `${process.env.NEXT_PUBLIC_S3_PUBLIC_URL || 'http://localhost:9000/lulia-generated'}/${video.thumbnail_url}`)
    : video.hosting_type === 'youtube_embed' && video.youtube_video_id
      ? `https://img.youtube.com/vi/${video.youtube_video_id}/mqdefault.jpg`
      : null;

  return (
    <button onClick={onClick}
      className="rounded-xl overflow-hidden text-left relative"
      style={{
        background: 'var(--cream)',
        border: selected ? '2px solid var(--coral)' : '1px solid var(--border)',
        cursor: 'pointer',
        boxShadow: selected ? '0 0 0 3px rgba(216,108,82,0.2)' : 'none',
        transition: 'all 0.15s ease',
      }}>
      {selected && (
        <div className="absolute top-2 right-2 z-10 p-1 rounded-full"
          style={{ background: 'var(--coral)', color: 'white' }}>
          <Check className="w-4 h-4" strokeWidth={3} />
        </div>
      )}
      <div className="relative w-full aspect-video" style={{ background: '#000' }}>
        {thumbSrc ? (
          <img src={thumbSrc} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Play className="w-8 h-8" style={{ color: 'white' }} />
          </div>
        )}
        {video.duration_seconds ? (
          <span className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[10px] font-bold"
            style={{ background: 'rgba(0,0,0,0.75)', color: 'white' }}>
            {Math.floor(video.duration_seconds / 60)}:{(video.duration_seconds % 60).toString().padStart(2, '0')}
          </span>
        ) : null}
      </div>
      <div className="p-2">
        <div className="font-serif text-[13px] line-clamp-2" style={{ color: 'var(--text-dark)' }}>
          {video.title || 'Untitled'}
        </div>
        <div className="text-[11px] mt-0.5 truncate" style={{ color: 'var(--text-mid)' }}>
          {video.attribution || video.source_lane}
        </div>
      </div>
    </button>
  );
}
