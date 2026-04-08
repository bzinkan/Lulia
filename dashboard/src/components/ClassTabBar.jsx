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
        background: 'white', borderBottom: '1px solid #E7E5E4',
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
                  borderBottom: isActive ? '2px solid #F97316' : '2px solid transparent',
                  color: isActive ? '#78350F' : '#A8A29E',
                  fontWeight: isActive ? 600 : 400,
                  fontFamily: "'DM Sans', sans-serif", fontSize: 13,
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = '#78716C'; }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = '#A8A29E'; }}
              >
                <Icon style={{ width: 15, height: 15, flexShrink: 0 }} />
                <span>{cls.name}</span>
                <span style={{
                  fontSize: 9, fontWeight: 600, padding: '1px 5px', borderRadius: 4,
                  background: isActive ? '#FFF7ED' : '#F5F5F4',
                  color: isActive ? '#F97316' : '#A8A29E',
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
              cursor: 'pointer', color: '#D6D3D1', fontSize: 12,
              fontFamily: "'DM Sans', sans-serif", whiteSpace: 'nowrap',
              borderBottom: '2px solid transparent',
            }}
            onMouseEnter={e => e.currentTarget.style.color = '#F97316'}
            onMouseLeave={e => e.currentTarget.style.color = '#D6D3D1'}
            title="Add a class"
          >
            <Plus style={{ width: 14, height: 14 }} />
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      <div className="sm:hidden" style={{
        background: 'white', borderBottom: '1px solid #E7E5E4',
        position: 'sticky', top: 0, zIndex: 20,
        padding: '6px 12px',
      }}>
        <button onClick={() => setMobileOpen(!mobileOpen)} style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 12px', borderRadius: 10, border: '1px solid #E7E5E4',
          background: 'white', cursor: 'pointer', fontFamily: "'DM Sans', sans-serif",
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#78350F', fontWeight: 600 }}>
            <ActiveIcon style={{ width: 16, height: 16 }} />
            {activeClass?.name || 'Select a class'}
            <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: '#FFF7ED', color: '#F97316', fontWeight: 600 }}>
              {activeClass?.grade_level}
            </span>
          </span>
          <ChevronDown style={{ width: 16, height: 16, color: '#A8A29E', transform: mobileOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
        </button>

        {mobileOpen && (
          <div style={{
            position: 'absolute', left: 12, right: 12, top: '100%',
            background: 'white', borderRadius: 12, border: '1px solid #E7E5E4',
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
                    padding: '10px 14px', border: 'none', borderBottom: '1px solid #F5F5F4',
                    background: isActive ? '#FFF7ED' : 'white', cursor: 'pointer',
                    fontFamily: "'DM Sans', sans-serif", fontSize: 13,
                    color: isActive ? '#78350F' : '#1C1917',
                  }}>
                  <Icon style={{ width: 15, height: 15, color: isActive ? '#F97316' : '#A8A29E' }} />
                  {cls.name}
                  <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: isActive ? '#F97316' : '#F5F5F4', color: isActive ? 'white' : '#A8A29E', fontWeight: 600, marginLeft: 'auto' }}>
                    {cls.grade_level}
                  </span>
                </button>
              );
            })}
            <button onClick={() => { onCreateClick?.(); setMobileOpen(false); }}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center',
                padding: '10px 14px', border: 'none', background: '#FFF7ED',
                cursor: 'pointer', fontFamily: "'DM Sans', sans-serif", fontSize: 12,
                color: '#F97316', fontWeight: 600,
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
          background: 'white', borderRadius: 10, border: '1px solid #E7E5E4',
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)', zIndex: 50,
          overflow: 'hidden', minWidth: 140,
        }}>
          {[
            { label: 'Edit details', action: () => { onEditClick?.(contextMenu.classId); setContextMenu(null); } },
            { label: 'Archive', action: () => { /* handled by parent */ onEditClick?.(contextMenu.classId, 'archive'); setContextMenu(null); } },
          ].map(item => (
            <button key={item.label} onClick={item.action}
              style={{
                width: '100%', padding: '8px 14px', border: 'none', background: 'white',
                cursor: 'pointer', textAlign: 'left', fontSize: 12,
                fontFamily: "'DM Sans', sans-serif", color: item.label === 'Archive' ? '#EF4444' : '#1C1917',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#FFF7ED'}
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
