'use client';
import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminFetch('/api/v1/admin/health')
      .then(setHealth)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading || !health) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-white/50 rounded-[14px]" />)}</div>;

  function StatusIcon({ status }) {
    if (status === 'healthy' || status === 'configured') return <CheckCircle className="w-5 h-5 text-green-500" />;
    if (status === 'error') return <XCircle className="w-5 h-5 text-red-500" />;
    return <AlertTriangle className="w-5 h-5 text-amber-500" />;
  }

  const services = [
    { label: 'Database', ...health.database },
    { label: 'Storage (MinIO/S3)', ...health.storage },
    { label: 'Anthropic API', ...health.anthropic },
    { label: 'Gemini API', ...health.gemini },
    { label: 'AWS Bedrock', ...health.bedrock },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>System Health</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {services.map(s => (
          <div key={s.label} className="bg-white rounded-[14px] p-4 flex items-center gap-3" style={{ border: '1px solid #E7E5E4' }}>
            <StatusIcon status={s.status} />
            <div>
              <p className="text-sm font-medium text-gray-800">{s.label}</p>
              <p className="text-xs text-gray-400">{s.status}{s.size_bytes ? ` · ${(s.size_bytes / 1024 / 1024).toFixed(1)} MB` : ''}{s.buckets ? ` · ${s.buckets} buckets` : ''}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
        <p className="text-sm"><strong>Event Queue:</strong> {health.event_queue?.pending || 0} pending</p>
        <p className="text-sm"><strong>Failed Jobs (24h):</strong> {health.failed_jobs_24h || 0}</p>
      </div>
    </div>
  );
}
