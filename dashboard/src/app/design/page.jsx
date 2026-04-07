'use client';
import { useState, useCallback } from 'react';
import { Save, Eye, Sparkles, Undo2, Redo2, GripVertical, Trash2, Copy, ChevronUp, ChevronDown, Loader2, Plus } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { RENDERERS } from '@/components/design/ComponentRenderers';

// Toolbox component definitions
const TOOLBOX = [
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
    { type: 'math_problem', label: 'Math Problem', icon: '🔢', defaults: { problem: '', showWorkSpace: true } },
  ]},
  { group: 'Content', items: [
    { type: 'instructions', label: 'Instructions', icon: '📋', defaults: { html: '<b>Directions:</b> Complete all problems.' } },
    { type: 'text_block', label: 'Text Block', icon: '¶', defaults: { text: '' } },
    { type: 'word_bank', label: 'Word Bank', icon: '📦', defaults: { words: [] } },
    { type: 'reading_passage', label: 'Reading Passage', icon: '📖', defaults: { text: '', title: '' } },
    { type: 'example', label: 'Example', icon: '💡', defaults: { text: '' } },
    { type: 'vocabulary', label: 'Vocabulary', icon: '📚', defaults: { term: '', definition: '' } },
  ]},
  { group: 'Visual', items: [
    { type: 'image', label: 'Image', icon: '🖼️', defaults: {} },
    { type: 'table', label: 'Table', icon: '📊', defaults: { rows: 3, cols: 3, showHeader: true } },
    { type: 'number_line', label: 'Number Line', icon: '📏', defaults: { min: 0, max: 10, interval: 1 } },
    { type: 'graph_grid', label: 'Graph Grid', icon: '📐', defaults: {} },
  ]},
  { group: 'Layout', items: [
    { type: 'divider', label: 'Divider', icon: '—', defaults: { label: '' } },
    { type: 'spacer', label: 'Spacer', icon: '↕', defaults: { size: 'medium' } },
    { type: 'answer_key', label: 'Answer Key', icon: '🔑', defaults: { auto_populate: true } },
  ]},
];

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

  const selectedComp = components.find(c => c.instanceId === selectedId);

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

  async function handleSave() {
    setSaving(true);
    const canvasJson = { name: docName, theme, primaryColor, components };
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

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', margin: '-24px', overflow: 'hidden' }}>
      {/* LEFT: Component Toolbox */}
      <div style={{ width: 240, background: 'white', borderRight: '1px solid #E7E5E4', overflowY: 'auto', padding: 12, flexShrink: 0 }}>
        <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#1C1917', marginBottom: 10 }}>Components</h3>
        {TOOLBOX.map(group => (
          <div key={group.group} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#A8A29E', marginBottom: 4, paddingLeft: 4 }}>{group.group}</div>
            {group.items.map(item => (
              <button key={item.type} onClick={() => addComponent(item)}
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
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 16px', background: '#FEF7EE', borderBottom: '1px solid #E7E5E4', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button onClick={undo} disabled={undoStack.length === 0} title="Undo" style={{ padding: 4, borderRadius: 6, border: 'none', background: 'transparent', cursor: 'pointer', color: undoStack.length ? '#78350F' : '#D6D3D1' }}><Undo2 className="w-4 h-4" /></button>
            <span style={{ fontSize: 10, color: '#A8A29E', display: 'flex', alignItems: 'center', gap: 4 }}>
              Zoom: <input type="range" min={50} max={150} value={zoom} onChange={e => setZoom(+e.target.value)} style={{ width: 60, accentColor: '#F97316' }} /> {zoom}%
            </span>
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
                  return (
                    <div key={comp.instanceId}
                      onClick={e => { e.stopPropagation(); setSelectedId(comp.instanceId); }}
                      style={{
                        position: 'relative', padding: '8px 12px', marginBottom: 6, borderRadius: 10,
                        border: isSelected ? '2px solid #F97316' : '1px solid transparent',
                        background: isSelected ? 'rgba(249,115,22,0.03)' : 'transparent',
                        cursor: 'pointer', transition: 'border 0.15s',
                      }}
                      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.border = '1px solid #FDBA74'; }}
                      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.border = '1px solid transparent'; }}>
                      {/* Toolbar for selected */}
                      {isSelected && (
                        <div style={{ position: 'absolute', top: -28, left: 0, display: 'flex', gap: 2, background: 'white', borderRadius: 8, padding: 2, boxShadow: '0 2px 8px rgba(0,0,0,0.1)', zIndex: 10 }}>
                          <button onClick={e => { e.stopPropagation(); moveComponent(idx, -1); }} title="Move up" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#78716C' }}><ChevronUp className="w-3.5 h-3.5" /></button>
                          <button onClick={e => { e.stopPropagation(); moveComponent(idx, 1); }} title="Move down" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#78716C' }}><ChevronDown className="w-3.5 h-3.5" /></button>
                          <button onClick={e => { e.stopPropagation(); duplicateComponent(comp.instanceId); }} title="Duplicate" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#78716C' }}><Copy className="w-3.5 h-3.5" /></button>
                          <button onClick={e => { e.stopPropagation(); removeComponent(comp.instanceId); }} title="Delete" style={{ padding: 3, borderRadius: 4, border: 'none', background: 'transparent', cursor: 'pointer', color: '#EF4444' }}><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                      )}
                      {/* Renderer */}
                      {Renderer ? <Renderer config={comp.config} theme={theme} /> : <div style={{ fontSize: 12, color: '#A8A29E' }}>[{comp.type}]</div>}
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
              <Field label="Image URL" value={selectedComp.config.url} onChange={v => updateConfig(selectedId, { url: v })} />
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
          </div>
        ) : (
          /* Document properties */
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
          </div>
        )}
      </div>
    </div>
  );
}

// --- Reusable form helpers ---

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
