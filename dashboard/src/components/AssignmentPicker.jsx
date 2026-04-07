'use client';
import { useEffect, useState } from 'react';
import { Search, FileText } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function AssignmentPicker({ onSelect, selected }) {
  const [assignments, setAssignments] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const q = search ? `&search=${encodeURIComponent(search)}` : '';
    apiFetch(`/api/v1/assistant/assignments?limit=15${q}`)
      .then(d => setAssignments(d.assignments || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [search]);

  return (
    <div>
      <div className="relative mb-3">
        <Search className="w-4 h-4 absolute left-3 top-2.5" style={{ color: '#A8A29E' }} />
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search your assignments..."
          className="w-full pl-9 pr-4 py-2 rounded-xl text-sm outline-none"
          style={{ border: '1px solid #E7E5E4', fontFamily: "'DM Sans'" }}
        />
      </div>
      <div style={{ maxHeight: 280, overflowY: 'auto' }} className="space-y-1.5">
        {loading ? (
          [1,2,3].map(i => <div key={i} className="h-14 rounded-xl animate-pulse" style={{ background: '#F5F5F4' }} />)
        ) : assignments.length === 0 ? (
          <div className="text-center py-6">
            <FileText className="w-8 h-8 mx-auto mb-2" style={{ color: '#E7E5E4' }} />
            <p className="text-sm" style={{ color: '#A8A29E' }}>{search ? 'No matches' : 'No assignments yet'}</p>
          </div>
        ) : assignments.map(a => (
          <button
            key={a.assignment_id}
            onClick={() => onSelect(a)}
            className="w-full text-left p-3 rounded-xl transition-colors"
            style={{
              border: selected === a.assignment_id ? '2px solid #F97316' : '1px solid #E7E5E4',
              background: selected === a.assignment_id ? '#FFF7ED' : 'white',
            }}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium" style={{ color: '#1C1917' }}>{a.title}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: '#FFF7ED', color: '#9A3412' }}>{a.output_template_id}</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              {a.class_name && <span className="text-[10px]" style={{ color: '#A8A29E' }}>{a.class_name}</span>}
              {a.subject && <span className="text-[10px]" style={{ color: '#A8A29E' }}>• {a.subject}</span>}
              {a.question_count && <span className="text-[10px]" style={{ color: '#A8A29E' }}>• {a.question_count}q</span>}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
