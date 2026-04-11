'use client';
import { useState } from 'react';
import { ClassProvider, useClassContext } from './ClassContext';
import ClassTabBar from './ClassTabBar';
import ClassFormModal from './ClassFormModal';
import Image from 'next/image';
import { Plus } from 'lucide-react';

function AppShellInner({ children }) {
  const { classes, activeClassId, loading, createClass, updateClass, archiveClass } = useClassContext();
  const [showModal, setShowModal] = useState(false);
  const [editClass, setEditClass] = useState(null);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(null);

  function handleEditClick(classId, action) {
    if (action === 'archive') {
      const cls = classes.find(c => c.class_id === classId);
      setShowArchiveConfirm(cls);
    } else {
      const cls = classes.find(c => c.class_id === classId);
      setEditClass(cls);
      setShowModal(true);
    }
  }

  async function handleArchiveConfirm() {
    if (showArchiveConfirm) {
      await archiveClass(showArchiveConfirm.class_id);
      setShowArchiveConfirm(null);
    }
  }

  return (
    <>
      {/* Class Tab Bar */}
      {!loading && classes.length > 0 && (
        <ClassTabBar
          onCreateClick={() => { setEditClass(null); setShowModal(true); }}
          onEditClick={handleEditClick}
        />
      )}

      {/* Empty state when no classes */}
      {!loading && classes.length === 0 && (
        <div style={{
          background: 'var(--warm-card)', borderBottom: '1px solid var(--border)',
          padding: '24px 16px', textAlign: 'center',
        }}>
          <Image src="/icons/graduation.png" alt="" width={48} height={48} style={{ margin: '0 auto 8px' }} />
          <h2 className="font-serif" style={{ fontSize: 18, color: 'var(--text-dark)', marginBottom: 4 }}>
            Welcome to Lulia Lesson Lab
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-mid)', maxWidth: 480, margin: '0 auto 16px', lineHeight: 1.5 }}>
            Create your first class to get started. Each class keeps its own standards, curriculum, and materials separate so Lulia&apos;s AI stays focused on the right grade and subject.
          </p>
          <button onClick={() => { setEditClass(null); setShowModal(true); }}
            style={{
              padding: '10px 24px', borderRadius: 10, border: 'none',
              background: 'var(--coral)', color: 'white', cursor: 'pointer',
              fontSize: 14, fontWeight: 600,
              display: 'inline-flex', alignItems: 'center', gap: 8,
            }}>
            <Plus style={{ width: 16, height: 16 }} /> Create your first class
          </button>
        </div>
      )}

      {/* Main content */}
      <div className="p-6">
        {children}
      </div>

      {/* Create/Edit modal */}
      {showModal && (
        <ClassFormModal
          existingClass={editClass}
          onSubmit={editClass
            ? (payload) => updateClass(editClass.class_id, payload)
            : (payload) => createClass(payload)
          }
          onClose={() => { setShowModal(false); setEditClass(null); }}
        />
      )}

      {/* Archive confirmation */}
      {showArchiveConfirm && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }} onClick={() => setShowArchiveConfirm(null)}>
          <div style={{
            background: 'var(--warm-card)', borderRadius: 16, width: '100%', maxWidth: 380,
            padding: 24, boxShadow: '0 8px 32px rgba(60,40,20,0.15)', margin: '0 16px',
          }} onClick={e => e.stopPropagation()}>
            <h3 className="font-serif" style={{ fontSize: 18, color: 'var(--text-dark)', marginBottom: 8 }}>
              Archive {showArchiveConfirm.name}?
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text-mid)', lineHeight: 1.5, marginBottom: 20 }}>
              Its materials and lesson plans will be preserved but hidden from your active tabs. You can restore it later from Settings.
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setShowArchiveConfirm(null)}
                style={{ flex: 1, padding: '10px 0', borderRadius: 10, border: '1px solid var(--border)', background: 'var(--warm-card)', cursor: 'pointer', fontSize: 13, color: 'var(--text-mid)' }}>
                Cancel
              </button>
              <button onClick={handleArchiveConfirm}
                style={{ flex: 1, padding: '10px 0', borderRadius: 10, border: 'none', background: '#EF4444', color: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                Archive
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function AppShell({ children }) {
  return (
    <ClassProvider>
      <AppShellInner>{children}</AppShellInner>
    </ClassProvider>
  );
}
