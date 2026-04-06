'use client';
import { useEffect, useState } from 'react';
import { Zap, Upload, Calendar } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

const TYPE_ICONS = { generation: Zap, upload: Upload, plan: Calendar };
const TYPE_COLORS = { generation: '#F97316', upload: '#2563EB', plan: '#7C3AED' };

export default function AdminActivity() {
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminFetch('/api/v1/admin/activity?limit=100')
      .then(d => setActivity(d.activity || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Activity Feed</h1>
      <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : activity.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No activity yet</div>
        ) : (
          <div className="divide-y" style={{ borderColor: '#F5F5F4' }}>
            {activity.map((a, i) => {
              const Icon = TYPE_ICONS[a.type] || Zap;
              const color = TYPE_COLORS[a.type] || '#A8A29E';
              return (
                <div key={i} className="flex items-center gap-3 px-4 py-3 hover:bg-orange-50/30 transition-colors">
                  <Icon className="w-4 h-4" style={{ color }} />
                  <span className="text-xs font-medium uppercase px-1.5 py-0.5 rounded" style={{ background: `${color}15`, color }}>{a.type}</span>
                  <span className="text-sm text-gray-800 flex-1">{a.detail}</span>
                  <span className="text-xs text-gray-400">{a.created_at ? new Date(a.created_at).toLocaleString() : ''}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
