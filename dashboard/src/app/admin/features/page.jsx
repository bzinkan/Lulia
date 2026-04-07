'use client';
import { useEffect, useState } from 'react';
import { ToggleLeft, ToggleRight } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminFeatures() {
  const [features, setFeatures] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);
  async function load() {
    adminFetch('/api/v1/admin/features').then(d => setFeatures(d.features || [])).catch(console.error).finally(() => setLoading(false));
  }

  async function toggle(key, current) {
    await adminFetch(`/api/v1/admin/features/${key}`, { method: 'PUT', body: JSON.stringify({ default_enabled: !current }) });
    load();
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Feature Flags</h1>
      <div className="space-y-2">
        {features.map(f => (
          <div key={f.key} className="bg-white rounded-[14px] p-4 flex items-center justify-between" style={{ border: '1px solid #E7E5E4' }}>
            <div>
              <p className="text-sm font-medium text-gray-800">{f.name}</p>
              <p className="text-xs text-gray-400">{f.description}</p>
              <div className="flex gap-2 mt-1">
                {f.tier_required && <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-700">{f.tier_required}+</span>}
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{f.rollout_percentage}% rollout</span>
              </div>
            </div>
            <button onClick={() => toggle(f.key, f.default_enabled)}>
              {f.default_enabled ? <ToggleRight className="w-8 h-8 text-green-500" /> : <ToggleLeft className="w-8 h-8 text-gray-300" />}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
