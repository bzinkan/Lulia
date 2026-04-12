'use client';
import { useEffect, useState } from 'react';
import { X, Play, Loader2, AlertTriangle, Film, Lock } from 'lucide-react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api';

const WARN_STYLES = {
  green:  { bg: 'rgba(107,160,138,0.08)', color: 'var(--sage)',   border: 'var(--sage)'  },
  yellow: { bg: 'rgba(245,158,11,0.08)',  color: '#B45309',        border: '#F59E0B'      },
  red:    { bg: 'rgba(239,68,68,0.08)',   color: '#B91C1C',        border: '#EF4444'      },
};

/**
 * Pre-generation modal for a Short Clip.
 * Reused by: /clips page, Print & Go, Planner ShortClipRefiner.
 *
 * Props:
 *   prompt: string — what the clip will show
 *   initialDuration: number — default seconds (e.g. 30)
 *   teacherId: string
 *   classId?: string
 *   topicLabel?: string — stored for search/filing
 *   onGenerated: (clip) => void — parent handler receives {clip_id, primary_uri, ...}
 *   onClose: () => void
 */
export default function ClipCostModal({
  prompt, initialDuration = 30, teacherId, classId, topicLabel,
  onGenerated, onClose,
}) {
  const [duration, setDuration] = useState(initialDuration);
  const [cost, setCost] = useState(null);
  const [loadingCost, setLoadingCost] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [tierBlock, setTierBlock] = useState(null);

  // Fetch live cost preview whenever duration changes
  useEffect(() => {
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
  }, [duration, teacherId]);

  const warning = cost?.warning;
  const warnStyle = warning ? WARN_STYLES[warning.level] : WARN_STYLES.green;
  const requiresConfirm = warning?.require_confirm && !acknowledged;

  async function handleGenerate() {
    if (!cost?.sufficient) return;
    if (warning?.require_confirm && !acknowledged) return;
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
        }),
      });
      onGenerated?.(clip);
      onClose();
    } catch (e) {
      // 402 = tier or credit block
      if (e.status === 402) {
        const msg = e.body?.error || e.message;
        if (e.body?.tier_required) setTierBlock(e.body);
        else setError(msg);
      } else {
        setError(e.message);
      }
    } finally {
      setGenerating(false);
    }
  }

  const insufficient = cost && !cost.sufficient;
  const affordableMaxSec = cost?.balance?.total
    ? Math.floor(cost.balance.total / (cost.rate_per_sec || 3))
    : 0;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-md mx-4"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2">
            <Film className="w-5 h-5" style={{ color: 'var(--coral)' }} />
            <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
              Generate Short Clip
            </h3>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-light)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Tier lock */}
          {tierBlock && (
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
          )}

          {!tierBlock && (
            <>
              {/* Prompt preview */}
              <div className="p-3 rounded-xl text-[12px]"
                style={{ background: 'var(--cream)', border: '1px solid var(--border)', color: 'var(--text-mid)' }}>
                <span className="font-bold" style={{ color: 'var(--text-dark)' }}>Prompt: </span>
                {prompt}
              </div>

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

              {/* Cost & balance */}
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

              {/* Warning band */}
              {warning && (
                <div className="p-2.5 rounded-lg flex items-start gap-2 text-[12px]"
                  style={{ background: warnStyle.bg, border: `1px solid ${warnStyle.border}`, color: warnStyle.color }}>
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                  <span>{warning.label}</span>
                </div>
              )}

              {/* Hard-confirm checkbox */}
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

              {/* Insufficient funds */}
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
            </>
          )}
        </div>

        {/* Footer */}
        {!tierBlock && (
          <div className="p-5 flex justify-end gap-2" style={{ borderTop: '1px solid var(--border)' }}>
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold"
              style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
              Cancel
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
        )}
      </div>
    </div>
  );
}
