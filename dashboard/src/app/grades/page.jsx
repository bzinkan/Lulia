'use client';
import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { CheckCircle, AlertTriangle, Camera, FileText, Clock } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const TABS = [
  { id: 'review', label: 'Needs Review', status: 'needs_review' },
  { id: 'pending', label: 'Pending', status: 'pending' },
  { id: 'graded', label: 'Graded', status: 'graded' },
  { id: 'all', label: 'All', status: null },
];

function GradesInner() {
  const params = useSearchParams();
  const initialTab = params.get('filter') || 'review';
  const [tab, setTab] = useState(initialTab);
  const [submissions, setSubmissions] = useState([]);
  const [counts, setCounts] = useState({ review: 0, pending: 0, graded: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, [tab]);

  async function load() {
    setLoading(true);
    try {
      const t = TABS.find(x => x.id === tab);
      const q = t?.status ? `?status=${t.status}` : '';
      const data = await apiFetch(`/api/v1/submissions${q}`);
      setSubmissions(data.submissions || []);
      // Lightweight count update from current page only — good enough for v1
      if (tab === 'all' || tab === 'review') {
        const all = await apiFetch('/api/v1/submissions');
        const items = all.submissions || [];
        setCounts({
          review: items.filter(s => s.status === 'needs_review').length,
          pending: items.filter(s => s.status === 'pending').length,
          graded: items.filter(s => s.status === 'graded').length,
        });
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  return (
    <div className="max-w-[1100px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-[26px]" style={{ color: 'var(--text-dark)' }}>Grades</h1>
          <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
            Review submissions and manage grades
          </p>
        </div>
        <Link href="/grading/scan"
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-[13px] font-semibold text-white"
          style={{ background: 'var(--coral)' }}>
          <Camera className="w-4 h-4" /> Scan &amp; Grade
        </Link>
      </div>

      {/* Tabs with badges */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {TABS.map(t => {
          const count = counts[t.id];
          const active = tab === t.id;
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className="px-3 py-1.5 rounded-xl text-[13px] font-semibold flex items-center gap-2"
              style={active
                ? { background: 'var(--coral)', color: 'white' }
                : { background: 'var(--cream)', color: 'var(--text-mid)', border: '1px solid var(--border)' }}>
              {t.label}
              {count > 0 && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                  style={active
                    ? { background: 'rgba(255,255,255,0.25)', color: 'white' }
                    : { background: 'var(--warm-card)', color: 'var(--coral)' }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Submissions */}
      {loading ? (
        <div className="space-y-2">
          {[1,2,3].map(i => (
            <div key={i} className="rounded-card animate-pulse"
              style={{ background: 'var(--warm-card)', border: '1px solid var(--border)', height: 64 }} />
          ))}
        </div>
      ) : submissions.length === 0 ? (
        <div className="rounded-card p-12 text-center"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          <CheckCircle className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--sage)', opacity: 0.4 }} />
          <h3 className="font-serif text-[18px] mb-1" style={{ color: 'var(--text-dark)' }}>
            {tab === 'review' ? 'All caught up!' : 'No submissions yet'}
          </h3>
          <p className="text-[13px] mb-4" style={{ color: 'var(--text-mid)' }}>
            {tab === 'review'
              ? 'Nothing needs your review right now.'
              : 'Upload student work to get started.'}
          </p>
          <Link href="/grading/scan"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-[13px] font-semibold text-white"
            style={{ background: 'var(--coral)' }}>
            <Camera className="w-4 h-4" /> Scan &amp; Grade
          </Link>
        </div>
      ) : (
        <div className="rounded-card overflow-hidden"
          style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
          <table className="w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Student', 'Assignment', 'Method', 'Status', 'Score', 'Date'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-[10px] uppercase tracking-wider font-bold"
                    style={{ color: 'var(--text-light)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {submissions.map(s => (
                <tr key={s.submission_id}
                  className="cursor-pointer transition-colors"
                  style={{ borderBottom: '1px solid var(--border)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--cream)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td className="px-4 py-3 text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                    {s.student_name || 'Unknown'}
                  </td>
                  <td className="px-4 py-3 text-[12px]" style={{ color: 'var(--text-mid)' }}>
                    {s.assignment_title || '—'}
                  </td>
                  <td className="px-4 py-3 text-[11px] uppercase font-semibold" style={{ color: 'var(--text-light)' }}>
                    {s.submission_method || s.item_type || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill status={s.status} />
                  </td>
                  <td className="px-4 py-3 text-[13px] font-bold" style={{ color: 'var(--coral)' }}>
                    {s.percentage != null ? `${s.percentage}%` : '—'}
                  </td>
                  <td className="px-4 py-3 text-[11px]" style={{ color: 'var(--text-light)' }}>
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    needs_review: { Icon: AlertTriangle, color: '#F59E0B', bg: 'rgba(245,158,11,0.1)', label: 'Needs Review' },
    pending:      { Icon: Clock,         color: '#3B82F6', bg: 'rgba(59,130,246,0.1)', label: 'Pending' },
    graded:       { Icon: CheckCircle,   color: '#16A34A', bg: 'rgba(22,163,74,0.1)',  label: 'Graded' },
  };
  const cfg = map[status] || { Icon: FileText, color: 'var(--text-light)', bg: 'var(--cream)', label: status || 'unknown' };
  const { Icon } = cfg;
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full"
      style={{ background: cfg.bg, color: cfg.color }}>
      <Icon className="w-3 h-3" /> {cfg.label}
    </span>
  );
}

export default function GradesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-[13px]" style={{ color: 'var(--text-light)' }}>Loading…</div>}>
      <GradesInner />
    </Suspense>
  );
}
