'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { PlusCircle, Upload, BookOpen, FileText, Database, CheckCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function DashboardHome() {
  const [stats, setStats] = useState({ frameworks: 0, sources: 0, assignments: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [fw, src] = await Promise.all([
          apiFetch('/api/v1/standards/frameworks').catch(() => ({ frameworks: [] })),
          apiFetch('/api/v1/knowledge/sources').catch(() => ({ sources: [] })),
        ]);
        setStats({
          frameworks: fw.frameworks?.length || 0,
          sources: src.sources?.length || 0,
          assignments: 0,
        });
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Welcome to Lulia</h1>
        <p className="text-sm text-gray-500 mt-1">Your AI teaching partner — generate standards-aligned content in seconds</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-50 rounded-lg flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900">
                {loading ? <span className="animate-pulse bg-gray-200 rounded w-8 h-6 inline-block" /> : stats.frameworks}
              </p>
              <p className="text-xs text-gray-400">Standards Frameworks</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-50 rounded-lg flex items-center justify-center">
              <Database className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900">
                {loading ? <span className="animate-pulse bg-gray-200 rounded w-8 h-6 inline-block" /> : stats.sources}
              </p>
              <p className="text-xs text-gray-400">KB Sources Uploaded</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-50 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-semibold text-gray-900">
                {loading ? <span className="animate-pulse bg-gray-200 rounded w-8 h-6 inline-block" /> : stats.assignments}
              </p>
              <p className="text-xs text-gray-400">Assignments Generated</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link href="/assignments/new" className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 hover:border-indigo-300 hover:shadow transition-all group">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center group-hover:bg-indigo-100 transition-colors">
              <PlusCircle className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-lg font-medium text-gray-900">New Assignment</h3>
              <p className="text-sm text-gray-500">Generate a standards-aligned worksheet, task cards, or quiz</p>
            </div>
          </div>
        </Link>

        <Link href="/library" className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 hover:border-indigo-300 hover:shadow transition-all group">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center group-hover:bg-emerald-100 transition-colors">
              <Upload className="w-6 h-6 text-emerald-600" />
            </div>
            <div>
              <h3 className="text-lg font-medium text-gray-900">Upload Materials</h3>
              <p className="text-sm text-gray-500">Add curriculum guides, textbooks, or teaching materials to your KB</p>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
