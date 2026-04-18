'use client';
import { useState, useRef } from 'react';
import { X, Upload, Loader2, CheckCircle, AlertTriangle, Video } from 'lucide-react';
import { apiFetch } from '@/lib/api';

/**
 * Teacher video upload modal.
 *
 * Flow:
 *   1. Teacher picks an MP4/MOV/WEBM file.
 *   2. POST /videos/upload/presign → get a presigned S3 PUT URL + video_id.
 *   3. PUT the file directly to S3 from the browser (progress bar).
 *   4. POST /videos/upload/complete → fire Inngest post-processing workflow.
 *   5. Show success; teacher can close and come back when auto-classification finishes.
 */
export default function VideoUploadModal({ teacherId, classId, onUploaded, onClose }) {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState('idle'); // idle | presigning | uploading | completing | done | error
  const [error, setError] = useState(null);
  const [videoId, setVideoId] = useState(null);
  const xhrRef = useRef(null);

  const ACCEPTED = {
    'video/mp4': '.mp4',
    'video/quicktime': '.mov',
    'video/webm': '.webm',
    'video/x-matroska': '.mkv',
  };
  const MAX_SIZE = 2 * 1024 * 1024 * 1024; // 2 GB

  function pickFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!Object.keys(ACCEPTED).includes(f.type)) {
      setError(`Unsupported file type: ${f.type}. Use MP4, MOV, WEBM, or MKV.`);
      return;
    }
    if (f.size > MAX_SIZE) {
      setError(`File too large: ${(f.size / 1e9).toFixed(2)} GB. Max 2 GB.`);
      return;
    }
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^/.]+$/, ''));
    setError(null);
  }

  async function startUpload() {
    if (!file) return;
    setPhase('presigning');
    setError(null);
    setProgress(0);

    try {
      const presign = await apiFetch('/api/v1/videos/upload/presign', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          content_type: file.type,
          teacher_id: teacherId,
          class_id: classId || null,
          title: title || file.name,
        }),
      });
      if (!presign.upload_url) throw new Error('Failed to get upload URL');
      setVideoId(presign.video_id);

      setPhase('uploading');
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhrRef.current = xhr;
        xhr.open('PUT', presign.upload_url);
        xhr.setRequestHeader('Content-Type', file.type);
        xhr.upload.addEventListener('progress', (ev) => {
          if (ev.lengthComputable) {
            setProgress(Math.round((ev.loaded / ev.total) * 100));
          }
        });
        xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`S3 PUT ${xhr.status}`)));
        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.send(file);
      });

      setPhase('completing');
      await apiFetch('/api/v1/videos/upload/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: presign.video_id }),
      });

      setPhase('done');
      onUploaded?.(presign.video_id);
    } catch (e) {
      setError(e.message || 'Upload failed');
      setPhase('error');
    }
  }

  function cancel() {
    if (xhrRef.current && phase === 'uploading') {
      try { xhrRef.current.abort(); } catch (_) {}
    }
    onClose?.();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(60,40,20,0.55)', backdropFilter: 'blur(4px)' }}>
      <div className="rounded-card w-full max-w-lg p-6"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)', boxShadow: '0 12px 40px rgba(60,40,20,0.25)' }}>

        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <Video className="w-5 h-5" style={{ color: 'var(--coral)' }} />
            <h2 className="font-serif text-[22px]" style={{ color: 'var(--text-dark)' }}>
              Upload Video
            </h2>
          </div>
          <button onClick={cancel}
            className="p-1 rounded-full hover:opacity-70"
            style={{ color: 'var(--text-mid)', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {phase === 'idle' && (
          <>
            <label htmlFor="video-file-input"
              className="block rounded-card p-8 text-center mb-4 cursor-pointer hover:opacity-90"
              style={{ background: 'var(--cream)', border: '2px dashed var(--border)' }}>
              <Upload className="w-10 h-10 mx-auto mb-2" style={{ color: 'var(--coral)' }} />
              <div className="font-bold text-[15px]" style={{ color: 'var(--text-dark)' }}>
                {file ? file.name : 'Click to select a video'}
              </div>
              <div className="text-[13px] mt-1" style={{ color: 'var(--text-mid)' }}>
                {file ? `${(file.size / 1e6).toFixed(1)} MB` : 'MP4, MOV, WEBM, MKV · Up to 2 GB'}
              </div>
              <input id="video-file-input"
                type="file"
                accept={Object.values(ACCEPTED).join(',')}
                onChange={pickFile}
                className="hidden" />
            </label>

            <label className="block text-[13px] font-bold mb-1" style={{ color: 'var(--text-dark)' }}>
              Title
            </label>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="Water cycle demonstration"
              className="w-full rounded-xl px-3 py-2 text-[14px] mb-4"
              style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-dark)' }} />

            {error && (
              <div className="rounded-xl p-3 mb-4 flex items-start gap-2"
                style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444' }}>
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: '#B91C1C' }} />
                <div className="text-[13px]" style={{ color: '#B91C1C' }}>{error}</div>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button onClick={cancel}
                className="px-4 py-2 rounded-xl text-[14px]"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                Cancel
              </button>
              <button onClick={startUpload} disabled={!file}
                className="px-4 py-2 rounded-xl text-[14px] font-bold"
                style={{
                  background: file ? 'var(--coral)' : 'var(--cream)',
                  color: file ? 'white' : 'var(--text-mid)',
                  border: 'none',
                  cursor: file ? 'pointer' : 'not-allowed',
                  opacity: file ? 1 : 0.6,
                }}>
                Upload
              </button>
            </div>
          </>
        )}

        {(phase === 'presigning' || phase === 'uploading' || phase === 'completing') && (
          <div className="text-center py-8">
            <Loader2 className="w-10 h-10 mx-auto mb-3 animate-spin" style={{ color: 'var(--coral)' }} />
            <div className="font-bold text-[15px] mb-2" style={{ color: 'var(--text-dark)' }}>
              {phase === 'presigning' && 'Preparing upload…'}
              {phase === 'uploading' && `Uploading ${progress}%`}
              {phase === 'completing' && 'Finalizing…'}
            </div>
            {phase === 'uploading' && (
              <div className="w-full rounded-full h-2" style={{ background: 'var(--cream)' }}>
                <div className="h-2 rounded-full transition-all"
                  style={{ width: `${progress}%`, background: 'var(--coral)' }} />
              </div>
            )}
          </div>
        )}

        {phase === 'done' && (
          <div className="text-center py-8">
            <CheckCircle className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--sage)' }} />
            <div className="font-bold font-serif text-[18px] mb-2" style={{ color: 'var(--text-dark)' }}>
              Upload complete!
            </div>
            <div className="text-[13px] mb-5" style={{ color: 'var(--text-mid)' }}>
              We're extracting a transcript and auto-classifying your video. It'll appear in your library in a few minutes.
            </div>
            <button onClick={onClose}
              className="px-5 py-2 rounded-xl text-[14px] font-bold"
              style={{ background: 'var(--coral)', color: 'white', border: 'none', cursor: 'pointer' }}>
              Done
            </button>
          </div>
        )}

        {phase === 'error' && (
          <div className="text-center py-8">
            <AlertTriangle className="w-10 h-10 mx-auto mb-3" style={{ color: '#EF4444' }} />
            <div className="font-bold text-[15px] mb-2" style={{ color: '#B91C1C' }}>
              Upload failed
            </div>
            <div className="text-[13px] mb-4" style={{ color: 'var(--text-mid)' }}>{error}</div>
            <button onClick={() => { setPhase('idle'); setError(null); setProgress(0); }}
              className="px-5 py-2 rounded-xl text-[14px] font-bold"
              style={{ background: 'var(--coral)', color: 'white', border: 'none', cursor: 'pointer' }}>
              Try Again
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
