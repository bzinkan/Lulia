'use client';
import { useEffect, useState } from 'react';
import { DollarSign } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminCosts() {
  const [costs, setCosts] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminFetch('/api/v1/admin/costs')
      .then(setCosts)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading || !costs) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-white/50 rounded-[14px]" />)}</div>;

  const items = [
    { label: 'Anthropic (Claude)', value: costs.anthropic_cost_mtd, color: '#F97316' },
    { label: 'Gemini (Google)', value: costs.gemini_cost_mtd, color: '#2563EB' },
    { label: 'Bedrock (AWS)', value: costs.bedrock_cost_mtd, color: '#7C3AED' },
    { label: 'AWS Infrastructure', value: costs.aws_infra_cost_mtd, color: '#059669' },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Cost Tracking</h1>

      {/* Total */}
      <div className="bg-white rounded-[14px] p-6 mb-6 text-center" style={{ border: '1px solid #E7E5E4' }}>
        <p className="text-[10px] uppercase tracking-wider text-gray-400 mb-1">Total Cost (Month to Date)</p>
        <p className="text-4xl font-bold text-orange-500">${costs.total_cost_mtd}</p>
        <p className="text-sm text-gray-500 mt-1">${costs.cost_per_teacher}/teacher · {costs.generations_mtd} generations</p>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {items.map(item => (
          <div key={item.label} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
            <p className="text-[10px] uppercase tracking-wider text-gray-400 mb-1">{item.label}</p>
            <p className="text-xl font-bold" style={{ color: item.color }}>${item.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
