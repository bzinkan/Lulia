'use client';
import { useEffect, useState } from 'react';
import { Video, Play } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import GenerationTabs from '@/components/GenerationTabs';

export default function VideosPage() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  function load() {
    apiFetch('/api/v1/videos').then(d => setVideos(d.videos || [])).catch(console.error).finally(() => setLoading(false));
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Videos</h1>
        <p className="text-sm mt-1" style={{ color: '#78716C' }}>AI-generated educational videos with narration</p>
      </div>

      <div className="mb-6">
        <GenerationTabs outputType="video" templates={[]} templateLabel="Voice" onResult={load} />
      </div>

      {loading ? (
        <div className="animate-pulse grid grid-cols-2 md:grid-cols-3 gap-4">{[1,2,3].map(i => <div key={i} className="h-40 rounded-[14px]" style={{ background: '#F5F5F4' }} />)}</div>
      ) : videos.length === 0 ? (
        <div className="rounded-[14px] p-8 text-center" style={{ background: 'white', border: '1px solid #E7E5E4' }}>
          <Video className="w-10 h-10 mx-auto mb-2" style={{ color: '#E7E5E4' }} />
          <p className="text-sm" style={{ color: '#A8A29E' }}>Videos you create will appear here</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {videos.map(v => (
            <div key={v.video_id} className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
              <div className="h-32 flex items-center justify-center relative" style={{ background: '#F5F5F4' }}>
                <Play className="w-12 h-12" style={{ color: '#E7E5E4' }} />
                {v.duration_seconds > 0 && (
                  <span className="absolute bottom-2 right-2 text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(0,0,0,0.6)', color: 'white' }}>
                    {Math.floor(v.duration_seconds / 60)}:{String(v.duration_seconds % 60).padStart(2, '0')}
                  </span>
                )}
              </div>
              <div className="p-3">
                <p className="text-sm font-medium truncate" style={{ color: '#1C1917' }}>{v.title || 'Untitled'}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[10px]" style={{ color: '#A8A29E' }}>{v.created_at ? new Date(v.created_at).toLocaleDateString() : ''}</span>
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
