'use client';
import { useState, useEffect } from 'react';
import { X, Loader2 } from 'lucide-react';

const GRADES = ['K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'];
const SUBJECTS = ['Mathematics', 'Science', 'English Language Arts', 'Social Studies', 'History', 'Art', 'Music', 'PE', 'World Languages', 'CTE / Electives', 'Other'];

export default function ClassFormModal({ existingClass, onSubmit, onClose }) {
  const [name, setName] = useState('');
  const [gradeLevel, setGradeLevel] = useState('4');
  const [subject, setSubject] = useState('Mathematics');
  const [customSubject, setCustomSubject] = useState('');
  const [period, setPeriod] = useState('');
  const [schoolYear, setSchoolYear] = useState('2026-2027');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const isEdit = !!existingClass;

  useEffect(() => {
    if (existingClass) {
      setName(existingClass.name || '');
      setGradeLevel(existingClass.grade_level || '4');
      const subj = existingClass.subject || 'Mathematics';
      if (SUBJECTS.includes(subj)) {
        setSubject(subj);
      } else {
        setSubject('Other');
        setCustomSubject(subj);
      }
      setPeriod(existingClass.period || '');
      setSchoolYear(existingClass.school_year || '2026-2027');
    }
  }, [existingClass]);

  // Auto-generate name from grade + subject
  useEffect(() => {
    if (!isEdit && !name.includes('Grade') && subject !== 'Other') {
      const grade = gradeLevel === 'K' ? 'Kindergarten' : `${gradeLevel}th Grade`;
      setName(`${grade} ${subject}`);
    }
  }, [gradeLevel, subject]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const finalSubject = subject === 'Other' ? customSubject : subject;
      await onSubmit({
        name: name.trim(),
        grade_level: gradeLevel,
        subject: finalSubject,
        period: period.trim() || null,
        school_year: schoolYear,
      });
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }} onClick={onClose}>
      <div style={{
        background: 'white', borderRadius: 16, width: '100%', maxWidth: 440,
        padding: 24, boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
        margin: '0 16px',
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 20, color: '#1C1917' }}>
            {isEdit ? 'Edit Class' : 'Create a Class'}
          </h2>
          <button onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#A8A29E', padding: 4 }}>
            <X style={{ width: 20, height: 20 }} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Grade + Subject row */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Grade Level</label>
              <select value={gradeLevel} onChange={e => setGradeLevel(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }}>
                {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
              </select>
            </div>
            <div style={{ flex: 2 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Subject</label>
              <select value={subject} onChange={e => setSubject(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }}>
                {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Custom subject */}
          {subject === 'Other' && (
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Custom Subject</label>
              <input value={customSubject} onChange={e => setCustomSubject(e.target.value)} placeholder="e.g., Computer Science"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }} />
            </div>
          )}

          {/* Class name */}
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Class Name</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g., 5th Grade Science - Period 3" required
              style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }} />
          </div>

          {/* Period + School Year row */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Period (optional)</label>
              <input value={period} onChange={e => setPeriod(e.target.value)} placeholder="e.g., 3rd"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>School Year</label>
              <input value={schoolYear} onChange={e => setSchoolYear(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 10, border: '1px solid #E7E5E4', fontSize: 13, fontFamily: "'DM Sans'", outline: 'none' }} />
            </div>
          </div>

          {/* Error */}
          {error && <div style={{ fontSize: 12, color: '#EF4444', marginBottom: 12, padding: '8px 12px', background: '#FEF2F2', borderRadius: 8 }}>{error}</div>}

          {/* Buttons */}
          <div style={{ display: 'flex', gap: 10 }}>
            <button type="button" onClick={onClose}
              style={{ flex: 1, padding: '10px 0', borderRadius: 10, border: '1px solid #E7E5E4', background: 'white', cursor: 'pointer', fontSize: 13, fontFamily: "'DM Sans'", color: '#78716C' }}>
              Cancel
            </button>
            <button type="submit" disabled={saving || !name.trim()}
              style={{ flex: 2, padding: '10px 0', borderRadius: 10, border: 'none', background: saving ? '#FDBA74' : '#F97316', color: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: "'DM Sans'", display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              {saving && <Loader2 style={{ width: 14, height: 14 }} className="animate-spin" />}
              {isEdit ? 'Save Changes' : 'Create Class'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
