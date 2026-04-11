'use client';
import { useState, useRef, useEffect } from 'react';
import { Beaker, Globe, BookOpen, Calculator, GraduationCap, Music, Paintbrush, Heart, Plus, ChevronDown, MoreVertical } from 'lucide-react';
import { useClassContext } from './ClassContext';

// Subject → icon mapping
const SUBJECT_ICONS = {
  Science: Beaker,
  'Social Studies': Globe,
  History: Globe,
  ELA: BookOpen,
  'English Language Arts': BookOpen,
  English: BookOpen,
  Math: Calculator,
  Mathematics: Calculator,
  Music: Music,
  Art: Paintbrush,
  'Fine Arts': Paintbrush,
  PE: Heart,
  'Health & PE': Heart,
};

function getSubjectIcon(subject) {
  return SUBJECT_ICONS[subject] || GraduationCap;
}

export default function ClassTabBar({ onCreateClick, onEditClick }) {
  const { classes, activeClassId, setActiveClassId, loading } = useClassContext();
  const [contextMenu, setContextMenu] = useState(null); // { classId, x, y }
  const [mobileOpen, setMobileOpen] = useState(false);
  const scrollRef = useRef(null);
  const menuRef = useRef(null);

  // Close context menu on outside click
  useEffect(() => {
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setContextMenu(null);
    }
    if (contextMenu) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [contextMenu]);

  if (loading || classes.length === 0) return null;

  function handleContextMenu(e, classId) {
    e.preventDefault();
    setContextMenu({ classId, x: e.clientX, y: e.clientY });
  }

  // ── Mobile dropdown ──────────────────────────────────────
  const activeClass = classes.find(c => c.class_id === activeClassId);
  const ActiveIcon = activeClass ? getSubjectIcon(activeClass.subject) : GraduationCap;

  return (
    <>
      {/* Desktop tab bar */}
      <div className="hidden sm:block" style={{
        background: 'var(--warm-card)', borderBottom: '1px solid var(--border)',
        position: 'sticky', top: 0, zIndex: 20,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center',
          overflowX: 'auto', scrollSnapType: 'x mandatory',
          scrollbarWidth: 'none', msOverflowStyle: 'none',
          paddingLeft: 8, paddingRight: 8,
        }} ref={scrollRef} className="hide-scrollbar">
          {classes.map(cls => {
            const Icon = getSubjectIcon(cls.subject);
            const isActive = cls.class_id === activeClassId;
            return (
              <button
                key={cls.class_id}
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveClassId(cls.class_id)}
                onContextMenu={e => handleContextMenu(e, cls.class_id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '10px 14px', border: 'none', background: 'transparent',
                  cursor: 'pointer', whiteSpace: 'nowrap', scrollSnapAlign: 'start',
                  borderBottom: isActive ? '2px solid var(--coral)' : '2px solid transparent',
                  color: isActive ? 'var(--text-dark)' : 'var(--text-light)',
                  fontWeight: isActive ? 600 : 400,
                  fontFamily: "'Nunito', sans-serif", fontSize: 13,
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-mid)'; }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-light)'; }}
              >
                <Icon style={{ width: 15, height: 15, flexShrink: 0 }} />
                <span>{cls.name}</span>
                <span style={{
                  fontSize: 9, fontWeight: 600, padding: '1px 5px', borderRadius: 4,
                  background: isActive ? 'var(--cream)' : 'var(--border)',
                  color: isActive ? 'var(--coral)' : 'var(--text-light)',
                }}>{cls.grade_level}</span>
              </button>
            );
          })}
          {/* Add class button */}
          <button
            onClick={onCreateClick}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '10px 12px', border: 'none', background: 'transparent',
              cursor: 'pointer', color: 'var(--text-light)', fontSize: 12,
              fontFamily: "'Nunito', sans-serif", whiteSpace: 'nowrap',
              borderBottom: '2px solid transparent',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--coral)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text-light)'}
            title="Add a class"
          >
            <Plus style={{ width: 14, height: 14 }} />
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      <div className="sm:hidden" style={{
        background: 'var(--warm-card)', borderBottom: '1px solid var(--border)',
        position: 'sticky', top: 0, zIndex: 20,
        padding: '6px 12px',
      }}>
        <button onClick={() => setMobileOpen(!mobileOpen)} style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 12px', borderRadius: 10, border: '1px solid var(--border)',
          background: 'var(--warm-card)', cursor: 'pointer', fontFamily: "'Nunito', sans-serif",
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-dark)', fontWeight: 600 }}>
            <ActiveIcon style={{ width: 16, height: 16 }} />
            {activeClass?.name || 'Select a class'}
            <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: 'var(--cream)', color: 'var(--coral)', fontWeight: 600 }}>
              {activeClass?.grade_level}
            </span>
          </span>
          <ChevronDown style={{ width: 16, height: 16, color: 'var(--text-light)', transform: mobileOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
        </button>

        {mobileOpen && (
          <div style={{
            position: 'absolute', left: 12, right: 12, top: '100%',
            background: 'var(--warm-card)', borderRadius: 12, border: '1px solid var(--border)',
            boxShadow: '0 4px 16px rgba(0,0,0,0.1)', zIndex: 30,
            overflow: 'hidden', marginTop: 4,
          }}>
            {classes.map(cls => {
              const Icon = getSubjectIcon(cls.subject);
              const isActive = cls.class_id === activeClassId;
              return (
                <button key={cls.class_id} onClick={() => { setActiveClassId(cls.class_id); setMobileOpen(false); }}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 14px', border: 'none', borderBottom: '1px solid var(--border)',
                    background: isActive ? 'var(--cream)' : 'white', cursor: 'pointer',
                    fontFamily: "'Nunito', sans-serif", fontSize: 13,
                    color: isActive ? 'var(--text-dark)' : 'var(--text-dark)',
                  }}>
                  <Icon style={{ width: 15, height: 15, color: isActive ? 'var(--coral)' : 'var(--text-light)' }} />
                  {cls.name}
                  <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: isActive ? 'var(--coral)' : 'var(--border)', color: isActive ? 'white' : 'var(--text-light)', fontWeight: 600, marginLeft: 'auto' }}>
                    {cls.grade_level}
                  </span>
                </button>
              );
            })}
            <button onClick={() => { onCreateClick?.(); setMobileOpen(false); }}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center',
                padding: '10px 14px', border: 'none', background: 'var(--cream)',
                cursor: 'pointer', fontFamily: "'Nunito', sans-serif", fontSize: 12,
                color: 'var(--coral)', fontWeight: 600,
              }}>
              <Plus style={{ width: 14, height: 14 }} /> New Class
            </button>
          </div>
        )}
      </div>

      {/* Context menu (desktop right-click) */}
      {contextMenu && (
        <div ref={menuRef} style={{
          position: 'fixed', left: contextMenu.x, top: contextMenu.y,
          background: 'var(--warm-card)', borderRadius: 10, border: '1px solid var(--border)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)', zIndex: 50,
          overflow: 'hidden', minWidth: 140,
        }}>
          {[
            { label: 'Edit details', action: () => { onEditClick?.(contextMenu.classId); setContextMenu(null); } },
            { label: 'Archive', action: () => { /* handled by parent */ onEditClick?.(contextMenu.classId, 'archive'); setContextMenu(null); } },
          ].map(item => (
            <button key={item.label} onClick={item.action}
              style={{
                width: '100%', padding: '8px 14px', border: 'none', background: 'var(--warm-card)',
                cursor: 'pointer', textAlign: 'left', fontSize: 12,
                fontFamily: "'Nunito', sans-serif", color: item.label === 'Archive' ? '#EF4444' : 'var(--text-dark)',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--cream)'}
              onMouseLeave={e => e.currentTarget.style.background = 'white'}>
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* Hide scrollbar CSS */}
      <style jsx global>{`
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { scrollbar-width: none; }
      `}</style>
    </>
  );
}
