'use client';
import { useState } from 'react';
import { X, CheckCircle, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';
import { categoryForTemplate } from '@/lib/plannerVariants';
import WorksheetRefiner from './refiners/WorksheetRefiner';
import SlidesRefiner from './refiners/SlidesRefiner';
import FormsRefiner from './refiners/FormsRefiner';
import InteractiveRefiner from './refiners/InteractiveRefiner';
import GameRefiner from './refiners/GameRefiner';
import VideoRefiner from './refiners/VideoRefiner';
import QuizRefiner from './refiners/QuizRefiner';

const REFINERS = {
  worksheet: WorksheetRefiner,
  slides: SlidesRefiner,
  forms: FormsRefiner,
  interactive: InteractiveRefiner,
  game: GameRefiner,
  video: VideoRefiner,
  quiz: QuizRefiner,
};

const CATEGORY_LABELS = {
  worksheet: 'Worksheet',
  slides: 'Google Slides',
  forms: 'Google Form',
  interactive: 'Interactive Activity',
  game: 'Live Game',
  video: 'Video',
  quiz: 'Assessment / Quiz',
};

/**
 * Per-day refinement modal. Teacher confirms each work order's variant,
 * config, and accommodations before the plan can be generated.
 *
 * Props:
 *   day: { day, title, work_orders: [...] }
 *   subject: string — class subject for variant catalogs
 *   onSave: (updatedDay) => void
 *   onClose: () => void
 */
export default function RefineDayModal({ day, subject, onSave, onClose }) {
  const [workOrders, setWorkOrders] = useState(day.work_orders || []);
  const [expandedIdx, setExpandedIdx] = useState(0);

  function updateWorkOrder(i, updated) {
    const next = [...workOrders];
    next[i] = updated;
    setWorkOrders(next);
    // Auto-advance to next unconfirmed work order
    const nextUnconfirmed = next.findIndex((w, idx) => idx > i && !w.confirmed);
    if (nextUnconfirmed >= 0) setExpandedIdx(nextUnconfirmed);
  }

  const allConfirmed = workOrders.length > 0 && workOrders.every(w => w.confirmed);

  function handleSave() {
    onSave({ ...day, work_orders: workOrders });
  }

  const dayLabel = (day.day || '').toUpperCase();

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
          <div>
            <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
              {dayLabel} · Confirm Materials
            </h3>
            <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-light)' }}>
              {day.title}
            </p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-light)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Work order cards */}
        <div className="flex-1 overflow-y-auto p-5 space-y-2">
          {workOrders.length === 0 && (
            <p className="text-center py-8 text-[13px]" style={{ color: 'var(--text-light)' }}>
              No materials scheduled for this day.
            </p>
          )}

          {workOrders.map((wo, i) => {
            const category = categoryForTemplate(wo.output_template_id);
            const Refiner = REFINERS[category] || WorksheetRefiner;
            const isExpanded = expandedIdx === i;
            const confirmed = wo.confirmed;

            return (
              <div key={i} className="rounded-xl overflow-hidden"
                style={{ border: `1px solid ${confirmed ? 'var(--sage)' : 'var(--border)'}` }}>
                <button
                  onClick={() => setExpandedIdx(isExpanded ? -1 : i)}
                  className="w-full flex items-center justify-between p-3 text-left"
                  style={{
                    background: confirmed ? 'rgba(107,160,138,0.08)' : 'var(--cream)',
                    border: 'none', cursor: 'pointer',
                  }}
                >
                  <div className="flex items-center gap-2">
                    {confirmed
                      ? <CheckCircle className="w-4 h-4" style={{ color: 'var(--sage)' }} />
                      : <AlertCircle className="w-4 h-4" style={{ color: '#F59E0B' }} />}
                    {isExpanded
                      ? <ChevronDown className="w-4 h-4" style={{ color: 'var(--text-light)' }} />
                      : <ChevronRight className="w-4 h-4" style={{ color: 'var(--text-light)' }} />}
                    <span className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
                      {CATEGORY_LABELS[category]}
                    </span>
                    {wo.variant && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
                        style={{ background: 'var(--warm-card)', color: 'var(--text-mid)', border: '1px solid var(--border)' }}>
                        {wo.variant}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {(wo.accommodations || []).length > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                        style={{ background: 'rgba(59,130,246,0.1)', color: '#3B82F6', fontWeight: 600 }}>
                        +{wo.accommodations.length} accom
                      </span>
                    )}
                    <span className="text-[11px] font-bold"
                      style={{ color: confirmed ? 'var(--sage)' : '#F59E0B' }}>
                      {confirmed ? 'Confirmed' : 'Needs review'}
                    </span>
                  </div>
                </button>

                {isExpanded && (
                  <div className="p-4" style={{ background: 'var(--warm-card)' }}>
                    <Refiner
                      workOrder={wo}
                      subject={subject}
                      dayTitle={day.title}
                      onConfirm={(updated) => updateWorkOrder(i, updated)}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-5 flex items-center justify-between" style={{ borderTop: '1px solid var(--border)' }}>
          <span className="text-[12px] font-semibold" style={{ color: 'var(--text-mid)' }}>
            {workOrders.filter(w => w.confirmed).length} / {workOrders.length} confirmed
          </span>
          <div className="flex gap-2">
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold"
              style={{ color: 'var(--text-mid)', border: '1px solid var(--border)', background: 'var(--warm-card)' }}>
              Cancel
            </button>
            <button onClick={handleSave} disabled={!allConfirmed}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white disabled:opacity-50"
              style={{ background: 'var(--sage)' }}>
              Save Day
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
