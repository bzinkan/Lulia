'use client';
import { useEffect, useState } from 'react';
import Image from 'next/image';
import { X, Play, Loader2, AlertTriangle, Film, Lock, Sparkles, CheckCircle, Wand2 } from 'lucide-react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api';
import InpaintEditor from './InpaintEditor';

const WARN_STYLES = {
  green:  { bg: 'rgba(107,160,138,0.08)', color: 'var(--sage)',   border: 'var(--sage)'  },
  yellow: { bg: 'rgba(245,158,11,0.08)',  color: '#B45309',        border: '#F59E0B'      },
  red:    { bg: 'rgba(239,68,68,0.08)',   color: '#B91C1C',        border: '#EF4444'      },
};

/**
 * Pre-generation modal for a Short Clip.
 *
 * Two steps:
 *   1. Preview thumbnails — 4 still images (6 free/mo on Plus+, then 1 credit each)
 *   2. Duration + cost confirmation — teacher picks duration, sees credit cost, generates
 *
 * Chosen preview image is passed to Veo as a style anchor (reference_image_uri).
 */
export default function ClipCostModal({
  prompt, initialDuration = 30, teacherId, classId, topicLabel,
  onGenerated, onClose,
}) {
  const [step, setStep] = useState('preview'); // 'preview' | 'configure'
  const [quota, setQuota] = useState(null);
  const [previews, setPreviews] = useState([]);
  const [previewMeta, setPreviewMeta] = useState(null); // { within_free_allowance, credits_charged, free_remaining }
  const [selectedImage, setSelectedImage] = useState(null);
  const [loadingPreviews, setLoadingPreviews] = useState(false);
  const [editingPreview, setEditingPreview] = useState(null); // URL of preview being inpainted

  const [duration, setDuration] = useState(initialDuration);
  const [cost, setCost] = useState(null);
  const [loadingCost, setLoadingCost] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [tierBlock, setTierBlock] = useState(null);

  // Load quota on open
  useEffect(() => {
    apiFetch(`/api/v1/clips/preview/quota?teacher_id=${teacherId}`)
      .then(setQuota)
      .catch(() => {});
  }, [teacherId]);

  // Fetch cost whenever duration changes in configure step
  useEffect(() => {
    if (step !== 'configure') return;
    let cancelled = false;
    async function load() {
      setLoadingCost(true);
      try {
        const data = await apiFetch(`/api/v1/clips/cost?duration_sec=${duration}&teacher_id=${teacherId}`);
        if (!cancelled) setCost(data);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoadingCost(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [duration, teacherId, step]);

  async function loadPreviews() {
    setLoadingPreviews(true); setError(null);
    try {
      const data = await apiFetch('/api/v1/clips/preview', {
        method: 'POST',
        body: JSON.stringify({ teacher_id: teacherId, prompt }),
      });
      setPreviews(data.images || []);
      setPreviewMeta(data);
      // Refresh quota counter
      apiFetch(`/api/v1/clips/preview/quota?teacher_id=${teacherId}`).then(setQuota).catch(() => {});
    } catch (e) {
      if (e.status === 402 && e.body?.tier_required) setTierBlock(e.body);
      else setError(e.message);
    } finally {
      setLoadingPreviews(false);
    }
  }

  async function handleGenerate() {
    if (!cost?.sufficient) return;
    if (cost.warning?.require_confirm && !acknowledged) return;
    setGenerating(true); setError(null);
    try {
      const clip = await apiFetch('/api/v1/clips/generate', {
        method: 'POST',
        body: JSON.stringify({
          teacher_id: teacherId,
          class_id: classId || null,
          prompt,
          duration_sec: duration,
          aspect_ratio: '16:9',
          topic_label: topicLabel || null,
          reference_image_uri: selectedImage || null,
        }),
      });
      onGenerated?.(clip);
      onClose();
    } catch (e) {
      if (e.status === 402 && e.body?.tier_required) setTierBlock(e.body);
      else setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  const warning = cost?.warning;
  const warnStyle = warning ? WARN_STYLES[warning.level] : WARN_STYLES.green;
  const requiresConfirm = warning?.require_confirm && !acknowledged;
  const insufficient = cost && !cost.sufficient;
  const affordableMaxSec = cost?.balance?.total
    ? Math.floor(cost.balance.total / (cost.rate_per_sec || 3))
    : 0;

  const previewCostLabel = quota
    ? (quota.free_remaining > 0
        ? `Free preview (${quota.free_remaining} of ${quota.free_total} free left this month)`
        : `1 credit per preview set (free allowance used up this month)`)
    : 'Preview';

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-lg mx-4 max-h-[92vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2">
            <Film className="w-5 h-5" style={{ color: 'var(--coral)' }} />
            <div>
              <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
                {step === 'preview' ? 'Pick a Look' : 'Generate Short Clip'}
              </h3>
              <p className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                {step === 'preview'
                  ? 'Preview 4 styles before spending credits on the full clip.'
                  : 'Set duration and confirm credit cost.'}
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-light)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tier lock */}
        {tierBlock && (
          <div className="p-5">
            <div className="p-4 rounded-xl flex flex-col items-center text-center"
              style={{ background: 'rgba(216,108,82,0.08)', border: '1px solid var(--coral)' }}>
              <Lock className="w-6 h-6 mb-2" style={{ color: 'var(--coral)' }} />
              <h4 className="font-bold text-[14px] mb-1" style={{ color: 'var(--text-dark)' }}>
                Short Clips require Plus
              </h4>
              <p className="text-[12px] mb-3" style={{ color: 'var(--text-mid)' }}>
                You're currently on {tierBlock.current_tier}. Upgrade to generate clips.
              </p>
              <Link href="/billing"
                className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white"
                style={{ background: 'var(--coral)' }}>
                Upgrade plan
              </Link>
            </div>
          </div>
        )}

        {/* STEP 1: Preview picker */}
        {!tierBlock && step === 'preview' && (
          <>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div className="p-3 rounded-xl text-[12px]"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-mid)' }}>
                <span className="font-bold" style={{ color: 'var(--text-dark)' }}>Prompt: </span>
                {prompt}
              </div>

              {previews.length === 0 ? (
                <div className="text-center py-8">
                  <Sparkles className="w-10 h-10 mx-auto mb-2" style={{ color: 'var(--coral)', opacity: 0.5 }} />
                  <p className="text-[13px] mb-1" style={{ color: 'var(--text-dark)' }}>
                    Generate 4 preview thumbnails
                  </p>
                  <p className="text-[11px] mb-4" style={{ color: 'var(--text-light)' }}>
                    {previewCostLabel}
                  </p>
                  <button onClick={loadPreviews} disabled={loadingPreviews}
                    className="px-5 py-2 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2 mx-auto disabled:opacity-50"
                    style={{ background: 'var(--coral)' }}>
                    {loadingPreviews
                      ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating previews…</>
                      : <><Sparkles className="w-4 h-4" /> Generate Previews</>}
                  </button>
                </div>
              ) : (
                <>
                  <p className="text-[12px] text-center" style={{ color: 'var(--text-mid)' }}>
                    Pick the style closest to what you want — the video will match.
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {previews.map((uri, i) => {
                      const selected = selectedImage === uri;
                      return (
                        <div key={i}
                          className="relative aspect-video rounded-lg overflow-hidden transition-all group"
                          style={{
                            border: `3px solid ${selected ? 'var(--coral)' : 'var(--border)'}`,
                            cursor: 'pointer',
                            background: '#1F1B17',
                          }}>
                          <button onClick={() => setSelectedImage(uri)} className="w-full h-full block"
                            style={{ cursor: 'pointer' }}>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={uri} alt={`Preview ${i + 1}`} className="w-full h-full object-cover" />
                          </button>
                          {selected && (
                            <div className="absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center pointer-events-none"
                              style={{ background: 'var(--coral)' }}>
                              <CheckCircle className="w-4 h-4 text-white" />
                            </div>
                          )}
                          <button onClick={(e) => { e.stopPropagation(); setEditingPreview(uri); }}
                            className="absolute bottom-1 right-1 px-2 py-1 rounded-md text-[10px] font-bold flex items-center gap-1 transition-opacity opacity-0 group-hover:opacity-100"
                            style={{ background: 'rgba(255,255,255,0.95)', color: 'var(--text-dark)' }}
                            title="Edit this image with AI inpainting">
                            <Wand2 className="w-3 h-3" /> Edit
                          </button>
                        </div>
                      );
                    })}
                  </div>
                  {previewMeta && (
                    <p className="text-[11px] text-center" style={{ color: 'var(--text-light)' }}>
                      {previewMeta.within_free_allowance
                        ? `Free preview · ${previewMeta.free_remaining} free previews remaining this month`
                        : `Charged ${previewMeta.credits_charged} credit for this preview set`}
                    </p>
                  )}
                  <button onClick={loadPreviews} disabled={loadingPreviews}
                    className="w-full py-2 rounded-xl text-[12px] font-semibold flex items-center justify-center gap-2"
                    style={{ color: 'var(--text-mid)', background: 'var(--cream)', border: '1px solid var(--border)' }}>
                    {loadingPreviews
                      ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating…</>
                      : <><Sparkles className="w-3.5 h-3.5" /> Try different previews</>}
                  </button>
                </>
              )}

              {error && (
                <div className="p-2.5 rounded-lg text-[12px]"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#EF4444' }}>
                  {error}
                </div>
              )}
            </div>

            <div className="p-5 flex justify-between items-center" style={{ borderTop: '1px solid var(--border)' }}>
              <button
                onClick={() => setStep('configure')}
                className="px-3 py-2 rounded-xl text-[12px] font-semibold"
                style={{ color: 'var(--text-light)', background: 'transparent', border: 'none', textDecoration: 'underline', cursor: 'pointer' }}>
                Skip previews →
              </button>
              <button onClick={() => setStep('configure')}
                disabled={!selectedImage}
                className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white disabled:opacity-50"
                style={{ background: 'var(--coral)' }}>
                Continue with this style
              </button>
            </div>
          </>
        )}

        {/* STEP 2: Configure + generate */}
        {!tierBlock && step === 'configure' && (
          <>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {selectedImage && (
                <div className="flex items-center gap-3 p-2 rounded-xl"
                  style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                  <div className="w-16 h-10 rounded overflow-hidden flex-shrink-0" style={{ background: '#1F1B17' }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={selectedImage} alt="selected style" className="w-full h-full object-cover" />
                  </div>
                  <div className="flex-1">
                    <p className="text-[11px] font-semibold" style={{ color: 'var(--text-dark)' }}>Style reference</p>
                    <p className="text-[10px]" style={{ color: 'var(--text-light)' }}>Clip will match this look</p>
                  </div>
                  <button onClick={() => setStep('preview')}
                    className="text-[11px] font-semibold"
                    style={{ color: 'var(--coral)', background: 'none', border: 'none', cursor: 'pointer' }}>
                    Change
                  </button>
                </div>
              )}

              {/* Duration slider */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[12px] font-bold" style={{ color: 'var(--text-mid)' }}>Duration</label>
                  <span className="text-[13px] font-bold" style={{ color: 'var(--coral)' }}>{duration} sec</span>
                </div>
                <input type="range" min="5" max="120" step="5" value={duration}
                  onChange={e => setDuration(parseInt(e.target.value))}
                  className="w-full" style={{ accentColor: 'var(--coral)' }} />
                <div className="flex justify-between text-[9px]" style={{ color: 'var(--text-light)' }}>
                  <span>5s</span><span>30s</span><span>60s</span><span>120s</span>
                </div>
              </div>

              {loadingCost && (
                <div className="flex items-center gap-2 text-[12px]" style={{ color: 'var(--text-light)' }}>
                  <Loader2 className="w-4 h-4 animate-spin" /> Calculating…
                </div>
              )}

              {cost && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-semibold" style={{ color: 'var(--text-mid)' }}>Credit cost</span>
                    <span className="text-[16px] font-bold" style={{ color: 'var(--coral)' }}>
                      {cost.credits_needed} credits
                    </span>
                  </div>
                  <div className="p-3 rounded-xl text-[12px]"
                    style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
                    <div className="flex justify-between">
                      <span style={{ color: 'var(--text-mid)' }}>Your balance</span>
                      <span className="font-bold" style={{ color: 'var(--text-dark)' }}>{cost.balance.total} credits</span>
                    </div>
                    <div className="flex justify-between mt-0.5 pl-3">
                      <span style={{ color: 'var(--text-light)' }}>· Monthly (resets)</span>
                      <span style={{ color: 'var(--text-light)' }}>{cost.balance.monthly}</span>
                    </div>
                    <div className="flex justify-between pl-3">
                      <span style={{ color: 'var(--text-light)' }}>· Purchased (no expiry)</span>
                      <span style={{ color: 'var(--text-light)' }}>{cost.balance.purchased}</span>
                    </div>
                    {cost.after && (
                      <>
                        <hr className="my-2" style={{ borderColor: 'var(--border)' }} />
                        <div className="flex justify-between">
                          <span style={{ color: 'var(--text-mid)' }}>After this clip</span>
                          <span className="font-bold" style={{ color: 'var(--sage)' }}>{cost.after.total} credits</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {warning && (
                <div className="p-2.5 rounded-lg flex items-start gap-2 text-[12px]"
                  style={{ background: warnStyle.bg, border: `1px solid ${warnStyle.border}`, color: warnStyle.color }}>
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                  <span>{warning.label}</span>
                </div>
              )}

              {warning?.require_confirm && (
                <label className="flex items-center gap-2 cursor-pointer text-[12px]">
                  <input type="checkbox" checked={acknowledged}
                    onChange={e => setAcknowledged(e.target.checked)}
                    style={{ accentColor: 'var(--coral)' }} />
                  <span style={{ color: 'var(--text-dark)' }}>
                    I understand this clip uses {cost?.credits_needed} credits.
                  </span>
                </label>
              )}

              {insufficient && (
                <div className="p-3 rounded-xl"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#B91C1C' }}>
                  <p className="text-[13px] font-bold mb-1">Not enough credits</p>
                  <p className="text-[11px] mb-2">
                    You can afford up to <strong>{affordableMaxSec} seconds</strong> with your current balance.
                  </p>
                  <Link href="/billing"
                    className="inline-block px-3 py-1.5 rounded-lg text-[12px] font-semibold text-white"
                    style={{ background: 'var(--coral)' }}>
                    Buy more credits
                  </Link>
                </div>
              )}

              {error && (
                <div className="p-2.5 rounded-lg text-[12px]"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#EF4444' }}>
                  {error}
                </div>
              )}
            </div>

            <div className="p-5 flex justify-between gap-2" style={{ borderTop: '1px solid var(--border)' }}>
              <button onClick={() => setStep('preview')}
                className="px-4 py-2 rounded-xl text-[13px] font-semibold"
                style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
                ← Back
              </button>
              <button onClick={handleGenerate}
                disabled={generating || !cost?.sufficient || requiresConfirm || loadingCost}
                className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2 disabled:opacity-50"
                style={{ background: 'var(--coral)' }}>
                {generating
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</>
                  : <><Play className="w-4 h-4" /> Generate Clip</>}
              </button>
            </div>
          </>
        )}
      </div>

      {editingPreview && (
        <InpaintEditor
          imageUrl={editingPreview}
          teacherId={teacherId}
          onComplete={(newUrl) => {
            setPreviews(prev => prev.map(p => p === editingPreview ? newUrl : p));
            if (selectedImage === editingPreview) setSelectedImage(newUrl);
            setEditingPreview(null);
          }}
          onClose={() => setEditingPreview(null)}
        />
      )}
    </div>
  );
}
