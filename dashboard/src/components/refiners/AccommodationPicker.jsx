'use client';
import { ACCOMMODATION_OPTIONS } from '@/lib/plannerVariants';

/**
 * Shared accommodation checkboxes shown at the bottom of every refiner.
 * Defaults to empty (off). Parent passes `value` (string[]) and `onChange`.
 */
export default function AccommodationPicker({ value = [], onChange }) {
  function toggle(id) {
    if (value.includes(id)) onChange(value.filter(v => v !== id));
    else onChange([...value, id]);
  }

  return (
    <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
      <p className="text-[12px] font-bold mb-2" style={{ color: 'var(--text-mid)' }}>
        Accommodation Versions <span style={{ color: 'var(--text-light)', fontWeight: 400 }}>(optional)</span>
      </p>
      <div className="grid grid-cols-2 gap-2">
        {ACCOMMODATION_OPTIONS.map(opt => {
          const checked = value.includes(opt.id);
          return (
            <label
              key={opt.id}
              className="flex items-center gap-2 p-2 rounded-lg cursor-pointer"
              style={{
                background: checked ? 'var(--cream)' : 'transparent',
                border: `1px solid ${checked ? opt.color : 'var(--border)'}`,
              }}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(opt.id)}
                style={{ accentColor: opt.color }}
              />
              <span
                className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                style={{ background: opt.color }}
              />
              <span className="text-[12px] font-semibold" style={{ color: 'var(--text-dark)' }}>
                {opt.label}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
