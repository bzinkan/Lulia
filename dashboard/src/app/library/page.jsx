'use client';
import { useState, useEffect, useRef } from 'react';
import { Upload, BookOpen, FileText, Calendar, CheckCircle, Loader2, AlertCircle } from 'lucide-react';
import { apiFetch, apiUpload } from '@/lib/api';

const UPLOAD_TYPES = [
  {
    id: 'standards',
    label: 'Upload Standards',
    desc: 'Custom school standards (JSON)',
    icon: BookOpen,
    endpoint: '/api/v1/upload/standards',
    accept: '.json',
  },
  {
    id: 'curriculum',
    label: 'Upload Curriculum',
    desc: 'Pacing guide → Calendar + KB',
    icon: Calendar,
    endpoint: '/api/v1/upload/curriculum',
    accept: '.pdf,.docx,.txt',
  },
  {
    id: 'materials',
    label: 'Upload Materials',
    desc: 'Textbooks, worksheets → KB',
    icon: FileText,
    endpoint: '/api/v1/upload/materials',
    accept: '.pdf,.docx,.txt',
  },
];

export default function ContentLibrary() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRefs = useRef({});

  useEffect(() => {
    loadSources();
  }, []);

  async function loadSources() {
    try {
      const data = await apiFetch('/api/v1/knowledge/sources');
      // Only show teacher-uploaded content, not system OER (OpenStax, LibreTexts)
      const teacherSources = (data.sources || []).filter(
        s => !['oer_textbook', 'openstax'].includes(s.upload_lane)
      );
      setSources(teacherSources);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(type, file) {
    setUploading(type.id);
    setUploadResult(null);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    if (type.id === 'curriculum') {
      formData.append('class_id', '00000000-0000-0000-0000-000000000010');
      formData.append('subject', 'Math');
      formData.append('grade_level', '4');
      formData.append('teacher_id', '00000000-0000-0000-0000-000000000001');
    } else if (type.id === 'materials') {
      formData.append('teacher_id', '00000000-0000-0000-0000-000000000001');
      formData.append('subject', 'Math');
      formData.append('grade_level', '4');
    }

    try {
      const data = await apiUpload(type.endpoint, formData);
      setUploadResult(data);
      loadSources();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(null);
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Content Library</h1>
        <p className="text-sm text-gray-500 mt-1">Upload standards, curriculum guides, and teaching materials</p>
      </div>

      {/* Upload buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {UPLOAD_TYPES.map(type => {
          const Icon = type.icon;
          const isUploading = uploading === type.id;
          return (
            <div key={type.id}>
              <input
                type="file"
                ref={el => fileRefs.current[type.id] = el}
                accept={type.accept}
                className="hidden"
                onChange={e => {
                  if (e.target.files[0]) handleUpload(type, e.target.files[0]);
                  e.target.value = '';
                }}
              />
              <button
                onClick={() => fileRefs.current[type.id]?.click()}
                disabled={isUploading}
                className="w-full flex flex-col items-center gap-3 p-6 bg-white rounded-xl border-2 border-gray-200 hover:border-indigo-400 hover:bg-indigo-50/50 transition-all disabled:opacity-50"
              >
                {isUploading ? (
                  <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
                ) : (
                  <Icon className="w-8 h-8 text-indigo-600" />
                )}
                <span className="font-medium text-gray-800">{type.label}</span>
                <span className="text-xs text-gray-400">{type.desc}</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Upload result */}
      {uploadResult && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-6">
          <div className="flex items-center gap-2 text-emerald-700">
            <CheckCircle className="w-5 h-5" />
            <span className="font-medium">Upload successful</span>
          </div>
          <p className="text-sm text-emerald-600 mt-1">
            {uploadResult.chunk_count ? `${uploadResult.chunk_count} chunks created` : ''}
            {uploadResult.calendar_entries ? `, ${uploadResult.calendar_entries} calendar entries` : ''}
            {uploadResult.standards_loaded ? `${uploadResult.standards_loaded} standards loaded` : ''}
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
          <div className="flex items-center gap-2 text-red-700">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Upload failed</span>
          </div>
          <p className="text-sm text-red-600 mt-1">{error}</p>
        </div>
      )}

      {/* Sources list */}
      <h2 className="text-xl font-semibold text-gray-900 mb-3">Uploaded Sources</h2>
      {loading ? (
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-200 rounded-xl"></div>
          ))}
        </div>
      ) : sources.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="text-center py-12">
            <Upload className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No sources uploaded</h3>
            <p className="text-sm text-gray-500">Upload curriculum guides or teaching materials to build your Knowledge Base</p>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Subject</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Chunks</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Uploaded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sources.map(s => (
                <tr key={s.source_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-gray-800 font-medium">{s.name}</td>
                  <td className="px-4 py-3 text-gray-600 uppercase text-xs">{s.file_type}</td>
                  <td className="px-4 py-3 text-gray-600">{s.subject || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{s.chunk_count}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      s.processing_status === 'complete'
                        ? 'bg-emerald-50 text-emerald-700'
                        : s.processing_status === 'failed'
                        ? 'bg-red-50 text-red-700'
                        : 'bg-amber-50 text-amber-700'
                    }`}>
                      {s.processing_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(s.uploaded_at).toLocaleDateString()}
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
