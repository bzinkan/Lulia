'use client';
import { useState, useRef } from 'react';
import { Upload, Camera, CheckCircle, Loader2, AlertTriangle } from 'lucide-react';
import { apiUpload } from '@/lib/api';

export default function ScanPage() {
  const [assignmentId, setAssignmentId] = useState('');
  const [studentName, setStudentName] = useState('');
  const [results, setResults] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  async function handleUpload(files) {
    if (!assignmentId) { alert('Enter an assignment ID first'); return; }
    setUploading(true);

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('assignment_id', assignmentId);
      if (studentName) formData.append('student_name', studentName);

      try {
        const result = await apiUpload('/api/v1/submissions/upload', formData);
        setResults(prev => [...prev, { file: file.name, ...result }]);
      } catch (e) {
        setResults(prev => [...prev, { file: file.name, error: e.message }]);
      }
    }
    setUploading(false);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900" style={{ fontFamily: "'DM Serif Display', serif" }}>Scan & Grade</h1>
        <p className="text-sm text-gray-500 mt-1">Upload photos of student work for automatic grading</p>
      </div>

      {/* Config */}
      <div className="bg-white rounded-[14px] p-6 mb-6" style={{ border: '1px solid #E7E5E4' }}>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Assignment ID</label>
            <input value={assignmentId} onChange={e => setAssignmentId(e.target.value)} placeholder="Paste assignment UUID" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Student Name (optional)</label>
            <input value={studentName} onChange={e => setStudentName(e.target.value)} placeholder="Will be detected from scan" className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300" />
          </div>
        </div>

        {/* Upload zone */}
        <input type="file" ref={fileRef} accept="image/*,.pdf" multiple className="hidden" onChange={e => e.target.files.length && handleUpload(Array.from(e.target.files))} />
        <div
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-orange-300 rounded-2xl p-8 text-center hover:border-orange-500 hover:bg-orange-50/50 transition-colors cursor-pointer"
        >
          {uploading ? (
            <div className="flex flex-col items-center">
              <Loader2 className="w-8 h-8 text-orange-500 animate-spin mb-3" />
              <p className="text-sm font-medium text-gray-700">Processing...</p>
            </div>
          ) : (
            <>
              <Camera className="w-8 h-8 text-orange-400 mx-auto mb-3" />
              <p className="text-sm font-medium text-gray-700">Drop photos here or click to browse</p>
              <p className="text-xs text-gray-400 mt-1">JPEG, PNG, or PDF — supports bulk upload</p>
            </>
          )}
        </div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold" style={{ fontFamily: "'DM Serif Display', serif" }}>Results</h2>
          {results.map((r, i) => (
            <div key={i} className="bg-white rounded-[14px] p-4" style={{ border: '1px solid #E7E5E4' }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-800">{r.student_name || r.file}</span>
                {r.error ? (
                  <span className="text-xs text-red-600 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Error</span>
                ) : (
                  <span className={`text-xs font-medium ${r.status === 'needs_review' ? 'text-amber-600' : 'text-green-600'}`}>
                    {r.percentage}% ({r.total_earned}/{r.total_possible})
                  </span>
                )}
              </div>
              {r.error && <p className="text-xs text-red-500">{r.error}</p>}
              {r.grades && (
                <div className="grid grid-cols-5 gap-1 mt-2">
                  {r.grades.map(g => (
                    <div key={g.question_number} className={`text-center py-1 rounded text-xs font-medium ${
                      g.needs_review ? 'bg-amber-50 text-amber-700' :
                      g.points_earned >= g.points_possible ? 'bg-green-50 text-green-700' :
                      'bg-red-50 text-red-700'
                    }`}>
                      Q{g.question_number}: {g.points_earned}/{g.points_possible}
                    </div>
                  ))}
                </div>
              )}
              {r.flagged_questions?.length > 0 && (
                <p className="text-xs text-amber-600 mt-2">
                  <AlertTriangle className="w-3 h-3 inline mr-1" />
                  Questions {r.flagged_questions.join(', ')} need teacher review
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
