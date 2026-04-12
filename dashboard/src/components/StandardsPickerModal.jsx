'use client';

import { useState, useEffect, useMemo } from 'react';
import { X, Search, Loader2, ChevronDown, ChevronRight } from 'lucide-react';
import { apiFetch } from '@/lib/api';

/**
 * Modal that shows state standards organized by domain.
 * Teacher selects specific standards to focus on.
 *
 * Props:
 *   subject: string — class subject (e.g., "Mathematics")
 *   gradeLevel: string — class grade (e.g., "4")
 *   stateCode: string — teacher's state (e.g., "OH")
 *   initialSelected: string[] — pre-selected standard codes
 *   onConfirm: (codes: string[]) => void — called with selected codes
 *   onClose: () => void
 */
export default function StandardsPickerModal({
  subject, gradeLevel, stateCode, initialSelected = [], onConfirm, onClose,
}) {
  const [loading, setLoading] = useState(true);
  const [standards, setStandards] = useState([]);
  const [selected, setSelected] = useState(new Set(initialSelected));
  const [search, setSearch] = useState('');
  const [expandedDomains, setExpandedDomains] = useState(new Set());

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (subject) params.set('subject', subject);
    if (gradeLevel) params.set('grade', gradeLevel);
    if (stateCode) params.set('state_code', stateCode);
    params.set('limit', '500');

    apiFetch(`/api/v1/standards?${params.toString()}`)
      .then(data => {
        // Filter out domain-level entries that don't have real descriptions
        // (imported as [0] codes with just the domain name as description)
        const filtered = (data.standards || []).filter(s => {
          const desc = s.description || '';
          const domain = s.domain || '';
          // Keep standards where description is more than just the domain name
          // and has meaningful content (> 30 chars)
          if (desc === domain) return false;
          if (desc.length < 25 && !s.code?.match(/\w+\.\w+/)) return false;
          return true;
        });
        setStandards(filtered);
        // Auto-expand first 3 domains
        const domains = [...new Set(filtered.map(s => s.domain).filter(Boolean))];
        setExpandedDomains(new Set(domains.slice(0, 3)));
      })
      .catch(() => setStandards([]))
      .finally(() => setLoading(false));
  }, [subject, gradeLevel, stateCode]);

  // Group standards by domain
  const grouped = useMemo(() => {
    const groups = {};
    for (const std of standards) {
      const domain = std.domain || 'Other';
      if (!groups[domain]) groups[domain] = [];
      groups[domain].push(std);
    }
    return groups;
  }, [standards]);

  // Filter by search
  const filteredGroups = useMemo(() => {
    if (!search.trim()) return grouped;
    const q = search.toLowerCase();
    const result = {};
    for (const [domain, stds] of Object.entries(grouped)) {
      const matches = stds.filter(s =>
        s.code?.toLowerCase().includes(q) ||
        s.description?.toLowerCase().includes(q) ||
        domain.toLowerCase().includes(q)
      );
      if (matches.length > 0) result[domain] = matches;
    }
    return result;
  }, [grouped, search]);

  function toggleStandard(code) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function toggleDomain(domain) {
    setExpandedDomains(prev => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  }

  function selectAllInDomain(domain, stds) {
    setSelected(prev => {
      const next = new Set(prev);
      const allSelected = stds.every(s => next.has(s.code));
      if (allSelected) {
        stds.forEach(s => next.delete(s.code));
      } else {
        stds.forEach(s => next.add(s.code));
      }
      return next;
    });
  }

  function handleConfirm() {
    onConfirm([...selected]);
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="rounded-card w-full max-w-2xl mx-4 max-h-[85vh] overflow-hidden flex flex-col"
        style={{ background: 'var(--warm-card)', boxShadow: '0 8px 32px rgba(60,40,20,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-serif text-[20px]" style={{ color: 'var(--text-dark)' }}>
                Select Standards
              </h3>
              <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-light)' }}>
                {[gradeLevel && `Grade ${gradeLevel}`, subject, stateCode].filter(Boolean).join(' · ')}
              </p>
            </div>
            <button onClick={onClose} style={{ color: 'var(--text-light)' }}>
              <X className="w-5 h-5" />
            </button>
          </div>
          {/* Search bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-light)' }} />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by standard code, keyword, or topic..."
              className="w-full pl-9 pr-3 py-2 rounded-xl text-[13px]"
              style={{ border: '1px solid var(--border)', background: 'white', color: 'var(--text-dark)' }}
            />
          </div>
        </div>

        {/* Standards list */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin" style={{ color: 'var(--coral)' }} />
            </div>
          )}

          {!loading && Object.keys(filteredGroups).length === 0 && (
            <div className="text-center py-8">
              <p className="text-[14px]" style={{ color: 'var(--text-mid)' }}>
                {search ? 'No standards match your search.' : 'No standards found for this class.'}
              </p>
            </div>
          )}

          {!loading && Object.entries(filteredGroups).map(([domain, stds]) => {
            const isExpanded = expandedDomains.has(domain);
            const selectedInDomain = stds.filter(s => selected.has(s.code)).length;

            return (
              <div key={domain} className="mb-3">
                {/* Domain header */}
                <button
                  onClick={() => toggleDomain(domain)}
                  className="w-full flex items-center justify-between p-3 rounded-xl text-left transition-colors"
                  style={{
                    background: selectedInDomain > 0 ? 'rgba(107,160,138,0.08)' : 'var(--cream)',
                    border: 'none', cursor: 'pointer',
                  }}
                >
                  <div className="flex items-center gap-2">
                    {isExpanded
                      ? <ChevronDown className="w-4 h-4" style={{ color: 'var(--text-light)' }} />
                      : <ChevronRight className="w-4 h-4" style={{ color: 'var(--text-light)' }} />
                    }
                    <span className="text-[13px] font-bold" style={{ color: 'var(--text-dark)' }}>
                      {domain}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedInDomain > 0 && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                        style={{ background: 'rgba(107,160,138,0.15)', color: 'var(--sage)' }}>
                        {selectedInDomain} selected
                      </span>
                    )}
                    <span className="text-[11px]" style={{ color: 'var(--text-light)' }}>
                      {stds.length} standards
                    </span>
                  </div>
                </button>

                {/* Standards in this domain */}
                {isExpanded && (
                  <div className="ml-6 mt-1 space-y-1">
                    {/* Select all toggle */}
                    <button
                      onClick={() => selectAllInDomain(domain, stds)}
                      className="text-[11px] font-semibold mb-1"
                      style={{ color: 'var(--sage)', background: 'none', border: 'none', cursor: 'pointer' }}
                    >
                      {stds.every(s => selected.has(s.code)) ? 'Deselect all' : 'Select all'}
                    </button>

                    {stds.map(std => {
                      const isSelected = selected.has(std.code);
                      return (
                        <label
                          key={std.standard_id || std.code}
                          className="flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors"
                          style={{ background: isSelected ? 'rgba(216,108,82,0.05)' : 'transparent' }}
                          onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--cream)'; }}
                          onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleStandard(std.code)}
                            className="mt-0.5 rounded"
                            style={{ accentColor: 'var(--coral)' }}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-0.5">
                              {std.code && !std.code.match(/^\[?\d+\]?$/) && (
                                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded flex-shrink-0"
                                  style={{
                                    background: isSelected ? 'rgba(216,108,82,0.12)' : 'var(--cream)',
                                    color: isSelected ? 'var(--coral)' : 'var(--text-mid)',
                                  }}>
                                  {std.code}
                                </span>
                              )}
                              {std.cluster && (
                                <span className="text-[10px]" style={{ color: 'var(--text-light)' }}>
                                  {std.cluster}
                                </span>
                              )}
                            </div>
                            <p className="text-[12px]" style={{ color: 'var(--text-dark)' }}>
                              {std.description}
                            </p>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-5 flex items-center justify-between" style={{ borderTop: '1px solid var(--border)' }}>
          <span className="text-[13px] font-semibold" style={{ color: 'var(--text-mid)' }}>
            {selected.size} standard{selected.size !== 1 ? 's' : ''} selected
          </span>
          <div className="flex gap-3">
            <button onClick={onClose}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold"
              style={{ color: 'var(--text-mid)', border: '1px solid var(--border)' }}>
              Cancel
            </button>
            <button onClick={handleConfirm}
              disabled={selected.size === 0}
              className="px-4 py-2 rounded-xl text-[13px] font-semibold text-white disabled:opacity-50"
              style={{ background: 'var(--coral)' }}>
              Confirm Selection
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
