'use client';
import { useState } from 'react';
import {
  CheckCircle, Copy, ExternalLink, Loader2, RefreshCw,
  ArrowLeft, Sparkles, X as CloseIcon,
} from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { chipsForTemplate } from '@/lib/interactiveRefinementChips';

/**
 * Current-result panel for the Interactive page.
 *
 * Shows a live iframe of the generated activity + refinement chip row.
 * Clicking a chip calls POST /api/v1/interactive/{id}/refine which creates
 * a NEW activity (preserves original for before/after). A small "← Previous"
 * button appears once a refinement exists so teachers can compare.
 *
 * Props:
 *   activity — { activity_id, access_code, access_url, template, ... }
 *   onResult(newActivity) — bubble new activity up so the page can refresh
 *                           its library + keep showing the latest
 */
export default function InteractiveResult({ activity, onResult }) {
  // Stack of results — first = original, last = current showing
  const [history, setHistory] = useState([activity]);
  const [refining, setRefining] = useState(false);
  const [error, setError] = useState(null);
  const [customMode, setCustomMode] = useState(false);
  const [customText, setCustomText] = useState('');

  const current = history[history.length - 1];
  const chips = chipsForTemplate(current.template);

  async function applyChip(chip, customInstructions = null) {
    setRefining(true);
    setError(null);
    setCustomMode(false);
    try {
      const res = await apiFetch(`/api/v1/interactive/${current.activity_id}/refine`, {
        method: 'POST',
        body: JSON.stringify({
          instruction_id: chip.id,
          custom_instructions: customInstructions,
        }),
      });
      if (res?.error) {
        setError(res.error);
      } else if (res?.activity_id) {
        setHistory(h => [...h, res]);
        onResult?.(res);
      } else {
        setError('Refinement returned an unexpected response.');
      }
    } catch (e) {
      setError(e?.message || 'Refinement failed. Try again?');
    } finally {
      setRefining(false);
    }
  }

  function goBack() {
    if (history.length <= 1) return;
    setHistory(h => h.slice(0, -1));
    setError(null);
  }

  function submitCustom() {
    const t = customText.trim();
    if (t.length < 3) return;
    applyChip({ id: 'custom' }, t);
    setCustomText('');
  }

  return (
    <div className="rounded-card p-5 mb-5"
      style={{
        background: 'var(--warm-card)',
        border: '2px solid var(--coral)',
        boxShadow: '0 4px 16px rgba(216,108,82,0.15)',
      }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <CheckCircle className="w-5 h-5" style={{ color: 'var(--sage)' }} />
          <h2 className="font-serif text-[18px]" style={{ color: 'var(--text-dark)' }}>
            Activity ready
          </h2>
          {history.length > 1 && (
            <span className="text-[11px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider"
              style={{ background: 'rgba(216,108,82,0.12)', color: 'var(--coral)' }}>
              V{history.length}
            </span>
          )}
        </div>
        {history.length > 1 && (
          <button onClick={goBack}
            className="flex items-center gap-1 text-[12px] font-semibold px-3 py-1.5 rounded-full"
            style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-mid)', cursor: 'pointer' }}>
            <ArrowLeft className="w-3 h-3" /> Previous version
          </button>
        )}
      </div>

      {/* Access code + URL */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-mid)' }}>
          Access code
        </span>
        <AccessCode code={current.access_code} />
        {current.access_url && (
          <a href={current.access_url} target="_blank" rel="noopener"
            className="text-[12px] font-semibold underline inline-flex items-center gap-1"
            style={{ color: 'var(--coral)' }}>
            Open in new tab <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>

      {/* Iframe preview */}
      <div className="rounded-xl overflow-hidden relative mb-4"
        style={{ background: 'var(--cream)', border: '1px solid var(--border)', height: 520 }}>
        {refining && (
          <div className="absolute inset-0 z-10 flex items-center justify-center"
            style={{ background: 'rgba(254,249,242,0.85)', backdropFilter: 'blur(2px)' }}>
            <div className="text-center">
              <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin" style={{ color: 'var(--coral)' }} />
              <p className="text-[13px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                Refining activity…
              </p>
              <p className="text-[11px] mt-1" style={{ color: 'var(--text-mid)' }}>
                Usually takes 10-20 seconds
              </p>
            </div>
          </div>
        )}
        {current.access_url ? (
          <iframe
            key={current.activity_id}
            src={current.access_url}
            title="Activity preview"
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-[13px]" style={{ color: 'var(--text-mid)' }}>
              Preview not available. Use the access code on the student device.
            </p>
          </div>
        )}
      </div>

      {/* Refinement chips (Pattern C) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider"
            style={{ color: 'var(--text-mid)' }}>
            Not quite right?
          </span>
        </div>

        {customMode ? (
          <div className="flex items-start gap-2">
            <textarea
              value={customText}
              onChange={e => setCustomText(e.target.value)}
              placeholder="Describe what to change — e.g. 'replace the 2-digit numbers with 3-digit numbers and add a word-bank of 6 extra distractors'"
              rows={2}
              className="flex-1 rounded-xl p-3 text-[13px] outline-none resize-none"
              style={{
                border: '1px solid var(--border)', background: 'white',
                color: 'var(--text-dark)', fontFamily: "'Nunito', sans-serif",
              }} />
            <div className="flex flex-col gap-1">
              <button onClick={submitCustom} disabled={refining || customText.trim().length < 3}
                className="px-3 py-2 rounded-xl text-[12px] font-bold text-white flex items-center gap-1"
                style={{
                  background: customText.trim().length >= 3 ? 'var(--coral)' : 'var(--coral-light)',
                  cursor: customText.trim().length >= 3 ? 'pointer' : 'not-allowed',
                  opacity: customText.trim().length >= 3 ? 1 : 0.6,
                }}>
                <Sparkles className="w-3.5 h-3.5" /> Apply
              </button>
              <button onClick={() => { setCustomMode(false); setCustomText(''); }}
                className="px-3 py-1 rounded-xl text-[11px]"
                style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-mid)', cursor: 'pointer' }}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {chips.map(chip => (
              <button key={chip.id} onClick={() => chip.opensTextarea ? setCustomMode(true) : applyChip(chip)}
                disabled={refining}
                className="text-[12px] font-semibold px-3 py-1.5 rounded-full inline-flex items-center gap-1 transition-all"
                style={{
                  background: chip.opensTextarea ? 'transparent' : 'var(--cream)',
                  border: `1px ${chip.opensTextarea ? 'dashed' : 'solid'} var(--border)`,
                  color: 'var(--text-mid)',
                  cursor: refining ? 'not-allowed' : 'pointer',
                  opacity: refining ? 0.5 : 1,
                }}
                onMouseEnter={e => {
                  if (!refining) {
                    e.currentTarget.style.background = 'var(--warm-bg, #F5EDE0)';
                    e.currentTarget.style.color = 'var(--coral)';
                    e.currentTarget.style.borderColor = 'var(--coral)';
                  }
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = chip.opensTextarea ? 'transparent' : 'var(--cream)';
                  e.currentTarget.style.color = 'var(--text-mid)';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}>
                {chip.opensTextarea && <RefreshCw className="w-3 h-3" />}
                {chip.label}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="mt-3 p-3 rounded-xl text-[12px]"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #FECACA', color: '#B91C1C' }}>
            {error}
            <button onClick={() => setError(null)}
              className="ml-2 text-[11px] underline inline-flex items-center gap-1"
              style={{ cursor: 'pointer' }}>
              <CloseIcon className="w-3 h-3" /> Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function AccessCode({ code }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <>
      <span className="text-[13px] font-mono font-bold px-2 py-1 rounded-md"
        style={{ background: 'white', color: 'var(--coral)', border: '1px solid var(--border)' }}>
        {code}
      </span>
      <button onClick={copy} title="Copy code"
        className="p-1 rounded-md" style={{ color: 'var(--text-mid)', cursor: 'pointer' }}>
        {copied ? <CheckCircle className="w-3.5 h-3.5" style={{ color: 'var(--sage)' }} /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    </>
  );
}
