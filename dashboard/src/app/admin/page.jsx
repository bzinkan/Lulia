'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Users, Zap, Calendar, AlertTriangle, DollarSign, Database, FileText, BarChart3 } from 'lucide-react';
import { adminFetch, getAdminToken, setAdminToken } from '@/lib/admin';

export default function AdminOverview() {
  const router = useRouter();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showLogin, setShowLogin] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');

  useEffect(() => {
    if (!getAdminToken()) { setShowLogin(true); setLoading(false); return; }
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const data = await adminFetch('/api/v1/admin/overview');
      setStats(data);
    } catch (e) {
      setShowLogin(true);
    } finally { setLoading(false); }
  }

  async function handleLogin() {
    setLoginError('');
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${API}/api/v1/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) { setLoginError('Invalid credentials'); return; }
      const data = await res.json();
      setAdminToken(data.token);
      setShowLogin(false);
      loadStats();
    } catch (e) { setLoginError(e.message); }
  }

  if (showLogin) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="bg-white rounded-[14px] p-8 w-full max-w-sm" style={{ border: '1px solid #E7E5E4' }}>
          <h2 className="text-xl font-semibold text-center mb-6" style={{ fontFamily: "'DM Serif Display', serif" }}>Admin Login</h2>
          <div className="space-y-3">
            <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300" />
            <input value={password} onChange={e => setPassword(e.target.value)} type="password" placeholder="Password" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300" onKeyDown={e => e.key === 'Enter' && handleLogin()} />
            {loginError && <p className="text-xs text-red-500">{loginError}</p>}
            <button onClick={handleLogin} className="w-full bg-orange-500 hover:bg-orange-600 text-white py-2.5 rounded-xl font-medium text-sm">Sign In</button>
          </div>
        </div>
      </div>
    );
  }

  if (loading || !stats) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-white/50 rounded-[14px]" />)}</div>;

  const cards = [
    { label: 'Total Teachers', value: stats.total_teachers, icon: Users, color: '#F97316' },
    { label: 'Active (7d)', value: stats.active_teachers_7d, icon: Users, color: '#22C55E' },
    { label: 'Generations Today', value: stats.generations_today, icon: Zap, color: '#F97316' },
    { label: 'Generations (Week)', value: stats.generations_this_week, icon: Zap, color: '#FB923C' },
    { label: 'Plans (Week)', value: stats.plans_this_week, icon: Calendar, color: '#7C3AED' },
    { label: 'Errors (24h)', value: stats.errors_24h, icon: AlertTriangle, color: stats.errors_24h > 0 ? '#EF4444' : '#22C55E' },
    { label: 'KB Sources', value: stats.kb_sources_total, icon: Database, color: '#2563EB' },
    { label: 'Revenue MTD', value: `$${stats.revenue_mtd}`, icon: DollarSign, color: '#059669' },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>Overview</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {cards.map(c => (
          <div key={c.label} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
            <div className="flex items-center gap-2 mb-1">
              <c.icon className="w-4 h-4" style={{ color: c.color }} />
              <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{c.label}</span>
            </div>
            <p className="text-2xl font-bold" style={{ color: '#1C1917' }}>{c.value}</p>
          </div>
        ))}
      </div>

      {/* Quick totals */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
          <h3 className="text-sm font-semibold mb-2" style={{ fontFamily: "'DM Serif Display', serif" }}>Total Generations</h3>
          <p className="text-3xl font-bold text-orange-500">{stats.generations_total}</p>
        </div>
        <div className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
          <h3 className="text-sm font-semibold mb-2" style={{ fontFamily: "'DM Serif Display', serif" }}>Total Plans</h3>
          <p className="text-3xl font-bold text-purple-500">{stats.plans_total}</p>
        </div>
        <div className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
          <h3 className="text-sm font-semibold mb-2" style={{ fontFamily: "'DM Serif Display', serif" }}>KB Chunks</h3>
          <p className="text-3xl font-bold text-blue-500">{stats.kb_chunks_total}</p>
        </div>
      </div>
    </div>
  );
}
