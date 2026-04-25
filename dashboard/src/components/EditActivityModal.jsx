'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { Loader2, X, Plus, Trash2, Save, RefreshCw } from 'lucide-react';
import { chipsForTemplate } from '@/lib/interactiveRefinementChips';

/**
 * Edit modal — fetches an activity's data and renders:
 *   - a per-template form editor when the activity was generated in
 *     structured mode (crossword, word_search, flashcards, timeline,
 *     number_line)
 *   - the refine-chip panel when the activity was generated in artifact
 *     mode (MCQ, fill-in-blank, drag-drop, matching, etc.)
 *
 * On save, structured activities PUT /data which rebuilds the HTML in
 * place. Artifact refine creates a NEW activity and callers should
 * refresh their list.
 */
export default function EditActivityModal({ activity, onClose, onSaved }) {
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState(null); // 'structured' | 'artifact'
  const [data, setData] = useState(null);
  const [templateId, setTemplateId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await apiFetch(`/api/v1/interactive/${activity.activity_id}/data`);
        if (cancelled) return;
        setMode(r.mode);
        setTemplateId(r.template_id);
        setData(r.data);
      } catch (e) {
        setError(e?.message || 'Failed to load activity data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [activity.activity_id]);

  async function save(newData) {
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/interactive/${activity.activity_id}/data`, {
        method: 'PUT',
        body: JSON.stringify({ data: newData }),
      });
      onSaved?.();
      onClose?.();
    } catch (e) {
      setError(e?.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.4)' }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="rounded-card w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', border: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--coral)' }}>
              Edit activity
            </div>
            <div className="text-sm font-semibold" style={{ color: 'var(--text-dark)' }}>
              {activity.content_json?.title || 'Activity'}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md" style={{ color: 'var(--text-mid)' }}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {loading && (
            <div className="flex items-center gap-2 py-8 justify-center" style={{ color: 'var(--text-mid)' }}>
              <Loader2 className="w-4 h-4 animate-spin" /> Loading…
            </div>
          )}
          {error && !loading && (
            <div className="p-3 rounded-md text-sm" style={{ background: '#FEF2F2', color: '#B91C1C' }}>
              {error}
            </div>
          )}
          {!loading && mode === 'structured' && data && (
            <StructuredEditor
              templateId={templateId}
              data={data}
              onSave={save}
              saving={saving}
            />
          )}
          {!loading && mode === 'artifact' && (
            <ArtifactRefineEditor activity={activity} templateId={templateId} onRefined={onSaved} />
          )}
        </div>
      </div>
    </div>
  );
}


function StructuredEditor({ templateId, data, onSave, saving }) {
  const [local, setLocal] = useState(() => JSON.parse(JSON.stringify(data)));

  function update(path, value) {
    setLocal(d => {
      const next = JSON.parse(JSON.stringify(d));
      let cur = next;
      for (let i = 0; i < path.length - 1; i++) cur = cur[path[i]];
      cur[path[path.length - 1]] = value;
      return next;
    });
  }
  function removeAt(listKey, idx) {
    setLocal(d => {
      const next = JSON.parse(JSON.stringify(d));
      next[listKey].splice(idx, 1);
      return next;
    });
  }
  function addItem(listKey, template) {
    setLocal(d => {
      const next = JSON.parse(JSON.stringify(d));
      next[listKey] = [...(next[listKey] || []), template];
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <TitleField value={local.title || ''} onChange={v => update(['title'], v)} />

      {templateId === 'crossword' && (
        <>
          <label className="flex items-center gap-2 p-2 rounded-md cursor-pointer"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
            <input type="checkbox" checked={!!local.word_bank}
              onChange={e => update(['word_bank'], e.target.checked)} />
            <span className="text-[13px]" style={{ color: 'var(--text-dark)' }}>
              Show <strong>word bank</strong> (lists all answer words above the grid — scaffolds for younger / struggling students)
            </span>
          </label>
          <ListEditor label="Words & clues" items={local.words || []}
            onAdd={() => addItem('words', { answer: '', clue: '' })}
            render={(w, i) => (
              <>
                <input className="editor-input w-32 font-mono uppercase" value={w.answer}
                  placeholder="ANSWER"
                  onChange={e => update(['words', i, 'answer'], e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))} />
                <input className="editor-input flex-1" value={w.clue} placeholder="Clue"
                  onChange={e => update(['words', i, 'clue'], e.target.value)} />
              </>
            )}
            onRemove={i => removeAt('words', i)} />
        </>
      )}

      {templateId === 'word_search' && (
        <ListEditor label="Words to find" items={local.words || []}
          onAdd={() => addItem('words', '')}
          render={(w, i) => (
            <input className="editor-input flex-1 font-mono uppercase" value={w} placeholder="WORD"
              onChange={e => update(['words', i], e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))} />
          )}
          onRemove={i => removeAt('words', i)} />
      )}

      {templateId === 'flash_cards_interactive' && (
        <ListEditor label="Cards (term + definition)" items={local.cards || []}
          onAdd={() => addItem('cards', { front: '', back: '' })}
          render={(c, i) => (
            <div className="flex-1 flex flex-col gap-1.5">
              <input className="editor-input" value={c.front} placeholder="Term"
                onChange={e => update(['cards', i, 'front'], e.target.value)} />
              <textarea className="editor-input" rows={2} value={c.back} placeholder="Definition"
                onChange={e => update(['cards', i, 'back'], e.target.value)} />
            </div>
          )}
          onRemove={i => removeAt('cards', i)} />
      )}

      {templateId === 'timeline' && (
        <ListEditor label="Events" items={local.events || []}
          onAdd={() => addItem('events', { label: '', date: '', description: '' })}
          render={(ev, i) => (
            <div className="flex-1 flex flex-col gap-1.5">
              <input className="editor-input" value={ev.label} placeholder="Event label"
                onChange={e => update(['events', i, 'label'], e.target.value)} />
              <div className="flex gap-1.5">
                <input className="editor-input w-28" value={ev.date} placeholder="Date / year"
                  onChange={e => update(['events', i, 'date'], e.target.value)} />
                <input className="editor-input flex-1" value={ev.description || ''} placeholder="Short description"
                  onChange={e => update(['events', i, 'description'], e.target.value)} />
              </div>
            </div>
          )}
          onRemove={i => removeAt('events', i)} />
      )}

      {templateId === 'fill_in_blank' && (
        <>
          <label className="flex items-center gap-2 p-2 rounded-md cursor-pointer"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
            <input type="checkbox" checked={!!local.word_bank}
              onChange={e => update(['word_bank'], e.target.checked)} />
            <span className="text-[13px]" style={{ color: 'var(--text-dark)' }}>
              Show <strong>word bank</strong> — lists all answer words as clickable pills above the items (scaffold for younger / struggling students)
            </span>
          </label>
          <ListEditor label="Sentences & answers" items={local.items || []}
            onAdd={() => addItem('items', { sentence: 'The ___ is ...', answer: '', hint: '' })}
            render={(it, i) => (
              <div className="flex-1 flex flex-col gap-1.5">
                <textarea className="editor-input" rows={2} value={it.sentence}
                  placeholder='Sentence with "___" where the blank goes'
                  onChange={e => update(['items', i, 'sentence'], e.target.value)} />
                <div className="flex gap-1.5">
                  <input className="editor-input flex-1" value={it.answer} placeholder="Answer"
                    onChange={e => update(['items', i, 'answer'], e.target.value)} />
                  <input className="editor-input flex-1" value={it.hint || ''} placeholder="Hint (optional)"
                    onChange={e => update(['items', i, 'hint'], e.target.value)} />
                </div>
              </div>
            )}
            onRemove={i => removeAt('items', i)} />
        </>
      )}

      {templateId === 'number_line' && (
        <>
          <div className="flex gap-2">
            <NumField label="Min" value={local.min} onChange={v => update(['min'], v)} />
            <NumField label="Max" value={local.max} onChange={v => update(['max'], v)} />
            <NumField label="Interval" value={local.interval} onChange={v => update(['interval'], v)} />
          </div>
          <ListEditor label="Questions" items={local.questions || []}
            onAdd={() => addItem('questions', { text: '', answer: 0 })}
            render={(q, i) => (
              <div className="flex-1 flex flex-col gap-1.5">
                <input className="editor-input" value={q.text} placeholder="Question prompt"
                  onChange={e => update(['questions', i, 'text'], e.target.value)} />
                <input className="editor-input w-24" type="number" value={q.answer} placeholder="Answer"
                  onChange={e => update(['questions', i, 'answer'], Number(e.target.value))} />
              </div>
            )}
            onRemove={i => removeAt('questions', i)} />
        </>
      )}

      <div className="flex gap-2 justify-end pt-2">
        <button className="btn-primary flex items-center gap-1.5" disabled={saving}
          onClick={() => onSave(local)}>
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>

      <style jsx>{`
        .editor-input {
          border: 1px solid var(--border);
          background: white;
          border-radius: 8px;
          padding: 8px 10px;
          font-size: 13px;
          font-family: inherit;
          color: var(--text-dark);
          outline: none;
          width: 100%;
        }
        .editor-input:focus {
          border-color: var(--coral);
          box-shadow: 0 0 0 3px rgba(249,115,22,0.1);
        }
        .btn-primary {
          background: var(--coral);
          color: white;
          border: none;
          border-radius: 10px;
          padding: 9px 18px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
        }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
      `}</style>
    </div>
  );
}


function TitleField({ value, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-mid)' }}>
        Title
      </label>
      <input className="editor-input" value={value} onChange={e => onChange(e.target.value)} placeholder="Activity title" />
      <style jsx>{`
        .editor-input {
          border: 1px solid var(--border);
          background: white;
          border-radius: 8px;
          padding: 8px 10px;
          font-size: 13px;
          outline: none;
          width: 100%;
          font-family: inherit;
          color: var(--text-dark);
        }
        .editor-input:focus { border-color: var(--coral); box-shadow: 0 0 0 3px rgba(249,115,22,0.1); }
      `}</style>
    </div>
  );
}


function NumField({ label, value, onChange }) {
  return (
    <div className="flex flex-col gap-1 flex-1">
      <label className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-mid)' }}>
        {label}
      </label>
      <input className="num-input" type="number" value={value ?? ''} step="any"
        onChange={e => onChange(Number(e.target.value))} />
      <style jsx>{`
        .num-input {
          border: 1px solid var(--border);
          background: white;
          border-radius: 8px;
          padding: 8px 10px;
          font-size: 13px;
          outline: none;
          color: var(--text-dark);
          font-family: inherit;
        }
        .num-input:focus { border-color: var(--coral); box-shadow: 0 0 0 3px rgba(249,115,22,0.1); }
      `}</style>
    </div>
  );
}


function ListEditor({ label, items, render, onAdd, onRemove }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <label className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-mid)' }}>
          {label} ({items.length})
        </label>
        <button onClick={onAdd}
          className="text-[12px] px-2 py-1 rounded-md font-medium flex items-center gap-1"
          style={{ background: 'var(--cream)', color: 'var(--coral)', border: '1px solid var(--border)' }}>
          <Plus className="w-3 h-3" /> Add
        </button>
      </div>
      <div className="flex flex-col gap-2">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2 p-2 rounded-md"
            style={{ background: 'var(--cream)', border: '1px solid var(--border)' }}>
            <div className="text-[11px] font-mono mt-2" style={{ color: 'var(--text-mid)', minWidth: 18 }}>
              {i + 1}.
            </div>
            {render(item, i)}
            <button onClick={() => onRemove(i)} className="p-1 rounded-md"
              style={{ color: '#B91C1C' }} title="Remove">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <div className="text-[12px] py-4 text-center" style={{ color: 'var(--text-mid)' }}>
            No items yet — click "Add" to create one.
          </div>
        )}
      </div>
    </div>
  );
}


function ArtifactRefineEditor({ activity, templateId, onRefined }) {
  const chips = chipsForTemplate(templateId || 'multiple_choice_quiz');
  const [busy, setBusy] = useState(false);
  const [customText, setCustomText] = useState('');
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState(null);

  async function applyChip(chip, custom = null) {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/interactive/${activity.activity_id}/refine`, {
        method: 'POST',
        body: JSON.stringify({
          instruction_id: chip.id,
          custom_instructions: custom,
        }),
      });
      if (res?.error) setError(res.error);
      else { setLastResult(res); onRefined?.(); }
    } catch (e) {
      setError(e?.message || 'Refinement failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="text-[13px]" style={{ color: 'var(--text-mid)' }}>
        This activity was generated with AI artifact mode — its HTML is unique. Use a refinement to regenerate a tweaked version.
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chips.map(chip => (
          <button key={chip.id} disabled={busy}
            onClick={() => chip.opensTextarea ? null : applyChip(chip)}
            className="text-[12px] px-3 py-1.5 rounded-full font-medium"
            style={{ background: chip.opensTextarea ? 'transparent' : 'var(--cream)',
                     border: `1px ${chip.opensTextarea ? 'dashed' : 'solid'} var(--border)`,
                     color: 'var(--text-dark)',
                     cursor: busy ? 'default' : 'pointer',
                     opacity: busy ? 0.5 : 1 }}>
            {chip.label}
          </button>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        <label className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-mid)' }}>
          Or describe your change
        </label>
        <textarea rows={2} value={customText} onChange={e => setCustomText(e.target.value)}
          placeholder="e.g. Use only words from our vocab list this week."
          className="custom-input" />
        <button disabled={busy || !customText.trim()}
          onClick={() => applyChip({ id: 'custom' }, customText.trim())}
          className="self-end text-[12px] px-3 py-1.5 rounded-md font-medium flex items-center gap-1"
          style={{ background: 'var(--coral)', color: 'white', cursor: busy || !customText.trim() ? 'not-allowed' : 'pointer', opacity: busy || !customText.trim() ? 0.5 : 1 }}>
          {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
          Regenerate
        </button>
      </div>
      {lastResult?.activity_id && (
        <div className="p-3 rounded-md text-[13px]" style={{ background: '#DCFCE7', color: '#15803D' }}>
          New version created. Close this modal to refresh the library.
        </div>
      )}
      {error && (
        <div className="p-3 rounded-md text-[13px]" style={{ background: '#FEF2F2', color: '#B91C1C' }}>
          {error}
        </div>
      )}
      <style jsx>{`
        .custom-input {
          border: 1px solid var(--border);
          background: white;
          border-radius: 8px;
          padding: 8px 10px;
          font-size: 13px;
          outline: none;
          color: var(--text-dark);
          font-family: inherit;
          resize: vertical;
        }
        .custom-input:focus { border-color: var(--coral); box-shadow: 0 0 0 3px rgba(249,115,22,0.1); }
      `}</style>
    </div>
  );
}
