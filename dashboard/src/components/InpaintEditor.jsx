'use client';
/**
 * InpaintEditor — Leonardo-powered image editing in-app.
 *
 * Teacher brushes over a region they want to change, types a prompt describing
 * the replacement, and the backend (/api/v1/images/inpaint) calls Leonardo's
 * canvas inpaint API. Result is displayed with Accept / Retry / Cancel.
 *
 * Usage:
 *   <InpaintEditor
 *     imageUrl="https://..."           // source image (must be CORS-enabled)
 *     teacherId="..."                   // for library persistence
 *     onComplete={(newUrl) => ...}      // called with the edited image URL
 *     onClose={() => ...}               // teacher cancels
 *   />
 *
 * The image is loaded with crossOrigin="anonymous" so the canvas stays untainted
 * and we can export the mask. If loading fails we fall back to fetching via the
 * API as a proxy.
 */
import { useEffect, useRef, useState } from 'react';
import { X, Brush, Eraser, Undo2, Trash2, Sparkles, Loader2, Check, RefreshCw } from 'lucide-react';
import { apiUpload } from '@/lib/api';

const MAX_CANVAS_SIZE = 768;

export default function InpaintEditor({ imageUrl, teacherId, onComplete, onClose }) {
  const imageCanvasRef = useRef(null);
  const maskCanvasRef = useRef(null);
  const containerRef = useRef(null);

  const [tool, setTool] = useState('brush');       // 'brush' | 'eraser'
  const [brushSize, setBrushSize] = useState(40);
  const [prompt, setPrompt] = useState('');
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  const [strokeHistory, setStrokeHistory] = useState([]); // snapshots for undo

  // Load the image onto the background canvas
  useEffect(() => {
    if (!imageUrl) return;
    setLoading(true);
    setLoadError(null);

    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const scale = Math.min(MAX_CANVAS_SIZE / img.naturalWidth, MAX_CANVAS_SIZE / img.naturalHeight, 1);
      const w = Math.round(img.naturalWidth * scale);
      const h = Math.round(img.naturalHeight * scale);
      setImgSize({ w, h });

      // Defer to next tick so refs are mounted
      requestAnimationFrame(() => {
        const imgCanvas = imageCanvasRef.current;
        const maskCanvas = maskCanvasRef.current;
        if (!imgCanvas || !maskCanvas) return;
        imgCanvas.width = w;
        imgCanvas.height = h;
        maskCanvas.width = w;
        maskCanvas.height = h;

        const ictx = imgCanvas.getContext('2d');
        ictx.drawImage(img, 0, 0, w, h);

        const mctx = maskCanvas.getContext('2d');
        mctx.clearRect(0, 0, w, h);

        setLoading(false);
      });
    };
    img.onerror = () => {
      setLoadError('Could not load image (CORS or network error). Try again or use a different image.');
      setLoading(false);
    };
    img.src = imageUrl;
  }, [imageUrl]);

  // Drawing handlers
  const drawing = useRef(false);
  const lastPoint = useRef(null);

  function canvasCoordsFromEvent(e) {
    const canvas = maskCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      x: (clientX - rect.left) * scaleX,
      y: (clientY - rect.top) * scaleY,
    };
  }

  function startStroke(e) {
    if (loading || resultUrl) return;
    e.preventDefault();
    const ctx = maskCanvasRef.current.getContext('2d');
    setStrokeHistory(prev => [...prev.slice(-19), ctx.getImageData(0, 0, imgSize.w, imgSize.h)]);
    drawing.current = true;
    lastPoint.current = canvasCoordsFromEvent(e);
    paintTo(lastPoint.current);
  }

  function continueStroke(e) {
    if (!drawing.current) return;
    e.preventDefault();
    const pt = canvasCoordsFromEvent(e);
    paintTo(pt);
    lastPoint.current = pt;
  }

  function endStroke() {
    drawing.current = false;
    lastPoint.current = null;
  }

  function paintTo(pt) {
    const ctx = maskCanvasRef.current.getContext('2d');
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineWidth = brushSize;
    if (tool === 'brush') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = 'rgba(216, 108, 82, 0.55)'; // coral overlay for visibility
      ctx.fillStyle = 'rgba(216, 108, 82, 0.55)';
    } else {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.strokeStyle = 'rgba(0,0,0,1)';
      ctx.fillStyle = 'rgba(0,0,0,1)';
    }
    if (lastPoint.current) {
      ctx.beginPath();
      ctx.moveTo(lastPoint.current.x, lastPoint.current.y);
      ctx.lineTo(pt.x, pt.y);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, brushSize / 2, 0, Math.PI * 2);
    ctx.fill();
  }

  function undo() {
    setStrokeHistory(prev => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      const ctx = maskCanvasRef.current.getContext('2d');
      ctx.putImageData(last, 0, 0);
      return prev.slice(0, -1);
    });
  }

  function clearMask() {
    const ctx = maskCanvasRef.current.getContext('2d');
    ctx.clearRect(0, 0, imgSize.w, imgSize.h);
    setStrokeHistory([]);
  }

  // Convert the mask canvas (coral translucent) into a pure black/white PNG
  // suitable for Leonardo's inpaint API (white = edit this region, black = keep).
  async function exportMaskBlob() {
    const src = maskCanvasRef.current;
    const out = document.createElement('canvas');
    out.width = src.width;
    out.height = src.height;
    const octx = out.getContext('2d');
    octx.fillStyle = '#000';
    octx.fillRect(0, 0, out.width, out.height);

    const srcData = src.getContext('2d').getImageData(0, 0, src.width, src.height);
    const outData = octx.getImageData(0, 0, out.width, out.height);
    for (let i = 0; i < srcData.data.length; i += 4) {
      if (srcData.data[i + 3] > 20) {
        outData.data[i]     = 255;
        outData.data[i + 1] = 255;
        outData.data[i + 2] = 255;
        outData.data[i + 3] = 255;
      }
    }
    octx.putImageData(outData, 0, 0);
    return new Promise(resolve => out.toBlob(resolve, 'image/png'));
  }

  async function exportImageBlob() {
    const src = imageCanvasRef.current;
    return new Promise(resolve => src.toBlob(resolve, 'image/png'));
  }

  async function submit() {
    if (!prompt.trim() || prompt.trim().length < 3) {
      setSubmitError('Describe what to put in the masked area (at least 3 characters).');
      return;
    }
    if (strokeHistory.length === 0) {
      setSubmitError('Brush over the area you want to change first.');
      return;
    }
    setSubmitError(null);
    setSubmitting(true);
    try {
      const [imageBlob, maskBlob] = await Promise.all([exportImageBlob(), exportMaskBlob()]);
      if (!imageBlob || !maskBlob) throw new Error('Could not export image/mask');
      const fd = new FormData();
      fd.append('image', imageBlob, 'source.png');
      fd.append('mask', maskBlob, 'mask.png');
      fd.append('prompt', prompt.trim());
      fd.append('teacher_id', teacherId || '00000000-0000-0000-0000-000000000001');
      fd.append('save_to_library', 'true');

      const data = await apiUpload('/api/v1/images/inpaint', fd);
      if (data?.storage_url || data?.leonardo_url) {
        setResultUrl(data.storage_url || data.leonardo_url);
      } else {
        setSubmitError(data?.error || 'Inpaint failed with no details.');
      }
    } catch (e) {
      setSubmitError(e?.message || 'Inpaint request failed.');
    } finally {
      setSubmitting(false);
    }
  }

  function tryAgain() {
    setResultUrl(null);
    setSubmitError(null);
    clearMask();
  }

  function accept() {
    if (resultUrl) onComplete?.(resultUrl);
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      style={{ background: 'rgba(30, 20, 10, 0.65)', backdropFilter: 'blur(4px)' }}
    >
      <div
        ref={containerRef}
        className="rounded-[20px] max-w-[900px] w-full max-h-[90vh] overflow-auto"
        style={{ background: 'var(--warm-card, #FEF9F2)', border: '1px solid var(--border, #E7E5E4)' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 sticky top-0 z-10"
          style={{ background: 'var(--warm-card, #FEF9F2)', borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5" style={{ color: 'var(--coral, #D86C52)' }} />
            <h2 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
              Edit image
            </h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-black/5"
            style={{ color: 'var(--text-mid)' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 grid gap-4">
          {/* Canvas stage */}
          <div className="flex items-center justify-center p-3 rounded-xl"
            style={{ background: 'var(--cream, #F5EDE0)', border: '1px solid var(--border)', minHeight: 320 }}>
            {loading && (
              <div className="flex items-center gap-2 text-[13px]" style={{ color: 'var(--text-mid)' }}>
                <Loader2 className="w-4 h-4 animate-spin" /> Loading image…
              </div>
            )}
            {loadError && (
              <div className="text-[13px] text-center" style={{ color: '#B91C1C' }}>
                {loadError}
              </div>
            )}
            {!loading && !loadError && !resultUrl && (
              <div
                className="relative"
                style={{
                  width: imgSize.w,
                  height: imgSize.h,
                  maxWidth: '100%',
                  cursor: tool === 'eraser' ? 'crosshair' : 'crosshair',
                  touchAction: 'none',
                }}
              >
                <canvas ref={imageCanvasRef} className="absolute inset-0 rounded-lg"
                  style={{ width: '100%', height: '100%' }} />
                <canvas ref={maskCanvasRef} className="absolute inset-0 rounded-lg"
                  style={{ width: '100%', height: '100%' }}
                  onMouseDown={startStroke} onMouseMove={continueStroke}
                  onMouseUp={endStroke} onMouseLeave={endStroke}
                  onTouchStart={startStroke} onTouchMove={continueStroke} onTouchEnd={endStroke}
                />
              </div>
            )}
            {resultUrl && (
              <img src={resultUrl} alt="Inpaint result"
                className="max-w-full max-h-[520px] rounded-lg"
                style={{ border: '1px solid var(--border)' }} />
            )}
          </div>

          {/* Tool row */}
          {!loading && !loadError && !resultUrl && (
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => setTool('brush')}
                className="px-3 py-1.5 rounded-lg text-[12px] font-bold flex items-center gap-1.5"
                style={{
                  background: tool === 'brush' ? 'var(--coral)' : 'transparent',
                  color: tool === 'brush' ? 'white' : 'var(--text-mid)',
                  border: '1px solid ' + (tool === 'brush' ? 'var(--coral)' : 'var(--border)'),
                }}>
                <Brush className="w-3.5 h-3.5" /> Brush
              </button>
              <button onClick={() => setTool('eraser')}
                className="px-3 py-1.5 rounded-lg text-[12px] font-bold flex items-center gap-1.5"
                style={{
                  background: tool === 'eraser' ? 'var(--sage, #6BA08A)' : 'transparent',
                  color: tool === 'eraser' ? 'white' : 'var(--text-mid)',
                  border: '1px solid ' + (tool === 'eraser' ? 'var(--sage)' : 'var(--border)'),
                }}>
                <Eraser className="w-3.5 h-3.5" /> Eraser
              </button>
              <div className="flex items-center gap-2 ml-2">
                <span className="text-[11px]" style={{ color: 'var(--text-light)' }}>Size</span>
                <input type="range" min="8" max="120" value={brushSize}
                  onChange={e => setBrushSize(parseInt(e.target.value, 10))}
                  style={{ accentColor: 'var(--coral)' }} />
                <span className="text-[11px] font-mono w-8" style={{ color: 'var(--text-mid)' }}>{brushSize}</span>
              </div>
              <div className="ml-auto flex items-center gap-2">
                <button onClick={undo} disabled={strokeHistory.length === 0}
                  className="px-3 py-1.5 rounded-lg text-[12px] font-bold flex items-center gap-1.5 disabled:opacity-40"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-mid)' }}>
                  <Undo2 className="w-3.5 h-3.5" /> Undo
                </button>
                <button onClick={clearMask}
                  className="px-3 py-1.5 rounded-lg text-[12px] font-bold flex items-center gap-1.5"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-mid)' }}>
                  <Trash2 className="w-3.5 h-3.5" /> Clear
                </button>
              </div>
            </div>
          )}

          {/* Prompt + submit */}
          {!resultUrl && (
            <>
              <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
                placeholder="Describe what to put in the painted area (e.g. 'a red apple', 'remove this object', 'a friendly cartoon fox')"
                rows={2}
                className="w-full px-3 py-2 rounded-xl text-[13px]"
                style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }} />
              {submitError && (
                <div className="text-[12px]" style={{ color: '#B91C1C' }}>{submitError}</div>
              )}
              <div className="flex items-center justify-end gap-2">
                <button onClick={onClose}
                  className="px-4 py-2 rounded-xl text-[13px] font-bold"
                  style={{ border: '1px solid var(--border)', color: 'var(--text-mid)' }}>
                  Cancel
                </button>
                <button onClick={submit} disabled={submitting || loading || !!loadError}
                  className="px-4 py-2 rounded-xl text-[13px] font-bold text-white flex items-center gap-2 disabled:opacity-50"
                  style={{ background: 'var(--coral)', boxShadow: '0 4px 14px rgba(216,108,82,0.3)' }}>
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {submitting ? 'Generating…' : 'Apply edit'}
                </button>
              </div>
            </>
          )}

          {/* Result — accept or retry */}
          {resultUrl && (
            <div className="flex items-center justify-end gap-2">
              <button onClick={tryAgain}
                className="px-4 py-2 rounded-xl text-[13px] font-bold flex items-center gap-2"
                style={{ border: '1px solid var(--border)', color: 'var(--text-mid)' }}>
                <RefreshCw className="w-4 h-4" /> Try again
              </button>
              <button onClick={accept}
                className="px-4 py-2 rounded-xl text-[13px] font-bold text-white flex items-center gap-2"
                style={{ background: 'var(--sage, #6BA08A)' }}>
                <Check className="w-4 h-4" /> Use this image
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
