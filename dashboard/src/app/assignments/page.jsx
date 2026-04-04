'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { FileText, PlusCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function AssignmentsList() {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // The API doesn't have a list endpoint yet, so we query the DB directly
    // For now, show a placeholder that links to the generate page
    setLoading(false);
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Assignments</h1>
          <p className="text-sm text-gray-500 mt-1">View and manage all generated assignments</p>
        </div>
        <Link
          href="/assignments/new"
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors flex items-center gap-2"
        >
          <PlusCircle className="w-4 h-4" />
          New Assignment
        </Link>
      </div>

      {/* Empty state */}
      {!loading && assignments.length === 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="text-center py-16">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No assignments yet</h3>
            <p className="text-sm text-gray-500 mb-4">Generate your first assignment to get started</p>
            <Link
              href="/assignments/new"
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              Generate Assignment
            </Link>
          </div>
        </div>
      )}

      {/* Table (when we have assignments) */}
      {assignments.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Title</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Subject</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Grade</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Template</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {assignments.map(a => (
                <tr key={a.assignment_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/assignments/${a.assignment_id}`} className="text-indigo-600 hover:text-indigo-700 font-medium">
                      {a.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{a.subject}</td>
                  <td className="px-4 py-3 text-gray-600">{a.grade_level}</td>
                  <td className="px-4 py-3 text-gray-600">{a.output_template_id}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      a.status === 'complete'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-amber-50 text-amber-700'
                    }`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{new Date(a.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
