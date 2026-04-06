'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Eye, Ban, CheckCircle, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import { adminFetch } from '@/lib/admin';

export default function AdminTeacherDetail() {
  const params = useParams();
  const router = useRouter();
  const [teacher, setTeacher] = useState(null);
  const [loading, setLoading] = useState(true);
  const [impersonating, setImpersonating] = useState(false);

  useEffect(() => {
    adminFetch(`/api/v1/admin/teachers/${params.id}`)
      .then(setTeacher)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [params.id]);

  async function handleImpersonate() {
    if (!confirm('This will be logged in the audit trail. Continue?')) return;
    setImpersonating(true);
    try {
      const data = await adminFetch(`/api/v1/admin/teachers/${params.id}/impersonate`, { method: 'POST' });
      window.open(`/?impersonate=${data.impersonation_token}`, '_blank');
    } catch (e) { alert(e.message); }
    finally { setImpersonating(false); }
  }

  async function handleSuspend() {
    if (!confirm('Suspend this teacher? They will not be able to log in.')) return;
    await adminFetch(`/api/v1/admin/teachers/${params.id}/suspend`, { method: 'POST' });
    setTeacher(t => ({ ...t, auth_provider: 'suspended' }));
  }

  async function handleUnsuspend() {
    await adminFetch(`/api/v1/admin/teachers/${params.id}/unsuspend`, { method: 'POST' });
    setTeacher(t => ({ ...t, auth_provider: 'email' }));
  }

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-white/50 rounded-[14px]" />)}</div>;
  if (!teacher) return <p className="text-red-500">Teacher not found</p>;

  const suspended = teacher.auth_provider === 'suspended';

  return (
    <div>
      <Link href="/admin/teachers" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to Teachers
      </Link>

      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* Profile */}
        <div className="col-span-2 bg-white rounded-[14px] p-6" style={{ border: '1px solid #E7E5E4' }}>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif" }}>{teacher.name}</h1>
              <p className="text-sm text-gray-500">{teacher.email}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-xs px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 border border-orange-200">{teacher.state_code || 'No state'}</span>
                {suspended && <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200">SUSPENDED</span>}
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleImpersonate} disabled={impersonating} className="bg-white hover:bg-orange-50 text-orange-600 border border-orange-200 px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1">
                <Eye className="w-3.5 h-3.5" /> Impersonate
              </button>
              {suspended ? (
                <button onClick={handleUnsuspend} className="bg-white hover:bg-green-50 text-green-600 border border-green-200 px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5" /> Unsuspend
                </button>
              ) : (
                <button onClick={handleSuspend} className="bg-white hover:bg-red-50 text-red-600 border border-red-200 px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1">
                  <Ban className="w-3.5 h-3.5" /> Suspend
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="bg-white rounded-[14px] p-6" style={{ border: '1px solid #E7E5E4' }}>
          <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: "'DM Serif Display', serif" }}>Usage</h3>
          <div className="space-y-2">
            {[
              { label: 'Generations', value: teacher.stats?.generations || 0 },
              { label: 'KB Sources', value: teacher.stats?.kb_sources || 0 },
              { label: 'Plans', value: teacher.stats?.plans || 0 },
              { label: 'Classes', value: teacher.classes?.length || 0 },
            ].map(s => (
              <div key={s.label} className="flex justify-between text-sm">
                <span className="text-gray-500">{s.label}</span>
                <span className="font-semibold text-gray-800">{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent assignments */}
      <div className="bg-white rounded-[14px] p-6" style={{ border: '1px solid #E7E5E4' }}>
        <h3 className="text-sm font-semibold mb-3" style={{ fontFamily: "'DM Serif Display', serif" }}>Recent Assignments</h3>
        {(teacher.recent_assignments || []).length === 0 ? (
          <p className="text-sm text-gray-400">No assignments yet</p>
        ) : (
          <div className="space-y-2">
            {teacher.recent_assignments.map(a => (
              <div key={a.assignment_id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <span className="text-sm text-gray-800">{a.title}</span>
                  <span className="text-xs text-gray-400 ml-2">{a.output_template_id}</span>
                </div>
                <span className="text-xs text-gray-400">{a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
