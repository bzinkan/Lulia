'use client';
import { useEffect, useState } from 'react';
import { Play, Upload, Clock, Tag, Filter, ExternalLink, Loader2, Video } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import VideoUploadModal from '@/components/VideoUploadModal';
import StandardsPickerModal from '@/components/StandardsPickerModal';

const TEACHER_ID = '00000000-0000-0000-0000-000000000001'; // TODO: replace with auth context

const BANDS = [
  { value: '', label: 'All grade bands' },
  { value: 'K-2', label: 'K-2' },
  { value: '3-5', label: '3-5' },
  { value: '6-8', label: '6-8' },
  { value: '9-12', label: '9-12' },
];

const SUBJECTS = [
  { value: '', label: 'All subjects' },
  { value: 'Math', label: 'Math' },
  { value: 'English Language Arts', label: 'English Language Arts' },
  { value: 'Science', label: 'Science' },
  { value: 'Social Studies', label: 'Social Studies' },
  { value: 'Art', label: 'Art' },
  { value: 'Music', label: 'Music' },
  { value: 'SEL', label: 'SEL' },
];

const SOURCE_LANES = [
  { value: '', label: 'All sources' },
  { value: 'lulia_signature', label: 'Lulia signature' },
  { value: 'teacher_upload', label: 'My uploads' },
  { value: 'youtube_embed', label: 'YouTube catalog' },
  { value: 'oer_public_domain', label: 'Public domain' },
  { value: 'generated', label: 'Lulia-generated' },
];

const LANE_BADGE = {
  lulia_signature: { label: 'Lulia signature', color: 'var(--coral)' },
  teacher_upload: { label: 'My upload', color: 'var(--sage)' },
  youtube_embed: { label: 'YouTube', color: '#FF0000' },
  oer_public_domain: { label: 'Public domain', color: '#4E8C96' },
  generated: { label: 'AI-generated', color: '#E9B44C' },
};


export default function VideoLibraryPage() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [gradeBand, setGradeBand] = useState('');
  const [subject, setSubject] = useState('');
  const [sourceLane, setSourceLane] = useState('');
  const [standardCode, setStandardCode] = useState('');
  const [showStandardsPicker, setShowStandardsPicker] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [preview, setPreview] = useState(null); // video object

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        teacher_id: TEACHER_ID,
        limit: '48',
      });
      if (gradeBand) params.set('grade_band', gradeBand);
      if (subject) params.set('subject', subject);
      if (sourceLane) params.set('source_lane', sourceLane);
      if (standardCode) params.set('standard_code', standardCode);
      const res = await apiFetch(`/api/v1/videos/library?${params.toString()}`);
      setVideos(res.videos || []);
    } catch (e) {
      console.error('Failed to load library:', e);
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [gradeBand, subject, sourceLane, standardCode]);

  const hasFilters = gradeBand || subject || sourceLane || standardCode;

  return (
    <div className="p-6 max-w-7xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-[32px]" style={{ color: 'var(--text-dark)' }}>
            Video Library
          </h1>
          <p className="text-[14px] mt-1" style={{ color: 'var(--text-mid)' }}>
            Standards-aligned videos for your classes. Browse curated content or upload your own.
          </p>
        </div>
        <button onClick={() => setShowUpload(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-[14px]"
          style={{ background: 'var(--coral)', color: 'white', border: 'none', cursor: 'pointer' }}>
          <Upload className="w-4 h-4" /> Upload video
        </button>
      </div>

      {/* Filter bar */}
      <div className="rounded-card p-4 mb-5 flex flex-wrap items-center gap-3"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <Filter className="w-4 h-4" style={{ color: 'var(--text-mid)' }} />
        <select value={gradeBand} onChange={(e) => setGradeBand(e.target.value)}
          className="rounded-xl px-3 py-2 text-[14px]"
          style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-dark)' }}>
          {BANDS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}
        </select>
        <select value={subject} onChange={(e) => setSubject(e.target.value)}
          className="rounded-xl px-3 py-2 text-[14px]"
          style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-dark)' }}>
          {SUBJECTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <select value={sourceLane} onChange={(e) => setSourceLane(e.target.value)}
          className="rounded-xl px-3 py-2 text-[14px]"
          style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-dark)' }}>
          {SOURCE_LANES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
        </select>
        <button onClick={() => setShowStandardsPicker(true)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-[14px]"
          style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-dark)', cursor: 'pointer' }}>
          <Tag className="w-4 h-4" />
          {standardCode ? standardCode : 'Filter by standard'}
        </button>
        {hasFilters && (
          <button onClick={() => { setGradeBand(''); setSubject(''); setSourceLane(''); setStandardCode(''); }}
            className="px-3 py-2 rounded-xl text-[13px]"
            style={{ background: 'transparent', color: 'var(--text-mid)', border: 'none', cursor: 'pointer' }}>
            Clear filters
          </button>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <div className="text-center py-16">
          <Loader2 className="w-8 h-8 mx-auto animate-spin" style={{ color: 'var(--coral)' }} />
        </div>
      ) : videos.length === 0 ? (
        <div className="rounded-card p-10 text-center"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          <Video className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-mid)' }} />
          <p className="font-serif text-[18px] mb-1" style={{ color: 'var(--text-dark)' }}>
            No videos yet
          </p>
          <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
            {hasFilters ? 'Try clearing some filters.' : 'Upload one to get started.'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
          {videos.map((v) => (
            <VideoCard key={v.video_id} video={v} onPreview={() => setPreview(v)} />
          ))}
        </div>
      )}

      {showUpload && (
        <VideoUploadModal
          teacherId={TEACHER_ID}
          onUploaded={() => { setShowUpload(false); load(); }}
          onClose={() => setShowUpload(false)} />
      )}

      {showStandardsPicker && (
        <StandardsPickerModal
          onSelect={(code) => { setStandardCode(code); setShowStandardsPicker(false); }}
          onClose={() => setShowStandardsPicker(false)} />
      )}

      {preview && <PreviewModal video={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}


function VideoCard({ video, onPreview }) {
  const lane = LANE_BADGE[video.source_lane] || { label: video.source_lane, color: 'var(--text-mid)' };
  const thumbSrc = video.thumbnail_url
    ? (video.thumbnail_url.startsWith('http')
        ? video.thumbnail_url
        : `${process.env.NEXT_PUBLIC_S3_PUBLIC_URL || 'http://localhost:9000/lulia-generated'}/${video.thumbnail_url}`)
    : video.hosting_type === 'youtube_embed' && video.youtube_video_id
      ? `https://img.youtube.com/vi/${video.youtube_video_id}/mqdefault.jpg`
      : null;

  return (
    <button onClick={onPreview}
      className="rounded-card overflow-hidden text-left flex flex-col hover:shadow-lg transition-shadow"
      style={{
        background: 'var(--warm-card)',
        border: '1px solid var(--border)',
        boxShadow: '0 2px 10px rgba(60,40,20,0.06)',
        cursor: 'pointer',
      }}>
      <div className="relative w-full aspect-video" style={{ background: 'var(--cream)' }}>
        {thumbSrc ? (
          <img src={thumbSrc} alt={video.title || ''} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Video className="w-10 h-10" style={{ color: 'var(--text-mid)' }} />
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity"
          style={{ background: 'rgba(60,40,20,0.3)' }}>
          <Play className="w-10 h-10" style={{ color: 'white' }} fill="white" />
        </div>
        {video.duration_seconds ? (
          <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded text-[11px] font-bold"
            style={{ background: 'rgba(0,0,0,0.7)', color: 'white' }}>
            {formatDuration(video.duration_seconds)}
          </span>
        ) : null}
      </div>
      <div className="p-3">
        <h3 className="font-serif text-[15px] mb-2 line-clamp-2" style={{ color: 'var(--text-dark)' }}>
          {video.title || 'Untitled'}
        </h3>
        <div className="flex items-center gap-2 flex-wrap text-[11px]">
          <span className="px-2 py-0.5 rounded-full font-bold"
            style={{ background: `${lane.color}1A`, color: lane.color }}>
            {lane.label}
          </span>
          {video.grade_level && (
            <span style={{ color: 'var(--text-mid)' }}>Gr {video.grade_level}</span>
          )}
          {video.subject && (
            <span style={{ color: 'var(--text-mid)' }}>· {video.subject}</span>
          )}
        </div>
        {video.domain && (
          <div className="text-[12px] mt-1 truncate" style={{ color: 'var(--text-mid)' }}>
            {video.domain}
          </div>
        )}
      </div>
    </button>
  );
}


function PreviewModal({ video, onClose }) {
  const isYouTube = video.hosting_type === 'youtube_embed' && video.youtube_video_id;
  const isExternal = video.hosting_type === 'external_url';
  const selfHostedSrc = !isYouTube && !isExternal && video.file_url
    ? (video.file_url.startsWith('http')
        ? video.file_url
        : `${process.env.NEXT_PUBLIC_S3_PUBLIC_URL || 'http://localhost:9000/lulia-generated'}/${video.file_url}`)
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(60,40,20,0.6)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}>
      <div className="rounded-card w-full max-w-3xl overflow-hidden"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}>
        <div className="relative w-full aspect-video" style={{ background: '#000' }}>
          {isYouTube ? (
            <iframe className="w-full h-full"
              src={`https://www.youtube.com/embed/${video.youtube_video_id}?autoplay=1`}
              allow="autoplay; encrypted-media; picture-in-picture"
              allowFullScreen />
          ) : isExternal ? (
            <div className="w-full h-full flex items-center justify-center">
              <a href={video.external_url} target="_blank" rel="noopener"
                className="flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-[14px]"
                style={{ background: 'var(--coral)', color: 'white' }}>
                <ExternalLink className="w-4 h-4" /> Open in new tab
              </a>
            </div>
          ) : selfHostedSrc ? (
            <video className="w-full h-full" src={selfHostedSrc} controls autoPlay />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-white">
              Video not available
            </div>
          )}
        </div>
        <div className="p-4">
          <h2 className="font-serif text-[22px] mb-1" style={{ color: 'var(--text-dark)' }}>
            {video.title}
          </h2>
          <div className="flex items-center gap-3 text-[13px] mb-2" style={{ color: 'var(--text-mid)' }}>
            {video.grade_level && <span>Grade {video.grade_level}</span>}
            {video.subject && <span>· {video.subject}</span>}
            {video.domain && <span>· {video.domain}</span>}
            {video.duration_seconds && (
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" /> {formatDuration(video.duration_seconds)}
              </span>
            )}
          </div>
          {video.attribution && (
            <div className="text-[12px]" style={{ color: 'var(--text-mid)' }}>
              Source: {video.attribution}{video.license ? ` · ${video.license}` : ''}
            </div>
          )}
          <div className="flex justify-end mt-4">
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[14px] font-bold"
              style={{ background: 'var(--coral)', color: 'white', border: 'none', cursor: 'pointer' }}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


function formatDuration(sec) {
  if (!sec) return '';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}
