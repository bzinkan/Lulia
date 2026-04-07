'use client';
import { useEffect, useState } from 'react';
import { Users, Download, Copy, TrendingUp } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function CommunityPage() {
  const [shared, setShared] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/api/v1/share/popular/list')
      .then(d => setShared(d.shared || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleRemix(slug) {
    try {
      const res = await apiFetch(`/api/v1/share/${slug}/remix`, { method: 'POST' });
      alert(`Remixed! Assignment ID: ${res.assignment_id}`);
    } catch (e) { alert(e.message); }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Community</h1>
        <p className="text-sm text-gray-500 mt-1">Shared by Lulia teachers — remix for your classroom</p>
      </div>

      {loading ? (
        <div className="animate-pulse grid grid-cols-2 md:grid-cols-3 gap-4">{[1,2,3].map(i => <div key={i} className="h-40 bg-white/50 rounded-[14px]" />)}</div>
      ) : shared.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <Users className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>No shared content yet</h3>
          <p className="text-sm text-gray-500">Share your assignments to see them here</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {shared.map(s => (
            <div key={s.assignment_id} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
              <div className="flex items-start justify-between mb-2">
                <span className="text-xs font-medium uppercase text-orange-500">{s.output_template_id?.replace('_', ' ')}</span>
                {s.remix_count > 0 && (
                  <span className="text-[10px] flex items-center gap-1 text-gray-400"><TrendingUp className="w-3 h-3" /> {s.remix_count} remixes</span>
                )}
              </div>
              <p className="text-sm font-medium text-gray-800 mb-1">{s.title}</p>
              <p className="text-xs text-gray-400 mb-3">by {s.teacher_name || 'A Lulia Teacher'}</p>
              <div className="flex gap-2">
                <button onClick={() => handleRemix(s.share_slug)}
                  className="flex-1 text-center text-xs py-1.5 rounded-lg bg-orange-500 text-white hover:bg-orange-600 font-medium flex items-center justify-center gap-1">
                  <Copy className="w-3 h-3" /> Remix
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
