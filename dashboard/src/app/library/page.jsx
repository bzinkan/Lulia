'use client';
import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import { Loader2, CheckCircle, AlertTriangle, X, Upload } from 'lucide-react';
import { apiFetch, apiUpload } from '@/lib/api';

const UPLOAD_TYPES = [
  {
    id: 'standards',
    label: 'Upload Standards',
    desc: 'Custom school or diocese standards',
    icon: 'star.png',
    endpoint: '/api/v1/upload/standards',
    accept: '.json,.pdf,.docx,.txt',
    accent: 'var(--coral)',
  },
  {
    id: 'curriculum',
    label: 'Upload Curriculum',
    desc: 'Pacing guides, scope & sequence',
    icon: 'calendar.png',
    endpoint: '/api/v1/upload/curriculum',
    accept: '.pdf,.docx,.txt',
    accent: 'var(--sage)',
  },
  {
    id: 'materials',
    label: 'Upload Materials',
    desc: 'Worksheets, textbooks, lesson plans',
    icon: 'document.png',
    endpoint: '/api/v1/upload/materials',
    accept: '.pdf,.docx,.txt',
    accent: 'var(--mustard)',
  },
];

const STATUS_STYLES = {
  complete: { bg: 'var(--green-bg, #DCFCE7)', color: 'var(--green-text, #16A34A)' },
  failed:   { bg: 'var(--red-bg, #FEF2F2)', color: '#EF4444' },
  pending:  { bg: 'var(--amber-bg, #FEF3C7)', color: 'var(--amber, #D97706)' },
};

export default function ContentLibrary() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(null);        // which type is uploading
  const [validating, setValidating] = useState(null);      // which type is validating
  const [validationResult, setValidationResult] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);     // file awaiting validation confirm
  const [pendingType, setPendingType] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRefs = useRef({});

  useEffect(() => { loadSources(); }, []);

  async function loadSources() {
    try {
      const data = await apiFetch('/api/v1/knowledge/sources');
      // Only show sources the teacher explicitly uploaded through the UI
      // Exclude system-ingested content (openstax, oer_textbook, teacher_reference, teacher_archive, loc)
      const teacherUploaded = (data.sources || []).filter(
        s => ['materials', 'curriculum'].includes(s.upload_lane)
      );
      setSources(teacherUploaded);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleFileSelected(type, file) {
    // Step 1: Validate with Haiku before uploading
    setValidating(type.id);
    setValidationResult(null);
    setUploadResult(null);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('upload_type', type.id);

    try {
      const result = await apiUpload('/api/v1/upload/validate', formData);
      setValidationResult(result);

      if (result.proceed) {
        // Validation passed — proceed to upload
        setPendingFile(file);
        setPendingType(type);
      } else {
        // Validation failed — show warning, let user decide
        setPendingFile(file);
        setPendingType(type);
      }
    } catch (e) {
      // Validation endpoint failed — allow upload anyway
      setPendingFile(file);
      setPendingType(type);
      setValidationResult({
        valid: true,
        confidence: 0.5,
        detected_type: type.id,
        message: 'Validation check unavailable — you can proceed with upload.',
        proceed: true,
      });
    } finally {
      setValidating(null);
    }
  }

  async function proceedWithUpload() {
    if (!pendingFile || !pendingType) return;
    const type = pendingType;
    const file = pendingFile;

    setUploading(type.id);
    setValidationResult(null);
    setPendingFile(null);
    setPendingType(null);

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

  function cancelUpload() {
    setPendingFile(null);
    setPendingType(null);
    setValidationResult(null);
  }

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-serif text-[26px]" style={{ color: 'var(--text-dark)' }}>
          Content Library
        </h1>
        <p className="text-[14px] mt-1" style={{ color: 'var(--text-mid)' }}>
          Upload standards, curriculum guides, and teaching materials
        </p>
      </div>

      {/* Upload cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {UPLOAD_TYPES.map(type => {
          const isUploading = uploading === type.id;
          const isValidating = validating === type.id;
          const isBusy = isUploading || isValidating;
          return (
            <div key={type.id}>
              <input
                type="file"
                ref={el => fileRefs.current[type.id] = el}
                accept={type.accept}
                className="hidden"
                onChange={e => {
                  if (e.target.files[0]) handleFileSelected(type, e.target.files[0]);
                  e.target.value = '';
                }}
              />
              <button
                onClick={() => fileRefs.current[type.id]?.click()}
                disabled={isBusy}
                className="hover-lift w-full flex flex-col items-center gap-3 p-6 rounded-card transition-all disabled:opacity-50"
                style={{
                  background: 'var(--warm-card)',
                  border: '2px dashed var(--border)',
                }}
              >
                {isBusy ? (
                  <div className="w-12 h-12 flex items-center justify-center">
                    <Loader2
                      className="w-8 h-8 animate-spin"
                      style={{ color: type.accent }}
                    />
                  </div>
                ) : (
                  <Image
                    src={`/icons/${type.icon}`}
                    alt=""
                    width={48}
                    height={48}
                    style={{ opacity: 0.85 }}
                  />
                )}
                <span className="font-bold text-[14px]" style={{ color: 'var(--text-dark)' }}>
                  {type.label}
                </span>
                <span className="text-[12px]" style={{ color: 'var(--text-light)' }}>
                  {isValidating ? 'Checking document...' : isUploading ? 'Processing...' : type.desc}
                </span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Validation result modal */}
      {validationResult && pendingFile && (
        <div
          className="rounded-card p-5 mb-6"
          style={{
            background: validationResult.valid ? 'var(--green-bg, #DCFCE7)' : '#FEF3C7',
            border: `1px solid ${validationResult.valid ? 'var(--green-text, #16A34A)' : 'var(--amber, #D97706)'}`,
          }}
        >
          <div className="flex items-start gap-3">
            {validationResult.valid ? (
              <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--green-text, #16A34A)' }} />
            ) : (
              <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--amber, #D97706)' }} />
            )}
            <div className="flex-1">
              <div className="font-bold text-[14px]" style={{ color: 'var(--text-dark)' }}>
                {validationResult.valid ? 'Document verified' : 'Document mismatch'}
              </div>
              <p className="text-[13px] mt-1" style={{ color: 'var(--text-mid)' }}>
                {validationResult.message}
              </p>
              {!validationResult.valid && validationResult.detected_type && (
                <p className="text-[12px] mt-1" style={{ color: 'var(--text-light)' }}>
                  This looks more like: <strong>{validationResult.detected_type}</strong>
                  {validationResult.confidence && ` (${Math.round(validationResult.confidence * 100)}% confidence)`}
                </p>
              )}
              {validationResult.format_info && (
                <p className="text-[11px] mt-1" style={{ color: 'var(--text-light)' }}>
                  {validationResult.format_info}
                </p>
              )}
              <div className="flex gap-3 mt-3">
                {!validationResult.hard_reject && (
                  <button
                    onClick={proceedWithUpload}
                    className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white"
                    style={{ background: validationResult.valid ? 'var(--sage)' : 'var(--amber, #D97706)' }}
                  >
                    {validationResult.valid ? 'Upload now' : 'Upload anyway'}
                  </button>
                )}
                <button
                  onClick={cancelUpload}
                  className="px-4 py-2 rounded-xl text-[13px] font-semibold"
                  style={{ color: 'var(--text-mid)', background: 'var(--warm-card)', border: '1px solid var(--border)' }}
                >
                  {validationResult.hard_reject ? 'Choose a different file' : 'Cancel'}
                </button>
              </div>
            </div>
            <button onClick={cancelUpload} style={{ color: 'var(--text-light)' }}>
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Upload success */}
      {uploadResult && (
        <div
          className="rounded-card p-4 mb-6"
          style={{ background: 'var(--green-bg, #DCFCE7)', border: '1px solid var(--green-text, #16A34A)' }}
        >
          <div className="flex items-center gap-2" style={{ color: 'var(--green-text, #16A34A)' }}>
            <CheckCircle className="w-5 h-5" />
            <span className="font-bold text-[14px]">Upload successful</span>
          </div>
          <p className="text-[13px] mt-1" style={{ color: 'var(--green-text, #16A34A)' }}>
            {uploadResult.standards_loaded ? `${uploadResult.standards_loaded} standards loaded` : ''}
            {uploadResult.standards_loaded && uploadResult.extraction_method === 'haiku_extraction' ? ' (auto-extracted from document)' : ''}
            {uploadResult.standards_loaded && uploadResult.name ? ` — ${uploadResult.name}` : ''}
            {uploadResult.chunk_count ? `${uploadResult.chunk_count} chunks created` : ''}
            {uploadResult.calendar_entries ? `, ${uploadResult.calendar_entries} calendar entries` : ''}
          </p>
        </div>
      )}

      {/* Upload error */}
      {error && (
        <div
          className="rounded-card p-4 mb-6"
          style={{ background: 'var(--red-bg, #FEF2F2)', border: '1px solid #EF4444' }}
        >
          <div className="flex items-center gap-2" style={{ color: '#EF4444' }}>
            <AlertTriangle className="w-5 h-5" />
            <span className="font-bold text-[14px]">Upload failed</span>
          </div>
          <p className="text-[13px] mt-1" style={{ color: '#EF4444' }}>{error}</p>
        </div>
      )}

      {/* Sources list */}
      <h2 className="font-serif text-[20px] mb-3" style={{ color: 'var(--text-dark)' }}>
        Uploaded Sources
      </h2>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div
              key={i}
              className="h-16 rounded-card animate-pulse"
              style={{ background: 'var(--border)' }}
            />
          ))}
        </div>
      ) : sources.length === 0 ? (
        <div
          className="rounded-card text-center py-12"
          style={{
            background: 'var(--warm-card)',
            border: '1px solid var(--border)',
          }}
        >
          <Image
            src="/icons/book.png"
            alt=""
            width={48}
            height={48}
            className="mx-auto mb-4"
            style={{ opacity: 0.5 }}
          />
          <h3 className="font-serif text-[18px] mb-1" style={{ color: 'var(--text-dark)' }}>
            No sources uploaded yet
          </h3>
          <p className="text-[13px]" style={{ color: 'var(--text-light)' }}>
            Upload curriculum guides or teaching materials to build your Knowledge Base
          </p>
        </div>
      ) : (
        <div
          className="rounded-card overflow-hidden"
          style={{
            background: 'var(--warm-card)',
            border: '1px solid var(--border)',
          }}
        >
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Name', 'Type', 'Subject', 'Status', 'Uploaded'].map(h => (
                  <th
                    key={h}
                    className="text-left px-4 py-3 font-semibold text-[11px] uppercase tracking-wider"
                    style={{ color: 'var(--text-light)' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sources.map(s => {
                const statusStyle = STATUS_STYLES[s.processing_status] || STATUS_STYLES.pending;
                return (
                  <tr
                    key={s.source_id}
                    className="transition-colors"
                    style={{ borderBottom: '1px solid var(--border)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--cream)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td className="px-4 py-3 font-semibold" style={{ color: 'var(--text-dark)' }}>
                      {s.name}
                    </td>
                    <td className="px-4 py-3 uppercase text-[11px]" style={{ color: 'var(--text-mid)' }}>
                      {s.file_type}
                    </td>
                    <td className="px-4 py-3" style={{ color: 'var(--text-mid)' }}>
                      {s.subject || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold"
                        style={{ background: statusStyle.bg, color: statusStyle.color }}
                      >
                        {s.processing_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[11px]" style={{ color: 'var(--text-light)' }}>
                      {new Date(s.uploaded_at).toLocaleDateString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
