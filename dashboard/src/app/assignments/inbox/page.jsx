'use client';
import { useEffect, useState } from 'react';
import { Inbox, CheckCircle, AlertTriangle, Clock } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export default function GradingInbox() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    apiFetch('/api/v1/manager/grading-inbox')
      .then(d => setItems(d.items || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter === 'all' ? items :
    filter === 'review' ? items.filter(i => i.status === 'needs_review') :
    items;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold" style={{ fontFamily: "'DM Serif Display', serif", color: '#1C1917' }}>
            Grading Inbox <span className="text-orange-500">({items.length})</span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">Everything that needs your attention</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        {[
          { id: 'all', label: 'All' },
          { id: 'review', label: 'Needs Review' },
        ].map(f => (
          <button key={f.id} onClick={() => setFilter(f.id)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f.id ? 'bg-orange-500 text-white' : 'bg-white text-gray-600 border border-gray-200'
            }`}>
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="animate-pulse space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-white/50 rounded-[14px]" />)}</div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-[14px] p-12 text-center" style={{ border: '1px solid #E7E5E4' }}>
          <CheckCircle className="w-12 h-12 text-green-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium" style={{ fontFamily: "'DM Serif Display', serif" }}>All caught up!</h3>
          <p className="text-sm text-gray-500">No items need grading right now</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((item, i) => (
            <div key={item.submission_id || i} className="bg-white rounded-[14px] p-4 flex items-center justify-between" style={{ border: '1px solid #E7E5E4' }}>
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  item.status === 'needs_review' ? 'bg-amber-50' : 'bg-blue-50'
                }`}>
                  {item.status === 'needs_review' ? <AlertTriangle className="w-4 h-4 text-amber-500" /> : <Clock className="w-4 h-4 text-blue-500" />}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-800">{item.student_name || 'Unknown Student'}</p>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>{item.assignment_title || 'Assignment'}</span>
                    <span>·</span>
                    <span className="uppercase">{item.item_type || item.submission_method}</span>
                    {item.class_name && <><span>·</span><span>{item.class_name}</span></>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {item.percentage != null && (
                  <span className="text-sm font-semibold text-orange-500">{item.percentage}%</span>
                )}
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                  item.status === 'needs_review' ? 'bg-amber-50 text-amber-700' : 'bg-blue-50 text-blue-700'
                }`}>{item.status}</span>
                <span className="text-xs text-gray-400">{item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
