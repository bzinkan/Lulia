'use client';
import { useEffect, useState } from 'react';
import { Video, Play, Trash2, Download } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function VideosPage() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [assignmentId, setAssignmentId] = useState('');

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      const data = await apiFetch('/api/v1/videos');
      setVideos(data.videos || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function handleGenerate() {
    if (!assignmentId) return;
    setGenerating(true);
    try {
      await apiFetch('/api/v1/videos/generate', {
        method: 'POST',
        body: JSON.stringify({ assignment_id: assignmentId, target_duration: 240 }),
      });
      load();
    } catch (e) { alert(e.message); }
    finally { setGenerating(false); setAssignmentId(''); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Videos</h1>
          <p className="text-sm text-gray-500 mt-1">AI-generated educational videos with narration</p>
        </div>
      </div>

      {/* Quick generate */}
      <div className="bg-white rounded-[14px] p-4 mb-6 flex items-center gap-3" style={{ border: '1px solid #E7E5E4' }}>
        <input value={assignmentId} onChange={e => setAssignmentId(e.target.value)} placeholder="Assignment ID" className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none" />
        <button onClick={handleGenerate} disabled={generating} className="bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white px-4 py-2 rounded-xl font-medium text-sm flex items-center gap-2">
          {generating ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Video className="w-4 h-4" />}
          Generate Video
        </button>
      </div>

      {/* Videos grid */}
      {loading ? (
        <div className="animate-pulse grid grid-cols-2 md:grid-cols-3 gap-4">{[1,2,3].map(i => <div key={i} className="h-48 bg-white/50 rounded-[14px]" />)}</div>
      ) : videos.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <Video className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>No videos yet</h3>
          <p className="text-sm text-gray-500">Generate a video from any assignment</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map(v => (
            <div key={v.video_id} className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
              <div className="h-32 bg-gray-100 flex items-center justify-center relative">
                <Play className="w-12 h-12 text-gray-300" />
                {v.duration_seconds && (
                  <span className="absolute bottom-2 right-2 text-[10px] bg-black/60 text-white px-1.5 py-0.5 rounded">
                    {Math.floor(v.duration_seconds / 60)}:{String(v.duration_seconds % 60).padStart(2, '0')}
                  </span>
                )}
              </div>
              <div className="p-3">
                <p className="text-sm font-medium text-gray-800 truncate">{v.title || 'Untitled'}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[10px] text-gray-400">{v.created_at ? new Date(v.created_at).toLocaleDateString() : ''}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${v.status === 'complete' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>{v.status}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
