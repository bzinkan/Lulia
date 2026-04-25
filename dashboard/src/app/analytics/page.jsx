'use client';
import { useEffect, useState } from 'react';
import { BarChart3, Users, BookOpen, AlertTriangle, CheckCircle, TrendingUp, FileText } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { useClassContext } from '@/components/ClassContext';

export default function AnalyticsPage() {
  const { activeClassId } = useClassContext();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reportHtml, setReportHtml] = useState(null);

  useEffect(() => {
    if (!activeClassId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    apiFetch(`/api/v1/analytics/class/${activeClassId}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeClassId]);

  async function generateReport() {
    if (!activeClassId) return;
    const res = await apiFetch(`/api/v1/analytics/reports/generate?class_id=${activeClassId}&report_type=class`, { method: 'POST' });
    setReportHtml(res.report_html);
  }

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-white/50 rounded-[14px]" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Analytics</h1>
          <p className="text-sm text-gray-500 mt-1">Class performance, standards mastery, and AI insights</p>
        </div>
        <button onClick={generateReport} className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-medium text-sm flex items-center gap-2">
          <FileText className="w-4 h-4" /> Generate Report
        </button>
      </div>

      {!data ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <BarChart3 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>No analytics data yet</h3>
          <p className="text-sm text-gray-500">Grade some assignments first to see analytics</p>
        </div>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard icon={Users} label="Students" value={data.total_students} color="#F97316" />
            <StatCard icon={TrendingUp} label="Class Average" value={`${data.class_average}%`} color={data.class_average >= 70 ? '#059669' : '#D97706'} />
            <StatCard icon={CheckCircle} label="Mastered" value={data.mastered_count} color="#059669" />
            <StatCard icon={AlertTriangle} label="Needs Work" value={data.needs_work_count} color={data.needs_work_count > 0 ? '#EF4444' : '#059669'} />
          </div>

          {/* Standards Heatmap */}
          <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
            <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: "'DM Serif Display', serif" }}>Standards Mastery</h2>
            <div className="space-y-2">
              {(data.standards || []).map(s => (
                <div key={s.standard_code} className="flex items-center gap-3">
                  <span className="text-xs font-medium text-gray-700 min-w-[80px]">{s.standard_code}</span>
                  <div className="flex-1 h-5 rounded-full overflow-hidden" style={{ background: '#F5F5F4' }}>
                    <div className="h-full rounded-full transition-all" style={{
                      width: `${Math.min(s.mastery_percent, 100)}%`,
                      background: s.mastery_percent >= 80 ? '#059669' : s.mastery_percent >= 60 ? '#D97706' : '#EF4444',
                    }} />
                  </div>
                  <span className="text-xs font-semibold min-w-[40px] text-right" style={{
                    color: s.mastery_percent >= 80 ? '#059669' : s.mastery_percent >= 60 ? '#D97706' : '#EF4444',
                  }}>{s.mastery_percent}%</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    s.status === 'mastered' ? 'bg-green-50 text-green-700' :
                    s.status === 'developing' ? 'bg-amber-50 text-amber-700' :
                    'bg-red-50 text-red-700'
                  }`}>{s.status}</span>
                </div>
              ))}
              {(data.standards || []).length === 0 && <p className="text-sm text-gray-400">No standards data yet</p>}
            </div>
          </div>

          {/* Insights */}
          {data.insights?.length > 0 && (
            <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
              <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: "'DM Serif Display', serif" }}>AI Insights</h2>
              <div className="space-y-3">
                {data.insights.map((ins, i) => (
                  <div key={i} className={`p-3 rounded-xl border ${
                    ins.type === 'celebration' ? 'bg-green-50 border-green-200' :
                    ins.type === 'concern' ? 'bg-red-50 border-red-200' :
                    ins.type === 'action' ? 'bg-amber-50 border-amber-200' :
                    'bg-blue-50 border-blue-200'
                  }`}>
                    <p className="text-sm font-medium text-gray-800">{ins.message}</p>
                    <p className="text-xs text-gray-500 mt-1">{ins.action}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Report preview */}
          {reportHtml && (
            <div className="bg-white rounded-[14px] p-1 mb-6" style={{ border: '1px solid #E7E5E4' }}>
              <iframe srcDoc={reportHtml} className="w-full min-h-[600px] rounded-lg" title="Report" />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4" style={{ color }} />
        <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{label}</span>
      </div>
      <p className="text-2xl font-bold" style={{ color: '#1C1917' }}>{value}</p>
    </div>
  );
}
