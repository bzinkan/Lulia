'use client';
import { useState } from 'react';
import { X, CheckCircle, Loader2, Trash2, Plus, AlertTriangle } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const DAY_TYPES = [
  { id: 'holiday',                  label: 'Holiday' },
  { id: 'break',                    label: 'Break' },
  { id: 'professional_development', label: 'PD Day' },
  { id: 'half_day',                 label: 'Half Day' },
  { id: 'snow_day',                 label: 'Snow Day' },
  { id: 'no_school',                label: 'No School' },
];

const TYPE_COLORS = {
  holiday: '#EF4444',
  break: '#F97316',
  professional_development: '#8B5CF6',
  half_day: '#E9B44C',
  snow_day: '#3B82F6',
  no_school: '#94A3B8',
};

/**
 * SchoolCalendarPreviewModal — step 2 of the upload flow.
 *
 * Shows all entries extracted by Haiku. Teacher can:
 *  - Uncheck rows to exclude them
 *  - Edit date / type / label inline
 *  - Delete rows
 *  - Add a row the AI missed
 * Clicking Save posts only the checked, valid rows to /school-calendar/confirm.
 *
 * Props:
 *   parsed: { entries: [{date, day_type, label}], school_year, total }
 *   teacherId: string
 *   onSaved: (result) => void
 *   onClose: () => void
 */
export default function SchoolCalendarPreviewModal({ parsed, teacherId, onSaved, onClose }) {
  const [rows, setRows] = useState(() =>
    (parsed.entries || []).map((e, i) => ({
      ...e,
      _id: i,
      _checked: true,
    }))
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function update(id, patch) {
    setRows(prev => prev.map(r => r._id === id ? { ...r, ...patch } : r));
  }
  function remove(id) {
    setRows(prev => prev.filter(r => r._id !== id));
  }
  function add() {
    const nextId = Math.max(0, ...rows.map(r => r._id)) + 1;
    const today = new Date().toISOString().slice(0, 10);
    setRows([...rows, { _id: nextId, _checked: true, date: today, day_type: 'holiday', label: '' }]);
  }

  async function handleSave() {
    const checked = rows.filter(r => r._checked && r.date && r.day_type);
    if (checked.length === 0) {
      setError('Nothing to save — check at least one row.');
      return;
    }
    setSaving(true); setError(null);
    try {
      const result = await apiFetch('/api/v1/upload/school-calendar/confirm', {
        method: 'POST',
        body: JSON.stringify({
          teacher_id: teacherId,
          school_year: parsed.school_year,
          entries: checked.map(r => ({ date: r.date, day_type: r.day_type, label: r.label || null })),
        }),
      });
      onSaved?.(result);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const checkedCount = rows.filter(r => r._checked).length;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-3xl mx-4 max-h-[92vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div>
            <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
              Review Extracted Days
            </h3>
            <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-light)' }}>
              Lulia found {parsed.total} non-school days for {parsed.school_year}. Uncheck anything wrong, edit as needed, then save.
            </p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-light)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* AI notice */}
        <div className="px-5 pt-3">
          <div className="p-2.5 rounded-lg flex items-start gap-2 text-[11px]"
            style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)', color: 'var(--text-mid)' }}>
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: '#F59E0B' }} />
            <span>
              AI-extracted — not perfect. Common issues: multi-day breaks missing some dates, wrong year
              for Dec/Jan entries, or Midterm Week / End of Quarter marked by mistake.
            </span>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
            <table className="w-full text-[12px]">
              <thead>
                <tr style={{ background: 'var(--cream)', borderBottom: '1px solid var(--border)' }}>
                  <th className="px-2 py-2 text-left font-bold w-8" style={{ color: 'var(--text-light)' }}></th>
                  <th className="px-2 py-2 text-left font-bold" style={{ color: 'var(--text-light)' }}>Date</th>
                  <th className="px-2 py-2 text-left font-bold" style={{ color: 'var(--text-light)' }}>Type</th>
                  <th className="px-2 py-2 text-left font-bold" style={{ color: 'var(--text-light)' }}>Label</th>
                  <th className="px-2 py-2 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r._id}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      opacity: r._checked ? 1 : 0.45,
                      background: r._checked ? 'var(--warm-card)' : 'transparent',
                    }}>
                    <td className="px-2 py-1.5">
                      <input type="checkbox" checked={r._checked}
                        onChange={e => update(r._id, { _checked: e.target.checked })}
                        style={{ accentColor: 'var(--coral)' }} />
                    </td>
                    <td className="px-2 py-1.5">
                      <input type="date" value={r.date || ''}
                        onChange={e => update(r._id, { date: e.target.value })}
                        className="px-2 py-1 rounded-md text-[11px]"
                        style={{ border: '1px solid var(--border)', background: 'white' }} />
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="inline-block w-2 h-2 rounded-full"
                          style={{ background: TYPE_COLORS[r.day_type] || '#94A3B8' }} />
                        <select value={r.day_type || 'holiday'}
                          onChange={e => update(r._id, { day_type: e.target.value })}
                          className="px-2 py-1 rounded-md text-[11px]"
                          style={{ border: '1px solid var(--border)', background: 'white' }}>
                          {DAY_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
                        </select>
                      </div>
                    </td>
                    <td className="px-2 py-1.5">
                      <input value={r.label || ''}
                        onChange={e => update(r._id, { label: e.target.value })}
                        placeholder="(no label)"
                        className="w-full px-2 py-1 rounded-md text-[11px]"
                        style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }} />
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <button onClick={() => remove(r._id)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444' }}
                        title="Remove this row">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button onClick={add}
            className="mt-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold"
            style={{ color: 'var(--coral)', background: 'var(--cream)', border: '1px solid var(--border)', cursor: 'pointer' }}>
            <Plus className="w-3.5 h-3.5" /> Add a day
          </button>

          {error && (
            <div className="mt-3 p-2.5 rounded-lg text-[12px]"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid #EF4444', color: '#EF4444' }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 flex items-center justify-between" style={{ borderTop: '1px solid var(--border)' }}>
          <span className="text-[12px] font-semibold" style={{ color: 'var(--text-mid)' }}>
            {checkedCount} of {rows.length} will be saved
          </span>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold"
              style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
              Cancel
            </button>
            <button onClick={handleSave} disabled={saving || checkedCount === 0}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white flex items-center gap-2 disabled:opacity-50"
              style={{ background: 'var(--sage)' }}>
              {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</> : <><CheckCircle className="w-4 h-4" /> Confirm &amp; Save ({checkedCount})</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
