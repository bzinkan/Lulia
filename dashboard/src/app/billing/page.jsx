'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Zap, CreditCard, TrendingUp, ArrowUpRight, ShoppingCart } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const TIER_NAMES = { free: 'Free', basic: 'Basic', plus: 'Plus', premium: 'Premium', max: 'Max' };
const TIER_COLORS = { free: '#A8A29E', basic: '#F97316', plus: '#7C3AED', premium: '#059669', max: '#2563EB' };

export default function BillingPage() {
  const [billing, setBilling] = useState(null);
  const [usage, setUsage] = useState(null);
  const [packs, setPacks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/billing/me').then(setBilling),
      apiFetch('/api/v1/billing/usage').then(setUsage),
      apiFetch('/api/v1/billing/credit-packs').then(d => setPacks(d.packs || [])),
    ]).catch(console.error).finally(() => setLoading(false));
  }, []);

  async function handleUpgrade(tier) {
    const res = await apiFetch('/api/v1/billing/checkout/subscription', {
      method: 'POST', body: JSON.stringify({ tier }),
    });
    if (res.checkout_url) window.location.href = res.checkout_url;
  }

  async function handleBuyCredits(packId) {
    const res = await apiFetch('/api/v1/billing/checkout/credits', {
      method: 'POST', body: JSON.stringify({ pack_id: packId }),
    });
    if (res.checkout_url) window.location.href = res.checkout_url;
  }

  async function handlePortal() {
    const res = await apiFetch('/api/v1/billing/portal', { method: 'POST' });
    if (res.portal_url) window.location.href = res.portal_url;
  }

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-white/50 rounded-[14px]" />)}</div>;

  const tier = billing?.tier || 'free';
  const balance = billing?.credit_balance || 0;
  const monthly = billing?.credits_per_month || 25;
  const usedPct = monthly > 0 ? Math.min(((monthly - balance) / monthly) * 100, 100) : 0;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Billing & Credits</h1>
      </div>

      {/* Current Plan */}
      <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <span className="text-[10px] uppercase tracking-wider text-gray-400">Current Plan</span>
            <h2 className="text-2xl font-bold" style={{ color: TIER_COLORS[tier], fontFamily: "'DM Serif Display', serif" }}>
              {TIER_NAMES[tier]}
            </h2>
          </div>
          <div className="flex gap-2">
            {tier !== 'max' && (
              <button onClick={() => handleUpgrade(tier === 'free' ? 'basic' : tier === 'basic' ? 'plus' : tier === 'plus' ? 'premium' : 'max')}
                className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" /> Upgrade
              </button>
            )}
            {tier !== 'free' && (
              <button onClick={handlePortal} className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 px-4 py-2 rounded-xl text-sm font-medium">
                Manage Subscription
              </button>
            )}
          </div>
        </div>

        {/* Credit bar */}
        <div className="mb-2">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Credits this month</span>
            <span className="font-semibold" style={{ color: TIER_COLORS[tier] }}>{balance} / {monthly === -1 ? '∞' : monthly}</span>
          </div>
          {monthly > 0 && (
            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${100 - usedPct}%`, background: TIER_COLORS[tier] }} />
            </div>
          )}
        </div>
      </div>

      {/* Usage breakdown */}
      {usage?.usage?.length > 0 && (
        <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: "'DM Serif Display', serif" }}>This Month's Usage</h3>
          <div className="space-y-2">
            {usage.usage.map(u => (
              <div key={u.reference_type} className="flex items-center justify-between text-sm">
                <span className="text-gray-600 capitalize">{(u.reference_type || 'other').replace('_', ' ')}</span>
                <span className="font-medium text-gray-800">{u.credits_used} credits ({u.count} items)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Credit Packs */}
      <h3 className="text-lg font-semibold mb-3" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Buy More Credits</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {packs.map(p => (
          <div key={p.id} className="bg-white rounded-[14px] p-4 text-center" style={{ border: '1px solid #E7E5E4' }}>
            <Zap className="w-6 h-6 text-orange-400 mx-auto mb-2" />
            <p className="text-lg font-bold text-gray-800">{p.credits}</p>
            <p className="text-xs text-gray-400 mb-1">credits</p>
            <p className="text-sm font-semibold text-orange-500">${(p.price_cents / 100).toFixed(2)}</p>
            {p.savings && <p className="text-[10px] text-green-600 font-medium">Save {p.savings}</p>}
            <button onClick={() => handleBuyCredits(p.id)}
              className="mt-2 w-full bg-orange-50 text-orange-700 border border-orange-200 py-1.5 rounded-lg text-xs font-medium hover:bg-orange-100">
              Buy Now
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
