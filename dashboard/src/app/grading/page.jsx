'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { CheckCircle, AlertTriangle, Camera, FileText } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function GradingPage() {
  const [submissions, setSubmissions] = useState([]);
  const [tab, setTab] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, [tab]);

  async function load() {
    try {
      const q = tab === 'review' ? '?status=needs_review' : tab === 'graded' ? '?status=graded' : '';
      const data = await apiFetch(`/api/v1/submissions${q}`);
      setSubmissions(data.submissions || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Grading</h1>
          <p className="text-sm text-gray-500 mt-1">Review submissions and manage grades</p>
        </div>
        <Link href="/grading/scan" className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm flex items-center gap-2">
          <Camera className="w-4 h-4" /> Scan & Grade
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {[
          { id: 'all', label: 'All' },
          { id: 'review', label: 'Needs Review' },
          { id: 'graded', label: 'Graded' },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === t.id ? 'bg-orange-500 text-white' : 'bg-white text-gray-600 border border-gray-200'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Submissions */}
      {loading ? (
        <div className="animate-pulse space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-white/50 rounded-[14px]" />)}</div>
      ) : submissions.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-1" style={{ fontFamily: "'DM Serif Display', serif" }}>No submissions yet</h3>
          <p className="text-sm text-gray-500 mb-4">Upload student work to get started with grading</p>
          <Link href="/grading/scan" className="inline-flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm">
            <Camera className="w-4 h-4" /> Scan & Grade
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-[14px] overflow-hidden" style={{ border: '1px solid #E7E5E4' }}>
          <table className="w-full text-sm">
            <thead><tr className="border-b" style={{ borderColor: '#F5F5F4' }}>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Student</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Method</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Status</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Flagged</th>
              <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-gray-400">Date</th>
            </tr></thead>
            <tbody className="divide-y" style={{ borderColor: '#F5F5F4' }}>
              {submissions.map(s => (
                <tr key={s.submission_id} className="hover:bg-orange-50/30 transition-colors cursor-pointer">
                  <td className="px-4 py-3 font-medium text-gray-800">{s.student_name || 'Unknown'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs uppercase">{s.submission_method}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
                      s.status === 'graded' ? 'bg-green-50 text-green-700' :
                      s.status === 'needs_review' ? 'bg-amber-50 text-amber-700' :
                      'bg-gray-50 text-gray-600'
                    }`}>
                      {s.status === 'needs_review' ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle className="w-3 h-3" />}
                      {s.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{(s.flagged_questions || []).length || '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{s.created_at ? new Date(s.created_at).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
