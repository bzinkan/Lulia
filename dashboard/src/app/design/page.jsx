'use client';
import { useState, useEffect } from 'react';
import { Save, Eye, Sparkles, Plus, GripVertical, Trash2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';

const COMPONENT_LIBRARY = [
  { id: 'header', name: 'Header', category: 'Header', icon: '📝' },
  { id: 'name_date_line', name: 'Name/Date', category: 'Header', icon: '✏️' },
  { id: 'instructions_box', name: 'Instructions', category: 'Content', icon: '📋' },
  { id: 'multiple_choice', name: 'Multiple Choice', category: 'Question', icon: '🔘' },
  { id: 'fill_in_blank', name: 'Fill in Blank', category: 'Question', icon: '___' },
  { id: 'short_answer', name: 'Short Answer', category: 'Question', icon: '📝' },
  { id: 'long_answer', name: 'Long Answer', category: 'Question', icon: '📄' },
  { id: 'true_false', name: 'True/False', category: 'Question', icon: '✓✗' },
  { id: 'number_problem', name: 'Math Problem', category: 'Question', icon: '🔢' },
  { id: 'text_block', name: 'Text Block', category: 'Content', icon: '¶' },
  { id: 'word_bank', name: 'Word Bank', category: 'Content', icon: '📦' },
  { id: 'example_box', name: 'Example', category: 'Content', icon: '💡' },
  { id: 'image_placeholder', name: 'Image', category: 'Visual', icon: '🖼️' },
  { id: 'table', name: 'Table', category: 'Visual', icon: '📊' },
  { id: 'section_header', name: 'Section', category: 'Layout', icon: '—' },
  { id: 'divider', name: 'Divider', category: 'Layout', icon: '—' },
];

export default function DesignStudio() {
  const [templateName, setTemplateName] = useState('Untitled Template');
  const [canvas, setCanvas] = useState([]);
  const [selected, setSelected] = useState(null);
  const [previewHtml, setPreviewHtml] = useState(null);
  const [saving, setSaving] = useState(false);
  const [filling, setFilling] = useState(false);
  const [fillTopic, setFillTopic] = useState('');
  const [fillStandards, setFillStandards] = useState('');
  const [savedId, setSavedId] = useState(null);

  function addComponent(comp) {
    setCanvas(prev => [...prev, {
      ...comp, instanceId: `${comp.id}_${Date.now()}`,
      label: comp.name, content: null,
    }]);
  }

  function removeComponent(instanceId) {
    setCanvas(prev => prev.filter(c => c.instanceId !== instanceId));
    if (selected === instanceId) setSelected(null);
  }

  function moveComponent(index, direction) {
    setCanvas(prev => {
      const arr = [...prev];
      const newIndex = index + direction;
      if (newIndex < 0 || newIndex >= arr.length) return arr;
      [arr[index], arr[newIndex]] = [arr[newIndex], arr[index]];
      return arr;
    });
  }

  async function handleSave() {
    setSaving(true);
    try {
      const canvasJson = { name: templateName, components: canvas };
      if (savedId) {
        await apiFetch(`/api/v1/design/templates/${savedId}`, {
          method: 'PUT',
          body: JSON.stringify({ name: templateName, canvas_json: canvasJson }),
        });
      } else {
        const res = await apiFetch('/api/v1/design/templates', {
          method: 'POST',
          body: JSON.stringify({ name: templateName, canvas_json: canvasJson }),
        });
        setSavedId(res.template_id);
      }
    } catch (e) { alert(e.message); }
    finally { setSaving(false); }
  }

  async function handleAIFill() {
    if (!savedId) { await handleSave(); }
    setFilling(true);
    try {
      const res = await apiFetch(`/api/v1/design/templates/${savedId}/ai-fill`, {
        method: 'POST',
        body: JSON.stringify({
          topic: fillTopic, standards: fillStandards.split(',').map(s => s.trim()).filter(Boolean),
        }),
      });
      if (res.filled_canvas?.components) setCanvas(res.filled_canvas.components);
      if (res.preview_html) setPreviewHtml(res.preview_html);
    } catch (e) { alert(e.message); }
    finally { setFilling(false); }
  }

  return (
    <div style={{ display: 'flex', gap: 0, height: 'calc(100vh - 80px)', margin: '-24px' }}>
      {/* Left: Component Library */}
      <div style={{ width: 220, background: 'white', borderRight: '1px solid #E7E5E4', padding: 12, overflowY: 'auto' }}>
        <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, marginBottom: 8, color: '#1C1917' }}>Components</h3>
        {['Header', 'Question', 'Content', 'Visual', 'Layout'].map(cat => (
          <div key={cat} style={{ marginBottom: 12 }}>
            <p style={{ fontSize: 10, color: '#A8A29E', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>{cat}</p>
            {COMPONENT_LIBRARY.filter(c => c.category === cat).map(comp => (
              <button key={comp.id} onClick={() => addComponent(comp)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%', padding: '6px 8px', borderRadius: 8, border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 12, color: '#1C1917', textAlign: 'left', fontFamily: "'DM Sans'" }}
                onMouseEnter={e => e.currentTarget.style.background = '#FFF7ED'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <span style={{ fontSize: 14 }}>{comp.icon}</span> {comp.name}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* Center: Canvas */}
      <div style={{ flex: 1, background: '#F5DEC3', padding: 24, overflowY: 'auto', display: 'flex', justifyContent: 'center' }}>
        {previewHtml ? (
          <div style={{ width: 680, background: 'white', borderRadius: 14, overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: '#FEF9F2', borderBottom: '1px solid #E7E5E4' }}>
              <span style={{ fontSize: 11, color: '#78716C' }}>Preview</span>
              <button onClick={() => setPreviewHtml(null)} style={{ fontSize: 11, color: '#F97316', cursor: 'pointer', border: 'none', background: 'none' }}>Back to Editor</button>
            </div>
            <iframe srcDoc={previewHtml} style={{ width: '100%', minHeight: 800, border: 'none' }} />
          </div>
        ) : (
          <div style={{ width: 680, minHeight: 880, background: '#FEF9F2', borderRadius: 14, padding: 24, boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>
            {/* Template name */}
            <input value={templateName} onChange={e => setTemplateName(e.target.value)}
              style={{ width: '100%', border: 'none', background: 'transparent', fontFamily: "'DM Serif Display', serif", fontSize: 20, color: '#1C1917', outline: 'none', marginBottom: 16 }} />

            {canvas.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#A8A29E' }}>
                <Plus style={{ width: 32, height: 32, margin: '0 auto 8px', color: '#FDBA74' }} />
                <p style={{ fontSize: 13 }}>Drag components from the left panel to build your template</p>
              </div>
            ) : (
              canvas.map((comp, i) => (
                <div key={comp.instanceId}
                  onClick={() => setSelected(comp.instanceId)}
                  style={{
                    padding: 10, marginBottom: 8, borderRadius: 10,
                    border: selected === comp.instanceId ? '2px solid #F97316' : '1px solid #E7E5E4',
                    background: 'white', cursor: 'pointer', position: 'relative',
                  }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 14 }}>{comp.icon}</span>
                      <span style={{ fontSize: 12, fontWeight: 500, color: '#1C1917' }}>{comp.name}</span>
                      {comp.content && <span style={{ fontSize: 9, color: '#22C55E' }}>● filled</span>}
                    </div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={e => { e.stopPropagation(); moveComponent(i, -1); }} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 10, color: '#A8A29E' }}>▲</button>
                      <button onClick={e => { e.stopPropagation(); moveComponent(i, 1); }} style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: 10, color: '#A8A29E' }}>▼</button>
                      <button onClick={e => { e.stopPropagation(); removeComponent(comp.instanceId); }} style={{ border: 'none', background: 'none', cursor: 'pointer' }}><Trash2 style={{ width: 12, height: 12, color: '#EF4444' }} /></button>
                    </div>
                  </div>
                  {comp.content && (
                    <div style={{ marginTop: 6, fontSize: 11, color: '#78716C', maxHeight: 40, overflow: 'hidden' }}>
                      {typeof comp.content === 'string' ? comp.content : JSON.stringify(comp.content).slice(0, 80)}...
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Right: Properties + AI Fill */}
      <div style={{ width: 260, background: 'white', borderLeft: '1px solid #E7E5E4', padding: 12, overflowY: 'auto' }}>
        <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, marginBottom: 12, color: '#1C1917' }}>Actions</h3>

        <button onClick={handleSave} disabled={saving}
          style={{ width: '100%', background: 'white', color: '#78350F', border: '1px solid #E7E5E4', padding: '8px', borderRadius: 10, fontSize: 12, fontWeight: 500, cursor: 'pointer', marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontFamily: "'DM Sans'" }}>
          <Save style={{ width: 14, height: 14 }} /> {saving ? 'Saving...' : 'Save Template'}
        </button>

        <div style={{ marginTop: 16, borderTop: '1px solid #E7E5E4', paddingTop: 12 }}>
          <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, marginBottom: 8, color: '#F97316' }}>AI Fill</h3>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: '#78350F' }}>Topic</label>
            <input value={fillTopic} onChange={e => setFillTopic(e.target.value)} placeholder="e.g. Fractions"
              style={{ width: '100%', border: '1px solid #E7E5E4', borderRadius: 8, padding: '6px 10px', fontSize: 12, outline: 'none', fontFamily: "'DM Sans'" }} />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 10, fontWeight: 600, color: '#78350F' }}>Standards</label>
            <input value={fillStandards} onChange={e => setFillStandards(e.target.value)} placeholder="4.NF.1, 4.NF.2"
              style={{ width: '100%', border: '1px solid #E7E5E4', borderRadius: 8, padding: '6px 10px', fontSize: 12, outline: 'none', fontFamily: "'DM Sans'" }} />
          </div>
          <button onClick={handleAIFill} disabled={filling || canvas.length === 0}
            style={{ width: '100%', background: '#F97316', color: 'white', border: 'none', padding: '10px', borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontFamily: "'DM Sans'" }}>
            {filling ? <div style={{ width: 14, height: 14, border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> : <Sparkles style={{ width: 14, height: 14 }} />}
            {filling ? 'Filling...' : 'AI Fill'}
          </button>
        </div>

        {canvas.length > 0 && (
          <div style={{ marginTop: 16, fontSize: 10, color: '#A8A29E' }}>
            {canvas.length} components · {canvas.filter(c => c.content).length} filled
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
