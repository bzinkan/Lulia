'use client';
import { useState, useEffect, useMemo, useRef } from 'react';
import { Save, Eye, Sparkles, Undo2, Trash2, Copy, ChevronUp, ChevronDown, Loader2, Plus, AlertTriangle, Upload, Wand2, Search, X, BookOpen } from 'lucide-react';
// Note: Wand2 used by AI Suggest Standards, Search used by Standards search
import { apiFetch, apiUpload } from '@/lib/api';
import { RENDERERS } from '@/components/design/ComponentRenderers';
import { SpecialistEditor } from '@/components/design/ComponentEditors';

// ── Constants ──────────────────────────────────────────────────────────────────
const CATEGORIES = [
  'Mathematics', 'English Language Arts', 'Science', 'Social Studies',
  'World Languages', 'Fine Arts', 'Health & PE', 'CTE / Electives', 'General',
];
const GRADES = ['K','1','2','3','4','5','6','7','8','9','10','11','12'];
const ELEMENTARY_GRADES = new Set(['K','1','2','3','4','5']);

const THEME_PRESETS = [
  { id: 'modern_clean', name: 'Modern Clean', color: '#F97316' },
  { id: 'ocean_blue', name: 'Ocean Blue', color: '#2563EB' },
  { id: 'forest_green', name: 'Forest Green', color: '#059669' },
  { id: 'royal_purple', name: 'Royal Purple', color: '#7C3AED' },
  { id: 'playful_pink', name: 'Playful Pink', color: '#E11D48' },
  { id: 'sunshine', name: 'Sunshine', color: '#D97706' },
  { id: 'slate_pro', name: 'Slate Pro', color: '#475569' },
  { id: 'midnight', name: 'Midnight', color: '#1E293B' },
];

// Grade-level rendering adjustments
const GRADE_ADJUSTMENTS = {
  K:  { baseFontSize: 20, lineHeight: 2.0, mcColumns: 1, answerLines: 1 },
  1:  { baseFontSize: 18, lineHeight: 1.9, mcColumns: 1, answerLines: 1 },
  2:  { baseFontSize: 16, lineHeight: 1.8, mcColumns: 1, answerLines: 2 },
  3:  { baseFontSize: 15, lineHeight: 1.7, mcColumns: 2, answerLines: 2 },
  4:  { baseFontSize: 14, lineHeight: 1.6, mcColumns: 2, answerLines: 2 },
  5:  { baseFontSize: 14, lineHeight: 1.6, mcColumns: 2, answerLines: 3 },
  6:  { baseFontSize: 13, lineHeight: 1.5, mcColumns: 2, answerLines: 3 },
  7:  { baseFontSize: 13, lineHeight: 1.5, mcColumns: 2, answerLines: 3 },
  8:  { baseFontSize: 12, lineHeight: 1.5, mcColumns: 2, answerLines: 3 },
  9:  { baseFontSize: 12, lineHeight: 1.4, mcColumns: 2, answerLines: 4 },
  10: { baseFontSize: 12, lineHeight: 1.4, mcColumns: 2, answerLines: 4 },
  11: { baseFontSize: 11, lineHeight: 1.4, mcColumns: 2, answerLines: 4 },
  12: { baseFontSize: 11, lineHeight: 1.4, mcColumns: 2, answerLines: 4 },
};

// ── Tier 1: Universal components (always visible) ─────────────────────────────
const UNIVERSAL_TOOLBOX = [
  { group: 'Header', items: [
    { type: 'header', label: 'Title / Header', icon: '📝', defaults: { text: 'Untitled Worksheet', level: 'h1', alignment: 'center' } },
    { type: 'name_date_line', label: 'Name / Date Line', icon: '✏️', defaults: { fields: ['name', 'date'] } },
    { type: 'banner', label: 'Banner', icon: '🏷️', defaults: { text: 'Section Title', color: '#F97316' } },
  ]},
  { group: 'Questions', items: [
    { type: 'multiple_choice', label: 'Multiple Choice', icon: '🔘', defaults: { question: '', options: ['', '', '', ''], correct: 0, points: 1 } },
    { type: 'fill_in_blank', label: 'Fill in the Blank', icon: '___', defaults: { sentence: 'The ___ is the answer.' } },
    { type: 'short_answer', label: 'Short Answer', icon: '📝', defaults: { question: '', lines: 2 } },
    { type: 'long_answer', label: 'Long Answer', icon: '📄', defaults: { question: '', size: 'medium' } },
    { type: 'true_false', label: 'True / False', icon: '✓✗', defaults: { statement: '' } },
    { type: 'matching', label: 'Matching', icon: '🔗', defaults: { pairs: [{ left: '', right: '' }, { left: '', right: '' }] } },
  ]},
  { group: 'Content', items: [
    { type: 'instructions', label: 'Instructions', icon: '📋', defaults: { html: '<b>Directions:</b> Complete all problems.' } },
    { type: 'text_block', label: 'Text Block', icon: '¶', defaults: { text: '' } },
    { type: 'word_bank', label: 'Word Bank', icon: '📦', defaults: { words: [] } },
    { type: 'example', label: 'Example', icon: '💡', defaults: { text: '' } },
    { type: 'vocabulary', label: 'Vocabulary', icon: '📚', defaults: { term: '', definition: '' } },
  ]},
  { group: 'Visual', items: [
    { type: 'image', label: 'Image', icon: '🖼️', defaults: {} },
    { type: 'table', label: 'Table', icon: '📊', defaults: { rows: 3, cols: 3, showHeader: true } },
  ]},
  { group: 'Layout', items: [
    { type: 'divider', label: 'Divider', icon: '—', defaults: { label: '' } },
    { type: 'spacer', label: 'Spacer', icon: '↕', defaults: { size: 'medium' } },
    { type: 'answer_key', label: 'Answer Key', icon: '🔑', defaults: { auto_populate: true } },
  ]},
];

// Placeholder component item factory — for category/course components that don't have
// dedicated renderers yet. They render as a labeled placeholder on the canvas.
function makeToolItem(type) {
  const label = type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  return { type, label, icon: '🧩', defaults: { _placeholder: true, _label: label } };
}

// ── Helpers: resolve course from config ────────────────────────────────────────

/** Given a course name (e.g. "Algebra 2"), find the category and course key. */
function resolveProfileCourse(config, courseName) {
  if (!config?.categories || !courseName) return null;
  for (const [catName, catData] of Object.entries(config.categories)) {
    for (const [courseKey, courseData] of Object.entries(catData.courses || {})) {
      if (courseData.name === courseName) return { category: catName, course: courseKey };
    }
  }
  return null;
}

/** Get courses for a category filtered by grade. */
function getCoursesForGrade(config, category, grade) {
  const catData = config?.categories?.[category];
  if (!catData) return [];
  return Object.entries(catData.courses || {})
    .filter(([, data]) => data.grades.includes(grade))
    .map(([key, data]) => ({ key, name: data.name }));
}

/** Get first available course key for a category + grade combo. */
function getFirstCourse(config, category, grade) {
  const courses = getCoursesForGrade(config, category, grade);
  return courses.length > 0 ? courses[0].key : null;
}

/** Collect all component type IDs that belong to a given category (across all courses). */
function getAllCategoryComponentTypes(config, category) {
  const catData = config?.categories?.[category];
  if (!catData) return new Set();
  const types = new Set(catData.category_components || []);
  for (const courseData of Object.values(catData.courses || {})) {
    for (const c of courseData.components || []) types.add(c);
  }
  return types;
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function DesignStudio() {
  const [docName, setDocName] = useState('Untitled Worksheet');
  const [components, setComponents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [theme, setTheme] = useState('modern_clean');
  const [primaryColor, setPrimaryColor] = useState('#F97316');
  const [previewHtml, setPreviewHtml] = useState(null);
  const [saving, setSaving] = useState(false);
  const [filling, setFilling] = useState(false);
  const [savedId, setSavedId] = useState(null);
  const [fillTopic, setFillTopic] = useState('');
  const [fillStandards, setFillStandards] = useState('');
  const [undoStack, setUndoStack] = useState([]);
  const [zoom, setZoom] = useState(85);

  // Two-level subject: category + course
  const [category, setCategory] = useState('Mathematics');
  const [course, setCourse] = useState(null); // course key e.g. "algebra_1"
  const [grade, setGrade] = useState('4');

  // Standards attached to this worksheet
  const [attachedStandards, setAttachedStandards] = useState([]);
  const [standardSearch, setStandardSearch] = useState('');
  const [standardResults, setStandardResults] = useState([]);
  const [searchingStandards, setSearchingStandards] = useState(false);
  const [suggestingStandards, setSuggestingStandards] = useState(false);

  // Image state
  const [imageUploading, setImageUploading] = useState(false);
  const [imageTab, setImageTab] = useState('search'); // 'search' | 'upload' | 'library'
  const [myImages, setMyImages] = useState([]);
  const [myImagesLoaded, setMyImagesLoaded] = useState(false);
  const [imageSearchQuery, setImageSearchQuery] = useState('');
  const [imageSearchResults, setImageSearchResults] = useState([]);
  const [imageSearching, setImageSearching] = useState(false);
  const fileInputRef = useRef(null);

  // First-time hint
  const [showHint, setShowHint] = useState(() => {
    if (typeof window !== 'undefined') return localStorage.getItem('lulia_design_hint_dismissed') !== 'true';
    return true;
  });

  // Course components config from backend
  const [courseConfig, setCourseConfig] = useState(null);
  const initDone = useRef(false);

  // 1. Fetch course config + teacher profile on mount
  useEffect(() => {
    (async () => {
      // Fetch course config
      let config = null;
      try {
        config = await apiFetch('/api/v1/design/course-components');
        setCourseConfig(config);
      } catch {
        // Config unavailable — will work with universal components only
      }

      // Fetch teacher profile for defaults
      try {
        const profile = await apiFetch('/api/v1/settings/profile');
        if (profile?.default_grade && GRADES.includes(String(profile.default_grade))) {
          setGrade(String(profile.default_grade));
        }
        // If profile has a course name, resolve to category + course
        if (profile?.default_subject && config) {
          const resolved = resolveProfileCourse(config, profile.default_subject);
          if (resolved) {
            setCategory(resolved.category);
            setCourse(resolved.course);
            initDone.current = true;
            return;
          }
          // Might be just a category name
          if (CATEGORIES.includes(profile.default_subject)) {
            setCategory(profile.default_subject);
          }
        }
      } catch {
        // Fall back to defaults
      }

      // Set initial course based on defaults
      if (config) {
        const g = grade; // closure has initial value '4'
        const first = getFirstCourse(config, 'Mathematics', g);
        setCourse(first);
      }
      initDone.current = true;
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 2. When category or grade changes, re-filter course list
  const availableCourses = useMemo(
    () => getCoursesForGrade(courseConfig, category, grade),
    [courseConfig, category, grade],
  );

  // Auto-select course when category/grade changes invalidate current selection
  useEffect(() => {
    if (!initDone.current || !courseConfig) return;
    if (ELEMENTARY_GRADES.has(grade)) {
      // Elementary: auto-pick first (general) course, dropdown hidden
      const first = getFirstCourse(courseConfig, category, grade);
      setCourse(first);
    } else {
      // Check if current course is still valid for new category+grade
      const valid = availableCourses.some(c => c.key === course);
      if (!valid) {
        setCourse(availableCourses.length > 0 ? availableCourses[0].key : null);
      }
    }
  }, [category, grade, courseConfig]); // eslint-disable-line react-hooks/exhaustive-deps

  // 3. Build the toolbox: Universal + Category tools + Course tools
  const isElementary = ELEMENTARY_GRADES.has(grade);

  const toolbox = useMemo(() => {
    const result = [...UNIVERSAL_TOOLBOX];
    if (!courseConfig?.categories?.[category]) return result;
    const catData = courseConfig.categories[category];

    // Tier 2: Category components
    const catComponents = catData.category_components || [];
    if (catComponents.length > 0) {
      result.push({
        group: `${category} Tools`,
        tier: 'category',
        items: catComponents.map(makeToolItem),
      });
    }

    // Tier 3: Course components
    if (course && catData.courses?.[course]) {
      const courseData = catData.courses[course];
      const courseComponents = courseData.components || [];
      if (courseComponents.length > 0) {
        result.push({
          group: courseData.name,
          tier: 'course',
          items: courseComponents.map(makeToolItem),
        });
      }
    }

    return result;
  }, [courseConfig, category, course]);

  // Collect which component types belong to the current category (for warning badges)
  const currentCategoryTypes = useMemo(
    () => getAllCategoryComponentTypes(courseConfig, category),
    [courseConfig, category],
  );
  // Collect all universal component types
  const universalTypes = useMemo(() => {
    const s = new Set();
    for (const g of UNIVERSAL_TOOLBOX) for (const item of g.items) s.add(item.type);
    return s;
  }, []);

  const gradeContext = useMemo(() => GRADE_ADJUSTMENTS[grade] || GRADE_ADJUSTMENTS['4'], [grade]);
  const selectedComp = components.find(c => c.instanceId === selectedId);

  // ── Actions ────────────────────────────────────────────────────────────────
  function pushUndo() { setUndoStack(prev => [...prev.slice(-20), JSON.stringify(components)]); }

  function undo() {
    if (undoStack.length === 0) return;
    const prev = undoStack[undoStack.length - 1];
    setUndoStack(s => s.slice(0, -1));
    setComponents(JSON.parse(prev));
  }

  function addComponent(toolItem) {
    pushUndo();
    const comp = {
      instanceId: `${toolItem.type}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type: toolItem.type,
      config: { ...toolItem.defaults },
      layout: { columns: 12, columnStart: 1 },
    };
    setComponents(prev => [...prev, comp]);
    setSelectedId(comp.instanceId);
  }

  function updateConfig(instanceId, updates) {
    pushUndo();
    setComponents(prev => prev.map(c => c.instanceId === instanceId ? { ...c, config: { ...c.config, ...updates } } : c));
  }

  function removeComponent(instanceId) {
    pushUndo();
    setComponents(prev => prev.filter(c => c.instanceId !== instanceId));
    if (selectedId === instanceId) setSelectedId(null);
  }

  function moveComponent(index, dir) {
    const newIdx = index + dir;
    if (newIdx < 0 || newIdx >= components.length) return;
    pushUndo();
    setComponents(prev => {
      const arr = [...prev];
      [arr[index], arr[newIdx]] = [arr[newIdx], arr[index]];
      return arr;
    });
  }

  function duplicateComponent(instanceId) {
    pushUndo();
    const orig = components.find(c => c.instanceId === instanceId);
    if (!orig) return;
    const copy = { ...orig, instanceId: `${orig.type}_${Date.now()}_dup`, config: { ...orig.config } };
    const idx = components.findIndex(c => c.instanceId === instanceId);
    setComponents(prev => [...prev.slice(0, idx + 1), copy, ...prev.slice(idx + 1)]);
  }

  function handleCategoryChange(newCat) {
    setCategory(newCat);
    // Course will be auto-reset by the useEffect
  }

  function handleGradeChange(newGrade) {
    setGrade(newGrade);
    // Course will be auto-reset by the useEffect
  }

  async function handleSave() {
    setSaving(true);
    const canvasJson = { name: docName, theme, primaryColor, category, course, grade, standards: attachedStandards.map(s => ({ standard_id: s.standard_id, code: s.code, description: s.description })), components };
    try {
      if (savedId) {
        await apiFetch(`/api/v1/design/templates/${savedId}`, { method: 'PUT', body: JSON.stringify({ name: docName, canvas_json: canvasJson, design_theme: theme }) });
      } else {
        const res = await apiFetch('/api/v1/design/templates', { method: 'POST', body: JSON.stringify({ name: docName, canvas_json: canvasJson, design_theme: theme }) });
        setSavedId(res.template_id);
      }
    } catch (e) { alert(e.message); }
    finally { setSaving(false); }
  }

  async function handlePreview() {
    if (!savedId) await handleSave();
    try {
      const res = await apiFetch(`/api/v1/design/templates/${savedId}/preview`, { method: 'POST' });
      setPreviewHtml(res.preview_html);
    } catch (e) { alert(e.message); }
  }

  async function handleAIFill() {
    if (!savedId) await handleSave();
    setFilling(true);
    try {
      const res = await apiFetch(`/api/v1/design/templates/${savedId}/ai-fill`, {
        method: 'POST',
        body: JSON.stringify({ topic: fillTopic, standards: fillStandards.split(',').map(s => s.trim()).filter(Boolean) }),
      });
      if (res.filled_canvas?.components) setComponents(res.filled_canvas.components);
    } catch (e) { alert(e.message); }
    finally { setFilling(false); }
  }

  function dismissHint() {
    setShowHint(false);
    if (typeof window !== 'undefined') localStorage.setItem('lulia_design_hint_dismissed', 'true');
  }

  // ── Image Upload / Generate ──────────────────────────────────────────────
  async function handleImageUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await apiUpload('/api/v1/images/upload', formData);
      if (data.storage_url && selectedId) {
        updateConfig(selectedId, { url: data.storage_url });
      }
    } catch (err) { alert('Upload failed: ' + err.message); }
    finally { setImageUploading(false); e.target.value = ''; }
  }

  async function loadMyImages() {
    if (myImagesLoaded) return;
    try {
      const res = await apiFetch('/api/v1/images');
      setMyImages(res.images || []);
    } catch { setMyImages([]); }
    finally { setMyImagesLoaded(true); }
  }

  async function handleImageSearch() {
    if (!imageSearchQuery.trim()) return;
    setImageSearching(true);
    try {
      const res = await apiFetch(`/api/v1/images/search?q=${encodeURIComponent(imageSearchQuery)}`);
      setImageSearchResults(res.images || []);
    } catch { setImageSearchResults([]); }
    finally { setImageSearching(false); }
  }

  function selectSearchImage(img) {
    if (selectedId) updateConfig(selectedId, { url: img.url, caption: img.attribution || '' });
  }


  // ── Standards Search / Suggest ───────────────────────────────────────────
  async function searchStandards() {
    if (!standardSearch.trim()) return;
    setSearchingStandards(true);
    try {
      const params = new URLSearchParams({ code: standardSearch, grade, limit: '20' });
      if (category !== 'General') params.set('subject', category);
      const res = await apiFetch(`/api/v1/standards?${params}`);
      setStandardResults(res.standards || []);
    } catch { setStandardResults([]); }
    finally { setSearchingStandards(false); }
  }

  async function suggestStandards() {
    setSuggestingStandards(true);
    try {
      const res = await apiFetch('/api/v1/standards/suggest', {
        method: 'POST',
        body: JSON.stringify({
          description: standardSearch || '',
          subject: category,
          grade,
          worksheet_content: components.map(c => ({ type: c.type, config: c.config })),
        }),
      });
      setStandardResults(res.standards || []);
    } catch { setStandardResults([]); }
    finally { setSuggestingStandards(false); }
  }

  function attachStandard(std) {
    if (attachedStandards.some(s => s.standard_id === std.standard_id)) return;
    setAttachedStandards(prev => [...prev, std]);
  }

  function removeStandard(standardId) {
    setAttachedStandards(prev => prev.filter(s => s.standard_id !== standardId));
  }

  // Check if a canvas component belongs to a different category (show warning)
  function isOutOfCategory(compType) {
    if (universalTypes.has(compType)) return false; // universal = always fine
    if (currentCategoryTypes.has(compType)) return false; // belongs to current category
    // It's a specialist component from another category
    return true;
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', margin: '-24px', overflow: 'hidden' }}>
      {/* LEFT: Component Toolbox */}
      <div style={{ width: 240, background: 'white', borderRight: '1px solid #E7E5E4', overflowY: 'auto', padding: 12, flexShrink: 0 }}>
        <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#1C1917', marginBottom: 10 }}>Components</h3>
        {toolbox.map(group => (
          <div key={group.group} style={{ marginBottom: 12 }}>
            <div style={{
              fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em',
              color: group.tier === 'category' ? '#F97316' : group.tier === 'course' ? '#7C3AED' : '#A8A29E',
              marginBottom: 4, paddingLeft: 4,
            }}>{group.group}</div>
            {group.items.map(item => (
              <button key={`${group.group}_${item.type}`} onClick={() => addComponent(item)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '5px 8px', borderRadius: 8, border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 12, color: '#1C1917', textAlign: 'left', fontFamily: "'DM Sans'", transition: 'background 0.15s' }}
                onMouseEnter={e => e.currentTarget.style.background = '#FFF7ED'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <span style={{ fontSize: 13, width: 20, textAlign: 'center' }}>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* CENTER: Canvas */}
      <div style={{ flex: 1, background: '#F5DEC3', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {/* Canvas toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 16px', background: '#FEF7EE', borderBottom: '1px solid #E7E5E4', flexShrink: 0, gap: 8 }}>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <button onClick={undo} disabled={undoStack.length === 0} title="Undo" style={{ padding: 4, borderRadius: 6, border: 'none', background: 'transparent', cursor: 'pointer', color: undoStack.length ? '#78350F' : '#D6D3D1' }}><Undo2 className="w-4 h-4" /></button>
            <span style={{ fontSize: 10, color: '#A8A29E', display: 'flex', alignItems: 'center', gap: 4 }}>
              Zoom: <input type="range" min={50} max={150} value={zoom} onChange={e => setZoom(+e.target.value)} style={{ width: 60, accentColor: '#F97316' }} /> {zoom}%
            </span>
          </div>
          {/* Category + Course + Grade selectors */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <select value={category} onChange={e => handleCategoryChange(e.target.value)}
              style={{ fontSize: 11, padding: '3px 8px', borderRadius: 8, border: '1px solid #E7E5E4', background: 'white', fontFamily: "'DM Sans'", color: '#1C1917', cursor: 'pointer', outline: 'none' }}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            {!isElementary && availableCourses.length > 0 && (
              <select value={course || ''} onChange={e => setCourse(e.target.value)}
                style={{ fontSize: 11, padding: '3px 8px', borderRadius: 8, border: '1px solid #E7E5E4', background: 'white', fontFamily: "'DM Sans'", color: '#1C1917', cursor: 'pointer', outline: 'none' }}>
                {availableCourses.map(c => <option key={c.key} value={c.key}>{c.name}</option>)}
              </select>
            )}
            <select value={grade} onChange={e => handleGradeChange(e.target.value)}
              style={{ fontSize: 11, padding: '3px 8px', borderRadius: 8, border: '1px solid #E7E5E4', background: 'white', fontFamily: "'DM Sans'", color: '#1C1917', cursor: 'pointer', outline: 'none' }}>
              {GRADES.map(g => <option key={g} value={g}>Grade {g}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {THEME_PRESETS.slice(0, 6).map(t => (
              <button key={t.id} onClick={() => { setTheme(t.id); setPrimaryColor(t.color); }} title={t.name}
                style={{ width: 20, height: 20, borderRadius: '50%', border: theme === t.id ? '2px solid #1C1917' : '2px solid transparent', background: t.color, cursor: 'pointer' }} />
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={handlePreview} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, border: '1px solid #E7E5E4', background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontFamily: "'DM Sans'" }}><Eye className="w-3.5 h-3.5" /> Preview</button>
            <button onClick={handleSave} disabled={saving} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, border: 'none', background: '#F97316', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontFamily: "'DM Sans'" }}>
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Save
            </button>
          </div>
        </div>

        {/* Preview mode */}
        {previewHtml ? (
          <div style={{ padding: 24, display: 'flex', justifyContent: 'center' }}>
            <div style={{ width: 680, background: 'white', borderRadius: 14, overflow: 'hidden' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 12px', background: '#FEF9F2', borderBottom: '1px solid #E7E5E4' }}>
                <span style={{ fontSize: 11, color: '#78716C' }}>Print Preview</span>
                <button onClick={() => setPreviewHtml(null)} style={{ fontSize: 11, color: '#F97316', cursor: 'pointer', border: 'none', background: 'none' }}>Back to Editor</button>
              </div>
              <iframe srcDoc={previewHtml} style={{ width: '100%', minHeight: 900, border: 'none' }} />
            </div>
          </div>
        ) : (
          /* Canvas */
          <div style={{ padding: 24, display: 'flex', justifyContent: 'center', flex: 1 }}>
            <div style={{
              width: 680, minHeight: 880, background: '#FEF9F2', borderRadius: 14, padding: 32,
              boxShadow: '0 2px 12px rgba(0,0,0,0.06)', transform: `scale(${zoom / 100})`, transformOrigin: 'top center',
            }} onClick={() => setSelectedId(null)}>
              {/* Document title */}
              <input value={docName} onChange={e => setDocName(e.target.value)} onClick={e => e.stopPropagation()}
                style={{ width: '100%', border: 'none', background: 'transparent', fontFamily: "'DM Serif Display', serif", fontSize: 20, color: '#1C1917', outline: 'none', marginBottom: 16, textAlign: 'center' }} />

              {components.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px 0', color: '#A8A29E' }}>
                  <Plus style={{ width: 32, height: 32, margin: '0 auto 8px', color: '#FDBA74' }} />
                  <p style={{ fontSize: 14, fontFamily: "'DM Serif Display', serif", color: '#78716C' }}>Click a component from the left panel</p>
                  <p style={{ fontSize: 12, marginTop: 4 }}>Your worksheet will appear here exactly as it will print</p>
                </div>
              ) : (
                components.map((comp, idx) => {
                  const Renderer = RENDERERS[comp.type];
                  const isSelected = selectedId === comp.instanceId;
                  const outOfCat = isOutOfCategory(comp.type);
                  return (
                    <div key={comp.instanceId}
                      onClick={e => { e.stopPropagation(); setSelectedId(comp.instanceId); }}
                      style={{
                        position: 'relative', padding: '8px 12px', marginBottom: 6, borderRadius: 10,
                        border: isSelected ? '2px solid #F97316' : outOfCat ? '1px dashed #FDBA74' : '1px solid transparent',
                        background: isSelected ? 'rgba(249,115,22,0.03)' : 'transparent',
                        cursor: 'pointer', transition: 'border 0.15s',
                      }}
                      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.border = outOfCat ? '1px dashed #F97316' : '1px solid #FDBA74'; }}
                      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.border = outOfCat ? '1px dashed #FDBA74' : '1px solid transparent'; }}>
                      {/* Warning badge for out-of-category components */}
                      {outOfCat && (
                        <div title="This component belongs to a different category" style={{ position: 'absolute', top: -6, right: -6, width: 16, height: 16, borderRadius: '50%', background: '#FEF3C7', border: '1px solid #F59E0B', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 5 }}>
                          <AlertTriangle style={{ width: 10, height: 10, color: '#D97706' }} />
                        </div>
                      )}
                      {/* Toolbar for selected */}
                      {isSelected && (
                        <div style={{ position: 'absolute', top: -28, left: 0, display: 'flex', gap: 2, background: 'white', borderRadius: 8, padding: 2, boxShadow: '0 2px 8px rgba(0,0,0,0.1)', zIndex: 10 }}>
                          <button onClick={e => { e.stopPropagation(); moveComponent(idx, -1); }} title="Move up" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#78716C' }}><ChevronUp className="w-3.5 h-3.5" /></button>
                          <button onClick={e => { e.stopPropagation(); moveComponent(idx, 1); }} title="Move down" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#78716C' }}><ChevronDown className="w-3.5 h-3.5" /></button>
                          <button onClick={e => { e.stopPropagation(); duplicateComponent(comp.instanceId); }} title="Duplicate" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#78716C' }}><Copy className="w-3.5 h-3.5" /></button>
                          <button onClick={e => { e.stopPropagation(); removeComponent(comp.instanceId); }} title="Delete" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#EF4444' }}><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                      )}
                      {/* First-time hint */}
                      {isSelected && showHint && (
                        <div style={{ position: 'absolute', top: -28, right: 0, background: '#78350F', color: 'white', padding: '4px 10px', borderRadius: 8, fontSize: 10, display: 'flex', alignItems: 'center', gap: 6, zIndex: 10, whiteSpace: 'nowrap', boxShadow: '0 2px 8px rgba(0,0,0,0.15)' }}>
                          Edit this component in the right panel &rarr;
                          <button onClick={e => { e.stopPropagation(); dismissHint(); }} style={{ border: 'none', background: 'transparent', color: '#FDBA74', cursor: 'pointer', fontSize: 10, textDecoration: 'underline', padding: 0 }}>Don't show again</button>
                        </div>
                      )}
                      {/* Renderer — placeholder for specialist components without a dedicated renderer */}
                      {Renderer
                        ? <Renderer config={comp.config} theme={theme} gradeContext={gradeContext} />
                        : <div style={{ fontSize: 12, color: '#78716C', padding: '12px 8px', background: '#F5F5F4', borderRadius: 8, border: '1px dashed #D6D3D1', textAlign: 'center' }}>
                            <span style={{ fontSize: 16, marginRight: 6 }}>🧩</span>{comp.config?._label || comp.type.replace(/_/g, ' ')}
                          </div>
                      }
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* RIGHT: Properties Panel */}
      <div style={{ width: 280, background: 'white', borderLeft: '1px solid #E7E5E4', overflowY: 'auto', padding: 12, flexShrink: 0 }}>
        {selectedComp ? (
          /* Component properties */
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#1C1917' }}>{selectedComp.type.replace(/_/g, ' ')}</h3>
              <button onClick={() => setSelectedId(null)} style={{ fontSize: 10, color: '#A8A29E', border: 'none', background: 'none', cursor: 'pointer' }}>✕</button>
            </div>

            {/* Dynamic config editor based on type */}
            {selectedComp.type === 'header' && <>
              <Field label="Text" value={selectedComp.config.text} onChange={v => updateConfig(selectedId, { text: v })} />
              <Select label="Level" value={selectedComp.config.level} options={[['h1','H1'],['h2','H2'],['h3','H3']]} onChange={v => updateConfig(selectedId, { level: v })} />
              <Select label="Align" value={selectedComp.config.alignment} options={[['left','Left'],['center','Center'],['right','Right']]} onChange={v => updateConfig(selectedId, { alignment: v })} />
              <Field label="Subtitle" value={selectedComp.config.subtitle} onChange={v => updateConfig(selectedId, { subtitle: v })} />
            </>}
            {selectedComp.type === 'multiple_choice' && <>
              <Field label="Question" value={selectedComp.config.question} onChange={v => updateConfig(selectedId, { question: v })} multiline />
              {(selectedComp.config.options || []).map((opt, i) => (
                <Field key={i} label={`Option ${String.fromCharCode(65 + i)}`} value={opt} onChange={v => {
                  const opts = [...(selectedComp.config.options || [])];
                  opts[i] = v;
                  updateConfig(selectedId, { options: opts });
                }} />
              ))}
              <Select label="Correct" value={String(selectedComp.config.correct)} options={(selectedComp.config.options || []).map((_, i) => [String(i), String.fromCharCode(65 + i)])} onChange={v => updateConfig(selectedId, { correct: parseInt(v) })} />
              <Field label="Points" value={String(selectedComp.config.points || 1)} onChange={v => updateConfig(selectedId, { points: parseInt(v) || 1 })} />
            </>}
            {selectedComp.type === 'fill_in_blank' && <Field label="Sentence (use ___ for blanks)" value={selectedComp.config.sentence} onChange={v => updateConfig(selectedId, { sentence: v })} multiline />}
            {selectedComp.type === 'short_answer' && <>
              <Field label="Question" value={selectedComp.config.question} onChange={v => updateConfig(selectedId, { question: v })} multiline />
              <Select label="Lines" value={String(selectedComp.config.lines)} options={[['1','1'],['2','2'],['3','3']]} onChange={v => updateConfig(selectedId, { lines: parseInt(v) })} />
            </>}
            {selectedComp.type === 'long_answer' && <>
              <Field label="Question" value={selectedComp.config.question} onChange={v => updateConfig(selectedId, { question: v })} multiline />
              <Select label="Size" value={selectedComp.config.size} options={[['small','Small'],['medium','Medium'],['large','Large']]} onChange={v => updateConfig(selectedId, { size: v })} />
            </>}
            {selectedComp.type === 'true_false' && <Field label="Statement" value={selectedComp.config.statement} onChange={v => updateConfig(selectedId, { statement: v })} />}
            {selectedComp.type === 'instructions' && <Field label="Instructions (HTML)" value={selectedComp.config.html} onChange={v => updateConfig(selectedId, { html: v })} multiline />}
            {selectedComp.type === 'text_block' && <Field label="Text" value={selectedComp.config.text} onChange={v => updateConfig(selectedId, { text: v })} multiline />}
            {selectedComp.type === 'word_bank' && <Field label="Words (comma separated)" value={(selectedComp.config.words || []).join(', ')} onChange={v => updateConfig(selectedId, { words: v.split(',').map(w => w.trim()).filter(Boolean) })} />}
            {selectedComp.type === 'reading_passage' && <>
              <Field label="Title" value={selectedComp.config.title} onChange={v => updateConfig(selectedId, { title: v })} />
              <Field label="Passage" value={selectedComp.config.text} onChange={v => updateConfig(selectedId, { text: v })} multiline />
            </>}
            {selectedComp.type === 'image' && <>
              <input ref={fileInputRef} type="file" accept="image/*" onChange={handleImageUpload} style={{ display: 'none' }} />

              {/* Tabs */}
              <div style={{ display: 'flex', gap: 0, marginBottom: 8, borderRadius: 8, overflow: 'hidden', border: '1px solid #E7E5E4' }}>
                {[
                  ['search', 'Search'],
                  ['upload', 'Upload'],
                  ['library', 'Library'],
                ].map(([id, label]) => (
                  <button key={id} onClick={() => { setImageTab(id); if (id === 'library') loadMyImages(); }}
                    style={{ flex: 1, padding: '5px 0', border: 'none', borderLeft: id !== 'search' ? '1px solid #E7E5E4' : 'none', fontSize: 9, fontWeight: 600, fontFamily: "'DM Sans'", cursor: 'pointer', background: imageTab === id ? '#F97316' : 'white', color: imageTab === id ? 'white' : '#78716C' }}>
                    {label}
                  </button>
                ))}
              </div>

              {/* Search — Wikimedia + Pixabay */}
              {imageTab === 'search' && <>
                <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
                  <input value={imageSearchQuery} onChange={e => setImageSearchQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleImageSearch()}
                    placeholder="e.g. cell division, fractions"
                    style={{ flex: 1, border: '1px solid #E7E5E4', borderRadius: 8, padding: '5px 8px', fontSize: 11, outline: 'none', fontFamily: "'DM Sans'" }} />
                  <button onClick={handleImageSearch} disabled={imageSearching || !imageSearchQuery.trim()}
                    style={{ padding: '5px 8px', borderRadius: 8, border: 'none', background: '#F97316', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                    {imageSearching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
                  </button>
                </div>
                {imageSearchResults.length > 0 && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, maxHeight: 200, overflowY: 'auto', marginBottom: 4 }}>
                    {imageSearchResults.map(img => (
                      <button key={img.id} onClick={() => selectSearchImage(img)}
                        style={{ border: '1px solid #E7E5E4', borderRadius: 6, overflow: 'hidden', cursor: 'pointer', background: 'white', padding: 0, display: 'block', position: 'relative' }}
                        title={img.attribution}>
                        <img src={img.thumb} alt="" style={{ width: '100%', height: 65, objectFit: 'cover', display: 'block' }} />
                        <span style={{ position: 'absolute', bottom: 1, right: 2, fontSize: 7, color: 'white', background: 'rgba(0,0,0,0.5)', padding: '0 3px', borderRadius: 3 }}>{img.source}</span>
                      </button>
                    ))}
                  </div>
                )}
                <div style={{ fontSize: 8, color: '#A8A29E', textAlign: 'center' }}>Wikimedia Commons + Pixabay. Free for educational use.</div>
              </>}

              {/* Upload */}
              {imageTab === 'upload' && <>
                <button onClick={() => fileInputRef.current?.click()} disabled={imageUploading}
                  style={{ width: '100%', marginBottom: 8, padding: '20px 0', borderRadius: 10, border: '2px dashed #FDBA74', background: '#FFF7ED', cursor: 'pointer', fontSize: 12, fontFamily: "'DM Sans'", display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, color: '#78350F' }}>
                  {imageUploading ? <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#F97316' }} /> : <Upload className="w-5 h-5" style={{ color: '#F97316' }} />}
                  {imageUploading ? 'Uploading...' : 'Choose file or drag & drop'}
                  <span style={{ fontSize: 9, color: '#A8A29E' }}>PNG, JPG, GIF up to 10MB</span>
                </button>
              </>}

              {/* My Library */}
              {imageTab === 'library' && <>
                {!myImagesLoaded ? (
                  <div style={{ textAlign: 'center', padding: 16 }}><Loader2 className="w-4 h-4 animate-spin" style={{ color: '#F97316', margin: '0 auto' }} /></div>
                ) : myImages.length === 0 ? (
                  <div style={{ fontSize: 11, color: '#A8A29E', textAlign: 'center', padding: 16 }}>No images yet. Upload one first.</div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, maxHeight: 240, overflowY: 'auto', marginBottom: 8 }}>
                    {myImages.map(img => (
                      <button key={img.image_id} onClick={() => updateConfig(selectedId, { url: img.storage_url })}
                        style={{ border: '1px solid #E7E5E4', borderRadius: 6, overflow: 'hidden', cursor: 'pointer', background: 'white', padding: 0, display: 'block' }}
                        title={img.filename}>
                        <img src={img.thumbnail_url || img.storage_url} alt="" style={{ width: '100%', height: 70, objectFit: 'cover', display: 'block' }} />
                      </button>
                    ))}
                  </div>
                )}
              </>}

              <Field label="Caption" value={selectedComp.config.caption} onChange={v => updateConfig(selectedId, { caption: v })} />
              <Select label="Size" value={selectedComp.config.size} options={[['small','25%'],['medium','50%'],['large','75%'],['full','100%']]} onChange={v => updateConfig(selectedId, { size: v })} />
            </>}
            {selectedComp.type === 'table' && <>
              <Field label="Rows" value={String(selectedComp.config.rows)} onChange={v => updateConfig(selectedId, { rows: parseInt(v) || 3 })} />
              <Field label="Columns" value={String(selectedComp.config.cols)} onChange={v => updateConfig(selectedId, { cols: parseInt(v) || 3 })} />
            </>}
            {selectedComp.type === 'number_line' && <>
              <Field label="Min" value={String(selectedComp.config.min)} onChange={v => updateConfig(selectedId, { min: parseFloat(v) || 0 })} />
              <Field label="Max" value={String(selectedComp.config.max)} onChange={v => updateConfig(selectedId, { max: parseFloat(v) || 10 })} />
              <Field label="Interval" value={String(selectedComp.config.interval)} onChange={v => updateConfig(selectedId, { interval: parseFloat(v) || 1 })} />
            </>}
            {selectedComp.type === 'divider' && <Field label="Label (optional)" value={selectedComp.config.label} onChange={v => updateConfig(selectedId, { label: v })} />}
            {selectedComp.type === 'math_problem' && <>
              <Field label="Problem" value={selectedComp.config.problem} onChange={v => updateConfig(selectedId, { problem: v })} />
            </>}
            {selectedComp.type === 'example' && <Field label="Steps" value={selectedComp.config.text} onChange={v => updateConfig(selectedId, { text: v })} multiline />}
            {selectedComp.type === 'vocabulary' && <>
              <Field label="Term" value={selectedComp.config.term} onChange={v => updateConfig(selectedId, { term: v })} />
              <Field label="Definition" value={selectedComp.config.definition} onChange={v => updateConfig(selectedId, { definition: v })} multiline />
              <Field label="Example sentence" value={selectedComp.config.example} onChange={v => updateConfig(selectedId, { example: v })} />
            </>}
            {selectedComp.type === 'banner' && <>
              <Field label="Text" value={selectedComp.config.text} onChange={v => updateConfig(selectedId, { text: v })} />
              <Field label="Color (hex)" value={selectedComp.config.color} onChange={v => updateConfig(selectedId, { color: v })} />
            </>}
            {/* Specialist editor fallback — handles all 134 category/course components */}
            {!['header','multiple_choice','fill_in_blank','short_answer','long_answer','true_false',
               'instructions','text_block','word_bank','reading_passage','image','table','number_line',
               'divider','math_problem','example','vocabulary','banner','name_date_line','spacer',
               'answer_key','matching'].includes(selectedComp.type) && (
              <SpecialistEditor type={selectedComp.type} config={selectedComp.config} onUpdate={updates => updateConfig(selectedId, updates)} />
            )}
          </div>
        ) : (
          /* Document properties — NO subject/grade here (toolbar-only) */
          <div>
            <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#1C1917', marginBottom: 10 }}>Document</h3>
            <Field label="Worksheet Title" value={docName} onChange={setDocName} />
            <div style={{ fontSize: 10, color: '#A8A29E', marginTop: 4, marginBottom: 8 }}>{components.length} components</div>

            {/* Theme quick picks */}
            <div style={{ marginBottom: 12 }}>
              <span style={{ fontSize: 10, fontWeight: 600, color: '#78350F' }}>Theme</span>
              <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                {THEME_PRESETS.map(t => (
                  <button key={t.id} onClick={() => { setTheme(t.id); setPrimaryColor(t.color); }} title={t.name}
                    style={{ width: 24, height: 24, borderRadius: '50%', border: theme === t.id ? '2px solid #1C1917' : '2px solid #E7E5E4', background: t.color, cursor: 'pointer' }} />
                ))}
              </div>
            </div>

            {/* AI Fill */}
            <div style={{ borderTop: '1px solid #E7E5E4', paddingTop: 12, marginTop: 8 }}>
              <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#F97316', marginBottom: 8 }}>AI Fill</h3>
              <Field label="Topic" value={fillTopic} onChange={setFillTopic} placeholder="e.g. Fractions" />
              <Field label="Standards" value={fillStandards} onChange={setFillStandards} placeholder="4.NF.1, 4.NF.2" />
              <button onClick={handleAIFill} disabled={filling || components.length === 0}
                style={{ width: '100%', marginTop: 6, background: filling ? '#FDBA74' : '#F97316', color: 'white', border: 'none', padding: '8px', borderRadius: 10, fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontFamily: "'DM Sans'" }}>
                {filling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                {filling ? 'Filling...' : 'AI Fill'}
              </button>
            </div>

            {/* Standards */}
            <div style={{ borderTop: '1px solid #E7E5E4', paddingTop: 12, marginTop: 8 }}>
              <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <BookOpen className="w-3.5 h-3.5" /> Standards
              </h3>

              {/* Attached standards badges */}
              {attachedStandards.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                  {attachedStandards.map(s => (
                    <span key={s.standard_id} title={s.description}
                      style={{ fontSize: 10, padding: '2px 6px', background: '#FFF7ED', border: '1px solid #FDBA74', borderRadius: 6, color: '#78350F', display: 'flex', alignItems: 'center', gap: 3, maxWidth: '100%' }}>
                      <strong>{s.code}</strong>
                      <button onClick={() => removeStandard(s.standard_id)} style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0, color: '#A8A29E', lineHeight: 1 }}>
                        <X style={{ width: 10, height: 10 }} />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Search bar */}
              <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
                <input value={standardSearch} onChange={e => setStandardSearch(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && searchStandards()}
                  placeholder="Code or description..."
                  style={{ flex: 1, border: '1px solid #E7E5E4', borderRadius: 8, padding: '5px 8px', fontSize: 11, outline: 'none', fontFamily: "'DM Sans'" }} />
                <button onClick={searchStandards} disabled={searchingStandards}
                  title="Search standards"
                  style={{ padding: '5px 6px', borderRadius: 8, border: '1px solid #E7E5E4', background: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                  {searchingStandards ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
                </button>
              </div>

              {/* AI Suggest button */}
              <button onClick={suggestStandards} disabled={suggestingStandards}
                style={{ width: '100%', marginBottom: 6, padding: '6px 0', borderRadius: 8, border: '1px dashed #FDBA74', background: '#FFF7ED', cursor: 'pointer', fontSize: 11, fontFamily: "'DM Sans'", display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, color: '#78350F' }}>
                {suggestingStandards ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                {suggestingStandards ? 'Analyzing worksheet...' : 'AI Suggest Standards'}
              </button>

              {/* Search / suggestion results */}
              {standardResults.length > 0 && (
                <div style={{ maxHeight: 180, overflowY: 'auto', border: '1px solid #E7E5E4', borderRadius: 8, background: '#FAFAF9' }}>
                  {standardResults.map(s => {
                    const alreadyAttached = attachedStandards.some(a => a.standard_id === s.standard_id);
                    return (
                      <button key={s.standard_id} onClick={() => !alreadyAttached && attachStandard(s)}
                        disabled={alreadyAttached}
                        style={{ display: 'block', width: '100%', textAlign: 'left', padding: '6px 8px', border: 'none', borderBottom: '1px solid #F5F5F4', background: alreadyAttached ? '#F5F5F4' : 'transparent', cursor: alreadyAttached ? 'default' : 'pointer', fontSize: 10, fontFamily: "'DM Sans'" }}
                        onMouseEnter={e => { if (!alreadyAttached) e.currentTarget.style.background = '#FFF7ED'; }}
                        onMouseLeave={e => { if (!alreadyAttached) e.currentTarget.style.background = 'transparent'; }}>
                        <div style={{ fontWeight: 600, color: alreadyAttached ? '#A8A29E' : '#78350F' }}>
                          {s.code} {alreadyAttached && '(added)'}
                        </div>
                        <div style={{ color: '#78716C', marginTop: 1, lineHeight: 1.3 }}>{(s.description || '').slice(0, 120)}</div>
                        <div style={{ color: '#A8A29E', marginTop: 1 }}>{s.framework_name} &middot; {s.tier}</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Reusable form helpers ────────────────────────────────────────────────────

function Field({ label, value, onChange, placeholder, multiline }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ display: 'block', fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 2 }}>{label}</label>
      {multiline ? (
        <textarea value={value || ''} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={3}
          style={{ width: '100%', border: '1px solid #E7E5E4', borderRadius: 8, padding: '6px 8px', fontSize: 12, outline: 'none', resize: 'vertical', fontFamily: "'DM Sans'" }} />
      ) : (
        <input value={value || ''} onChange={e => onChange(e.target.value)} placeholder={placeholder}
          style={{ width: '100%', border: '1px solid #E7E5E4', borderRadius: 8, padding: '5px 8px', fontSize: 12, outline: 'none', fontFamily: "'DM Sans'" }} />
      )}
    </div>
  );
}

function Select({ label, value, options, onChange }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ display: 'block', fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 2 }}>{label}</label>
      <select value={value || ''} onChange={e => onChange(e.target.value)}
        style={{ width: '100%', border: '1px solid #E7E5E4', borderRadius: 8, padding: '5px 8px', fontSize: 12, outline: 'none', fontFamily: "'DM Sans'" }}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}
