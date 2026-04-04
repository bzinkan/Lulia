'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Download, BookOpen, CheckCircle, AlertCircle } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function AssignmentDetail() {
  const params = useParams();
  const [assignment, setAssignment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('student');
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch(`/api/v1/assignments/${params.id}`);
        setAssignment(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    if (params.id) load();
  }, [params.id]);

  function downloadHtml(html, filename) {
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-gray-200 rounded w-1/3"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        <div className="h-96 bg-gray-200 rounded-xl"></div>
      </div>
    );
  }

  if (error || !assignment) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
        <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-700">{error || 'Assignment not found'}</p>
        <Link href="/assignments" className="text-indigo-600 hover:text-indigo-700 text-sm mt-2 inline-block">
          Back to assignments
        </Link>
      </div>
    );
  }

  const questions = assignment.questions || [];
  const qaReport = assignment.qa_report || {};

  return (
    <div>
      {/* Back link */}
      <Link href="/assignments" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft className="w-4 h-4" />
        Back to Assignments
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{assignment.title}</h1>
          <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
            <span className="capitalize">{assignment.output_template_id?.replace('_', ' ')}</span>
            <span>·</span>
            <span>{questions.length} questions</span>
            <span>·</span>
            <span>{new Date(assignment.created_at).toLocaleDateString()}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => downloadHtml('<html><body>Student version</body></html>', `${assignment.title} - Student.html`)}
            className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 px-3 py-2 rounded-lg font-medium text-sm transition-colors flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download
          </button>
        </div>
      </div>

      {/* Metadata cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {/* Standards */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
          <div className="flex items-center gap-2 mb-2">
            <BookOpen className="w-4 h-4 text-indigo-600" />
            <span className="text-sm font-medium text-gray-700">Standards</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {(assignment.standards_ids || []).map(code => (
              <span key={code} className="inline-block bg-indigo-50 text-indigo-700 text-xs px-2 py-0.5 rounded-full">
                {code}
              </span>
            ))}
          </div>
        </div>

        {/* QA Report */}
        <div className={`rounded-xl border shadow-sm p-4 ${
          qaReport.approved
            ? 'bg-emerald-50 border-emerald-200'
            : 'bg-amber-50 border-amber-200'
        }`}>
          <div className="flex items-center gap-2 mb-2">
            {qaReport.approved
              ? <CheckCircle className="w-4 h-4 text-emerald-600" />
              : <AlertCircle className="w-4 h-4 text-amber-600" />
            }
            <span className={`text-sm font-medium ${qaReport.approved ? 'text-emerald-700' : 'text-amber-700'}`}>
              QA Score: {qaReport.score || 0}/100
            </span>
          </div>
          <p className={`text-xs ${qaReport.approved ? 'text-emerald-600' : 'text-amber-600'}`}>
            {qaReport.approved ? 'Content approved' : 'Content passed with notes'}
          </p>
        </div>

        {/* Template */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
          <p className="text-sm font-medium text-gray-700 mb-1">Details</p>
          <div className="text-xs text-gray-500 space-y-1">
            <p>Template: <span className="text-gray-700 capitalize">{assignment.output_template_id?.replace('_', ' ')}</span></p>
            <p>Format: <span className="text-gray-700">{assignment.output_format}</span></p>
            <p>Theme: <span className="text-gray-700 capitalize">{assignment.design_theme?.replace('_', ' ')}</span></p>
          </div>
        </div>
      </div>

      {/* Questions table */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-3">Questions</h2>
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-12">#</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Question</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-32">Answer</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-24">Difficulty</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-24">Standard</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {questions.map((q, i) => (
                <tr key={i} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-400">{q.question_number || i + 1}</td>
                  <td className="px-4 py-3 text-gray-800">{q.question_text?.slice(0, 120)}</td>
                  <td className="px-4 py-3 text-emerald-700 font-medium">{q.answer?.slice(0, 40)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      q.difficulty === 'easy' ? 'bg-emerald-50 text-emerald-700' :
                      q.difficulty === 'hard' ? 'bg-red-50 text-red-700' :
                      'bg-amber-50 text-amber-700'
                    }`}>
                      {q.difficulty}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-indigo-600">{q.standard_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
