'use client';
import { useEffect, useState } from 'react';
import { DollarSign } from 'lucide-react';
import { adminFetch } from '@/lib/admin';

export default function AdminBilling() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminFetch('/api/v1/admin/billing/overview').then(setData).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading || !data) return <div className="animate-pulse space-y-4">{[1,2].map(i => <div key={i} className="h-24 bg-white/50 rounded-[14px]" />)}</div>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Billing</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[
          { label: 'MRR', value: `$${data.mrr}`, color: '#059669' },
          { label: 'Basic', value: data.active_subscriptions?.basic || 0, color: '#F97316' },
          { label: 'Premium', value: data.active_subscriptions?.premium || 0, color: '#7C3AED' },
          { label: 'Churn Rate', value: `${data.churn_rate}%`, color: '#EF4444' },
          { label: 'Failed Payments', value: data.failed_payments, color: '#EF4444' },
          { label: 'Refunds MTD', value: data.refunds_mtd, color: '#D97706' },
        ].map(c => (
          <div key={c.label} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
            <p className="text-[10px] uppercase tracking-wider text-gray-400 mb-1">{c.label}</p>
            <p className="text-2xl font-bold" style={{ color: c.color }}>{c.value}</p>
          </div>
        ))}
      </div>
      <div className="mt-6 bg-white rounded-[14px] p-6 text-center" style={{ border: '1px solid #E7E5E4' }}>
        <DollarSign className="w-8 h-8 text-gray-300 mx-auto mb-2" />
        <p className="text-sm text-gray-500">Full billing integration coming in Phase 15 (Stripe)</p>
      </div>
    </div>
  );
}
