'use client';
import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

const CATEGORY_LABELS = {
  book_buddies: 'Book Buddies',
  pencil_pals: 'Pencil Pals',
  math_monsters: 'Math Monsters',
  science_sprites: 'Science Sprites',
  nature_friends: 'Nature Friends',
  lab_critters: 'Lab Critters',
};

// Fallback emoji avatars used when Lulings aren't generated yet
const FALLBACK_AVATARS = [
  { luling_id: 'emoji_bear', name: 'Bear', category: 'fallback', thumbnail_url: null, emoji: '🐻' },
  { luling_id: 'emoji_fox', name: 'Fox', category: 'fallback', thumbnail_url: null, emoji: '🦊' },
  { luling_id: 'emoji_cat', name: 'Cat', category: 'fallback', thumbnail_url: null, emoji: '🐱' },
  { luling_id: 'emoji_dog', name: 'Dog', category: 'fallback', thumbnail_url: null, emoji: '🐶' },
  { luling_id: 'emoji_lion', name: 'Lion', category: 'fallback', thumbnail_url: null, emoji: '🦁' },
  { luling_id: 'emoji_panda', name: 'Panda', category: 'fallback', thumbnail_url: null, emoji: '🐼' },
  { luling_id: 'emoji_unicorn', name: 'Unicorn', category: 'fallback', thumbnail_url: null, emoji: '🦄' },
  { luling_id: 'emoji_frog', name: 'Frog', category: 'fallback', thumbnail_url: null, emoji: '🐸' },
  { luling_id: 'emoji_octopus', name: 'Octopus', category: 'fallback', thumbnail_url: null, emoji: '🐙' },
  { luling_id: 'emoji_butterfly', name: 'Butterfly', category: 'fallback', thumbnail_url: null, emoji: '🦋' },
  { luling_id: 'emoji_owl', name: 'Owl', category: 'fallback', thumbnail_url: null, emoji: '🦉' },
  { luling_id: 'emoji_star', name: 'Star', category: 'fallback', thumbnail_url: null, emoji: '🌟' },
];

export default function LulingSelector({ onSelect, selected, showCategories = true }) {
  const [lulings, setLulings] = useState([]);
  const [categories, setCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch('/api/v1/lulings').catch(() => ({ lulings: [] })),
      apiFetch('/api/v1/lulings/categories').catch(() => ({ categories: [] })),
    ]).then(([lData, cData]) => {
      const allLulings = lData.lulings?.length > 0 ? lData.lulings : FALLBACK_AVATARS;
      setLulings(allLulings);
      setCategories(cData.categories || []);
    }).finally(() => setLoading(false));
  }, []);

  const filtered = activeCategory === 'all'
    ? lulings
    : lulings.filter(l => l.category === activeCategory);

  return (
    <div>
      {/* Category tabs */}
      {showCategories && categories.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, overflowX: 'auto', paddingBottom: 4 }}>
          <button
            onClick={() => setActiveCategory('all')}
            style={{
              padding: '4px 12px', borderRadius: 8, fontSize: 11, fontWeight: 500, cursor: 'pointer', border: 'none',
              background: activeCategory === 'all' ? '#F97316' : 'white', color: activeCategory === 'all' ? 'white' : '#78716C',
              whiteSpace: 'nowrap', fontFamily: "'DM Sans'",
            }}
          >All</button>
          {categories.map(c => (
            <button
              key={c.category}
              onClick={() => setActiveCategory(c.category)}
              style={{
                padding: '4px 12px', borderRadius: 8, fontSize: 11, fontWeight: 500, cursor: 'pointer', border: 'none',
                background: activeCategory === c.category ? '#F97316' : 'white', color: activeCategory === c.category ? 'white' : '#78716C',
                whiteSpace: 'nowrap', fontFamily: "'DM Sans'",
              }}
            >{CATEGORY_LABELS[c.category] || c.category} ({c.count})</button>
          ))}
        </div>
      )}

      {/* Luling grid */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          {[1,2,3,4,5,6,7,8].map(i => (
            <div key={i} style={{ width: '100%', aspectRatio: '1', background: '#E7E5E4', borderRadius: 12, animation: 'pulse 1.5s infinite' }} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, maxHeight: 280, overflowY: 'auto' }}>
          {filtered.map(l => {
            const isSelected = selected === l.luling_id || selected === l.name;
            return (
              <button
                key={l.luling_id}
                onClick={() => onSelect(l)}
                title={l.name}
                style={{
                  padding: 8, borderRadius: 12, cursor: 'pointer', textAlign: 'center',
                  border: isSelected ? '3px solid #F97316' : '2px solid transparent',
                  background: isSelected ? '#FFF7ED' : 'white',
                  transition: 'all 0.15s',
                }}
              >
                {l.thumbnail_url ? (
                  <img src={l.thumbnail_url} alt={l.name} style={{ width: '100%', aspectRatio: '1', borderRadius: 8, objectFit: 'cover' }} />
                ) : (
                  <div style={{ fontSize: 32, lineHeight: '48px' }}>{l.emoji || '🎯'}</div>
                )}
                <div style={{ fontSize: 9, color: '#78716C', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.name}</div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
