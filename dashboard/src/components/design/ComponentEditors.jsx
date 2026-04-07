'use client';

import { useState, useRef, useCallback } from 'react';

/**
 * Specialist config editors for each component type.
 * Mirrors config keys used in ComponentRenderers.jsx.
 */

// ─── Style constants ──────────────────────────────────────────────────────────
const labelStyle = { display: 'block', fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 2 };
const inputStyle = { width: '100%', border: '1px solid #E7E5E4', borderRadius: 8, padding: '5px 8px', fontSize: 12, outline: 'none', fontFamily: "'DM Sans'" };
const sectionDivider = <div style={{ borderTop: '1px solid #F5F5F4', margin: '10px 0' }} />;

// ─── Field / Select helpers ───────────────────────────────────────────────────
function Field({ label, value, onChange, placeholder, multiline, type = 'text' }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={labelStyle}>{label}</label>
      {multiline ? (
        <textarea value={value ?? ''} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={3}
          style={{ ...inputStyle, resize: 'vertical' }} />
      ) : type === 'number' ? (
        <input type="number" value={value ?? ''} onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} placeholder={placeholder}
          style={inputStyle} />
      ) : (
        <input value={value ?? ''} onChange={e => onChange(e.target.value)} placeholder={placeholder}
          style={inputStyle} />
      )}
    </div>
  );
}

function Select({ label, value, options, onChange }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={labelStyle}>{label}</label>
      <select value={value || ''} onChange={e => onChange(e.target.value)}
        style={inputStyle}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

function Checkbox({ label, checked, onChange }) {
  return (
    <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
      <input type="checkbox" checked={!!checked} onChange={e => onChange(e.target.checked)} />
      <label style={{ fontSize: 11, fontWeight: 600, color: '#78350F' }}>{label}</label>
    </div>
  );
}

function ArrayField({ label, value, onChange, placeholder }) {
  const arr = Array.isArray(value) ? value : [];
  return (
    <Field
      label={label}
      value={arr.join(', ')}
      onChange={v => onChange(v.split(',').map(s => s.trim()).filter(Boolean))}
      placeholder={placeholder || 'item1, item2, item3'}
    />
  );
}

// ─── Math Symbol Toolbar ──────────────────────────────────────────────────────
const MATH_SYMBOLS = {
  Variables: ['x', 'y', 'z', 'n', 'a', 'b', 'c'],
  Operators: ['+', '\u2212', '\u00d7', '\u00f7', '=', '\u2260', '<', '>', '\u2264', '\u2265'],
  Symbols: ['\u03c0', '\u221a', '\u00b2', '\u00b3', '\u221e', '\u03a3', '\u222b', '\u2202', '\u0394', '\u03b8', '\u03b1', '\u03b2'],
  Fractions: ['\u00bd', '\u2153', '\u00bc', '\u2154', '\u00be'],
};

function MathToolbar({ onInsert }) {
  return (
    <div style={{ marginBottom: 10, padding: 8, background: '#FEF9F2', borderRadius: 8, border: '1px solid #FDBA74' }}>
      <div style={{ fontSize: 9, fontWeight: 600, color: '#78350F', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Math Symbols</div>
      {Object.entries(MATH_SYMBOLS).map(([group, symbols]) => (
        <div key={group} style={{ marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: '#A8A29E', marginRight: 4 }}>{group}:</span>
          {symbols.map((s, i) => (
            <button key={i} type="button" onClick={() => onInsert(s)}
              style={{ fontSize: 13, padding: '2px 7px', margin: '1px 2px', background: 'white', borderRadius: 4, border: '1px solid #E7E5E4', color: '#78350F', cursor: 'pointer', fontFamily: 'serif', lineHeight: 1.3 }}>
              {s}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── Helper: insert symbol at cursor in the active input ──────────────────────
function useMathInsert(onUpdate) {
  const activeFieldRef = useRef(null);

  const handleInsert = useCallback((symbol) => {
    const el = activeFieldRef.current;
    if (el && el.tagName && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      const val = el.value;
      const newVal = val.slice(0, start) + symbol + val.slice(end);
      // Figure out which config key this field maps to via the data attribute
      const key = el.dataset.configKey;
      if (key) {
        onUpdate({ [key]: newVal });
        // Restore cursor after React re-render
        requestAnimationFrame(() => {
          el.focus();
          const pos = start + symbol.length;
          el.setSelectionRange(pos, pos);
        });
      }
    }
  }, [onUpdate]);

  const trackFocus = useCallback((e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      activeFieldRef.current = e.target;
    }
  }, []);

  return { handleInsert, trackFocus };
}

// ─── Math-aware Field (sets data-config-key for symbol insertion) ─────────────
function MathField({ label, configKey, value, onUpdate, placeholder, multiline }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={labelStyle}>{label}</label>
      {multiline ? (
        <textarea data-config-key={configKey} value={value ?? ''} onChange={e => onUpdate({ [configKey]: e.target.value })} placeholder={placeholder} rows={3}
          style={{ ...inputStyle, resize: 'vertical' }} />
      ) : (
        <input data-config-key={configKey} value={value ?? ''} onChange={e => onUpdate({ [configKey]: e.target.value })} placeholder={placeholder}
          style={inputStyle} />
      )}
    </div>
  );
}

// ─── Size selector ────────────────────────────────────────────────────────────
function SizeSelect({ value, onUpdate, configKey = 'size' }) {
  return (
    <Select label="Size" value={value} options={[['small', 'Small'], ['medium', 'Medium'], ['large', 'Large']]}
      onChange={v => onUpdate({ [configKey]: v })} />
  );
}

// ─── Math component types ─────────────────────────────────────────────────────
const MATH_TYPES = new Set([
  'equation_editor', 'system_of_equations', 'limit_expression', 'integral_derivative',
  'piecewise_function', 'series_summation', 'inequality_number_line', 'kinematics_equations',
  'chemical_equation_balancer',
]);

// ─── Grid/Graph range editor ──────────────────────────────────────────────────
function GridRangeEditor({ config, onUpdate }) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <Field label="X Min" type="number" value={config.xMin} onChange={v => onUpdate({ xMin: v })} />
        <Field label="X Max" type="number" value={config.xMax} onChange={v => onUpdate({ xMax: v })} />
        <Field label="Y Min" type="number" value={config.yMin} onChange={v => onUpdate({ yMin: v })} />
        <Field label="Y Max" type="number" value={config.yMax} onChange={v => onUpdate({ yMax: v })} />
      </div>
      <Field label="Grid Interval" type="number" value={config.interval ?? config.gridLines} onChange={v => onUpdate({ interval: v })} />
      <Checkbox label="Show Gridlines" checked={config.showGridlines ?? true} onChange={v => onUpdate({ showGridlines: v })} />
      <Checkbox label="Show Labels" checked={config.showLabels ?? true} onChange={v => onUpdate({ showLabels: v })} />
    </>
  );
}

// ─── Table editor helper ──────────────────────────────────────────────────────
function TableEditor({ config, onUpdate, hasRowHeaders = false }) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <Field label="Rows" type="number" value={config.rows} onChange={v => onUpdate({ rows: v })} />
        <Field label="Columns" type="number" value={config.cols} onChange={v => onUpdate({ cols: v })} />
      </div>
      <ArrayField label="Column Headers" value={config.headers || config.colHeaders} onChange={v => onUpdate({ headers: v })} />
      {hasRowHeaders && (
        <ArrayField label="Row Headers" value={config.rowHeaders} onChange={v => onUpdate({ rowHeaders: v })} />
      )}
    </>
  );
}

// ─── Per-type editor map ──────────────────────────────────────────────────────
const EDITORS = {
  // ── Math ──────────────────────────────────────────────────────────────────
  equation_editor: (config, onUpdate) => (
    <>
      <MathField label="Equation" configKey="equation" value={config.equation} onUpdate={onUpdate} placeholder="y = mx + b" />
    </>
  ),

  system_of_equations: (config, onUpdate) => (
    <>
      <MathField label="Equations (one per line)" configKey="equations"
        value={Array.isArray(config.equations) ? config.equations.join('\n') : config.equations}
        onUpdate={v => onUpdate({ equations: (v.equations || '').split('\n').filter(Boolean) })}
        placeholder="2x + 3y = 12" multiline />
    </>
  ),

  limit_expression: (config, onUpdate) => (
    <>
      <MathField label="Variable" configKey="variable" value={config.variable} onUpdate={onUpdate} placeholder="x" />
      <MathField label="Approaching" configKey="approaching" value={config.approaching} onUpdate={onUpdate} placeholder="\u221e" />
      <MathField label="Expression" configKey="expression" value={config.expression} onUpdate={onUpdate} placeholder="f(x)" />
    </>
  ),

  integral_derivative: (config, onUpdate) => (
    <>
      <Select label="Type" value={config.type || 'integral'} options={[['integral', 'Integral'], ['derivative', 'Derivative']]}
        onChange={v => onUpdate({ type: v })} />
      <MathField label="Expression" configKey="expression" value={config.expression} onUpdate={onUpdate} placeholder="f(x) dx" />
      <MathField label="Variable" configKey="variable" value={config.variable} onUpdate={onUpdate} placeholder="x" />
      {(config.type || 'integral') === 'integral' && (
        <>
          <MathField label="Upper Bound" configKey="upper" value={config.upper} onUpdate={onUpdate} placeholder="b" />
          <MathField label="Lower Bound" configKey="lower" value={config.lower} onUpdate={onUpdate} placeholder="a" />
        </>
      )}
    </>
  ),

  piecewise_function: (config, onUpdate) => {
    const pieces = config.pieces || [{ expression: '', condition: '' }];
    return (
      <>
        {pieces.map((p, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 4 }}>
            <MathField label={`Piece ${i + 1} Expr`} configKey={`_piece_expr_${i}`} value={p.expression}
              onUpdate={() => {}} placeholder="x + 1" />
            <MathField label="Condition" configKey={`_piece_cond_${i}`} value={p.condition}
              onUpdate={() => {}} placeholder="x < 0" />
          </div>
        ))}
        <div style={{ fontSize: 10, color: '#A8A29E', marginBottom: 6 }}>
          Edit pieces as JSON array or use the fields above.
        </div>
        <Field label="Pieces (JSON)" value={JSON.stringify(pieces, null, 2)} multiline
          onChange={v => { try { onUpdate({ pieces: JSON.parse(v) }); } catch {} }} />
      </>
    );
  },

  series_summation: (config, onUpdate) => (
    <>
      <MathField label="Upper Bound" configKey="upper" value={config.upper} onUpdate={onUpdate} placeholder="n" />
      <MathField label="Lower Bound" configKey="lower" value={config.lower} onUpdate={onUpdate} placeholder="i=1" />
      <MathField label="Expression" configKey="expression" value={config.expression} onUpdate={onUpdate} placeholder="a_i" />
    </>
  ),

  inequality_number_line: (config, onUpdate) => (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <Field label="Min" type="number" value={config.min} onChange={v => onUpdate({ min: v })} />
        <Field label="Max" type="number" value={config.max} onChange={v => onUpdate({ max: v })} />
      </div>
    </>
  ),

  kinematics_equations: (config, onUpdate) => (
    <>
      <Field label="Equations (one per line)" value={Array.isArray(config.equations) ? config.equations.join('\n') : ''} multiline
        onChange={v => onUpdate({ equations: v.split('\n').filter(Boolean) })} placeholder="v = v\u2080 + at" />
    </>
  ),

  chemical_equation_balancer: (config, onUpdate) => (
    <>
      <MathField label="Equation" configKey="equation" value={config.equation} onUpdate={onUpdate} placeholder="___ H\u2082 + ___ O\u2082 \u2192 ___ H\u2082O" />
    </>
  ),

  // ── Additional math types ─────────────────────────────────────────────────
  fraction_visual: (config, onUpdate) => (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <Field label="Numerator" type="number" value={config.numerator} onChange={v => onUpdate({ numerator: v })} />
        <Field label="Denominator" type="number" value={config.denominator} onChange={v => onUpdate({ denominator: v })} />
      </div>
      <Select label="Visual Type" value={config.type || 'circle'} options={[['circle', 'Circle'], ['bar', 'Bar']]}
        onChange={v => onUpdate({ type: v })} />
    </>
  ),

  multiplication_grid: (config, onUpdate) => (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <Field label="Factor A" type="number" value={config.a} onChange={v => onUpdate({ a: v })} />
        <Field label="Factor B" type="number" value={config.b} onChange={v => onUpdate({ b: v })} />
      </div>
    </>
  ),

  number_line: (config, onUpdate) => (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
        <Field label="Min" type="number" value={config.min} onChange={v => onUpdate({ min: v })} />
        <Field label="Max" type="number" value={config.max} onChange={v => onUpdate({ max: v })} />
        <Field label="Interval" type="number" value={config.interval} onChange={v => onUpdate({ interval: v })} />
      </div>
    </>
  ),

  // ── Grid / Graph ──────────────────────────────────────────────────────────
  coordinate_plane: (config, onUpdate) => {
    const equations = config.equations || [];
    function updateEq(idx, key, val) {
      const eqs = [...equations];
      eqs[idx] = { ...eqs[idx], [key]: val };
      onUpdate({ equations: eqs });
    }
    function addEq() { onUpdate({ equations: [...equations, { expr: '', label: 'f(x)' }] }); }
    function removeEq(idx) { onUpdate({ equations: equations.filter((_, i) => i !== idx) }); }
    return (
      <>
        <Field label="Size (px)" type="number" value={config.size} onChange={v => onUpdate({ size: v })} placeholder="260" />
        <GridRangeEditor config={config} onUpdate={onUpdate} />
        <div style={{ borderTop: '1px solid #E7E5E4', paddingTop: 8, marginTop: 8, marginBottom: 4 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#F97316', marginBottom: 6 }}>Equations</div>
          {equations.map((eq, i) => (
            <div key={i} style={{ display: 'flex', gap: 4, marginBottom: 4, alignItems: 'center' }}>
              <input value={eq.label || ''} onChange={e => updateEq(i, 'label', e.target.value)} placeholder="f(x)"
                style={{ width: 40, border: '1px solid #E7E5E4', borderRadius: 6, padding: '3px 4px', fontSize: 10, fontFamily: 'monospace', outline: 'none' }} />
              <span style={{ fontSize: 10, color: '#78716C' }}>=</span>
              <input value={eq.expr || ''} onChange={e => updateEq(i, 'expr', e.target.value)} placeholder="2x + 1"
                style={{ flex: 1, border: '1px solid #E7E5E4', borderRadius: 6, padding: '3px 6px', fontSize: 10, fontFamily: 'monospace', outline: 'none' }} />
              <button onClick={() => removeEq(i)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#EF4444', fontSize: 12, padding: 0 }}>×</button>
            </div>
          ))}
          <button onClick={addEq} style={{ fontSize: 10, color: '#F97316', border: '1px dashed #FDBA74', background: '#FFF7ED', borderRadius: 6, padding: '3px 8px', cursor: 'pointer', width: '100%', fontFamily: "'DM Sans'" }}>
            + Add equation
          </button>
          <div style={{ fontSize: 9, color: '#A8A29E', marginTop: 4 }}>
            Use x as variable. Examples: 2x+1, x^2, 0.5x-3, x^3-2x
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
            <input type="checkbox" checked={config.showAnswer !== false} onChange={e => onUpdate({ showAnswer: e.target.checked })} />
            <span style={{ fontSize: 10, color: '#78350F', fontWeight: 600 }}>Show graph lines (Answer Key)</span>
          </div>
          <div style={{ fontSize: 9, color: '#A8A29E', marginTop: 2 }}>
            Uncheck to print a blank grid with equations listed. Students plot the lines themselves.
          </div>
        </div>
      </>
    );
  },

  geometry_canvas: (config, onUpdate) => {
    const shapes = config.shapes || [];
    const SHAPE_TYPES = [
      { value: 'triangle', label: '△ Triangle' },
      { value: 'rectangle', label: '▭ Rectangle' },
      { value: 'circle', label: '○ Circle' },
      { value: 'line_segment', label: '— Line Segment' },
      { value: 'angle', label: '∠ Angle' },
    ];
    function addShape(type) {
      const defaults = {
        triangle: { type: 'triangle', variant: 'scalene', x: 140, y: 100, size: 80, color: '#F97316', showAngles: true, showSides: true, label: '' },
        rectangle: { type: 'rectangle', x: 60, y: 50, width: 120, height: 80, color: '#2563EB', showDimensions: true, label: '' },
        circle: { type: 'circle', x: 140, y: 110, radius: 50, color: '#059669', showRadius: true, showCenter: true, showDiameter: false, showChord: false, showCircumference: false, showArea: false, sectorAngle: 0, label: '' },
        line_segment: { type: 'line_segment', x1: 40, y1: 140, x2: 220, y2: 60, color: '#7C3AED', label: '' },
        angle: { type: 'angle', x: 100, y: 140, size: 60, degrees: 45, color: '#E11D48', degreeLabel: '' },
      };
      onUpdate({ shapes: [...shapes, defaults[type] || { type }] });
    }
    function updateShape(idx, key, val) {
      const s = [...shapes];
      s[idx] = { ...s[idx], [key]: val };
      onUpdate({ shapes: s });
    }
    function removeShape(idx) { onUpdate({ shapes: shapes.filter((_, i) => i !== idx) }); }
    return (
      <>
        <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="e.g. Find the area" />
        <Field label="Canvas Size (px)" type="number" value={config.size} onChange={v => onUpdate({ size: v })} placeholder="280" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <input type="checkbox" checked={config.showGrid !== false} onChange={e => onUpdate({ showGrid: e.target.checked })} />
          <span style={{ fontSize: 10, color: '#78350F' }}>Show Grid</span>
          <input type="checkbox" checked={config.showFormulas !== false} onChange={e => onUpdate({ showFormulas: e.target.checked })} style={{ marginLeft: 8 }} />
          <span style={{ fontSize: 10, color: '#78350F' }}>Show Formulas</span>
        </div>
        <div style={{ borderTop: '1px solid #E7E5E4', paddingTop: 8, marginTop: 4 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#F97316', marginBottom: 6 }}>Shapes</div>
          <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', marginBottom: 8 }}>
            {SHAPE_TYPES.map(s => (
              <button key={s.value} onClick={() => addShape(s.value)}
                style={{ fontSize: 9, padding: '3px 6px', borderRadius: 6, border: '1px solid #E7E5E4', background: 'white', cursor: 'pointer', fontFamily: "'DM Sans'" }}>
                {s.label}
              </button>
            ))}
          </div>
          {shapes.map((shape, i) => (
            <div key={i} style={{ border: '1px solid #E7E5E4', borderRadius: 8, padding: 6, marginBottom: 6, background: '#FAFAF9' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 10, fontWeight: 600, color: '#78350F' }}>{shape.type}</span>
                <button onClick={() => removeShape(i)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#EF4444', fontSize: 11, padding: 0 }}>×</button>
              </div>
              <Field label="Label" value={shape.label} onChange={v => updateShape(i, 'label', v)} placeholder="e.g. △ABC" />
              {shape.type === 'triangle' && <>
                <div style={{ marginBottom: 4 }}>
                  <label style={{ display: 'block', fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 2 }}>Type</label>
                  <select value={shape.variant || 'scalene'} onChange={e => updateShape(i, 'variant', e.target.value)}
                    style={{ width: '100%', border: '1px solid #E7E5E4', borderRadius: 8, padding: '4px 8px', fontSize: 11, outline: 'none', fontFamily: "'DM Sans'" }}>
                    <option value="scalene">Scalene</option>
                    <option value="right">Right Triangle (90°)</option>
                    <option value="isosceles">Isosceles</option>
                    <option value="equilateral">Equilateral</option>
                  </select>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  <Field label="Side a" value={shape.sideA} onChange={v => updateShape(i, 'sideA', v)} placeholder="5 cm" />
                  <Field label="Side b" value={shape.sideB} onChange={v => updateShape(i, 'sideB', v)} placeholder="12 cm" />
                  <Field label="Side c" value={shape.sideC} onChange={v => updateShape(i, 'sideC', v)} placeholder="13 cm" />
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  <Field label="∠A" value={shape.angleA} onChange={v => updateShape(i, 'angleA', v)} placeholder={shape.variant === 'right' ? '' : '60°'} />
                  <Field label="∠B" value={shape.angleB} onChange={v => updateShape(i, 'angleB', v)} placeholder={shape.variant === 'right' ? '90°' : '70°'} />
                  <Field label="∠C" value={shape.angleC} onChange={v => updateShape(i, 'angleC', v)} placeholder="50°" />
                </div>
                <Field label="Size" type="number" value={shape.size} onChange={v => updateShape(i, 'size', v)} />
                <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                  <label style={{ fontSize: 9, color: '#78716C', display: 'flex', alignItems: 'center', gap: 3 }}>
                    <input type="checkbox" checked={shape.showSides !== false} onChange={e => updateShape(i, 'showSides', e.target.checked)} /> Sides
                  </label>
                  <label style={{ fontSize: 9, color: '#78716C', display: 'flex', alignItems: 'center', gap: 3 }}>
                    <input type="checkbox" checked={shape.showAngles !== false} onChange={e => updateShape(i, 'showAngles', e.target.checked)} /> Angles
                  </label>
                </div>
              </>}
              {shape.type === 'rectangle' && <>
                <div style={{ display: 'flex', gap: 4 }}>
                  <Field label="Width label" value={shape.widthLabel} onChange={v => updateShape(i, 'widthLabel', v)} placeholder="12 cm" />
                  <Field label="Height label" value={shape.heightLabel} onChange={v => updateShape(i, 'heightLabel', v)} placeholder="8 cm" />
                </div>
              </>}
              {shape.type === 'circle' && <>
                <Field label="Radius label" value={shape.radiusLabel} onChange={v => updateShape(i, 'radiusLabel', v)} placeholder="5 cm" />
                <Field label="Diameter label" value={shape.diameterLabel} onChange={v => updateShape(i, 'diameterLabel', v)} placeholder="10 cm" />
                <Field label="Radius (px)" type="number" value={shape.radius} onChange={v => updateShape(i, 'radius', v)} />
                <Field label="Sector Angle (°)" type="number" value={shape.sectorAngle} onChange={v => updateShape(i, 'sectorAngle', v)} placeholder="0 = no sector" />
                <Field label="Sector label" value={shape.sectorLabel} onChange={v => updateShape(i, 'sectorLabel', v)} placeholder="90°" />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                  {[
                    ['showCenter', 'Center'],
                    ['showRadius', 'Radius'],
                    ['showDiameter', 'Diameter'],
                    ['showChord', 'Chord'],
                    ['showCircumference', 'C = 2πr'],
                    ['showArea', 'A = πr²'],
                  ].map(([key, lbl]) => (
                    <label key={key} style={{ fontSize: 9, color: '#78716C', display: 'flex', alignItems: 'center', gap: 3 }}>
                      <input type="checkbox" checked={!!shape[key]} onChange={e => updateShape(i, key, e.target.checked)} /> {lbl}
                    </label>
                  ))}
                </div>
              </>}
              {shape.type === 'angle' && <>
                <Field label="Degrees" type="number" value={shape.degrees} onChange={v => updateShape(i, 'degrees', v)} placeholder="45" />
                <Field label="Degree label" value={shape.degreeLabel} onChange={v => updateShape(i, 'degreeLabel', v)} placeholder="45°" />
              </>}
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <span style={{ fontSize: 9, color: '#78350F' }}>Color:</span>
                <input type="color" value={shape.color || '#F97316'} onChange={e => updateShape(i, 'color', e.target.value)} style={{ width: 20, height: 20, border: 'none', cursor: 'pointer' }} />
              </div>
            </div>
          ))}
        </div>
      </>
    );
  },

  transformation_grid: (config, onUpdate) => (
    <>
      <GridRangeEditor config={config} onUpdate={onUpdate} />
    </>
  ),

  graph_grid: (config, onUpdate) => (
    <>
      <GridRangeEditor config={config} onUpdate={onUpdate} />
    </>
  ),

  distribution_curve: (config, onUpdate) => (
    <>
      <Field label="X-Axis Label" value={config.xLabel} onChange={v => onUpdate({ xLabel: v })} placeholder="x" />
      <Field label="Y-Axis Label" value={config.yLabel} onChange={v => onUpdate({ yLabel: v })} placeholder="f(x)" />
    </>
  ),

  supply_demand_graph: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} />
    </>
  ),

  economic_model: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Economic Model" />
      <Field label="X-Axis Label" value={config.xLabel} onChange={v => onUpdate({ xLabel: v })} placeholder="Variable X" />
    </>
  ),

  // ── Table / Chart components ──────────────────────────────────────────────
  function_table: (config, onUpdate) => (
    <>
      <ArrayField label="Input Values" value={config.inputs} onChange={v => onUpdate({ inputs: v })} placeholder="x, 1, 2, 3, 4" />
      <ArrayField label="Output Values" value={config.outputs} onChange={v => onUpdate({ outputs: v })} placeholder="f(x), , , , " />
    </>
  ),

  two_way_table: (config, onUpdate) => (
    <>
      <ArrayField label="Row Headers" value={config.rowHeaders} onChange={v => onUpdate({ rowHeaders: v })} placeholder="Category A, Category B" />
      <ArrayField label="Column Headers" value={config.colHeaders} onChange={v => onUpdate({ colHeaders: v })} placeholder="Yes, No, Total" />
    </>
  ),

  data_collection_table: (config, onUpdate) => (
    <>
      <Field label="Rows" type="number" value={config.rows} onChange={v => onUpdate({ rows: v })} placeholder="5" />
      <ArrayField label="Column Headers" value={config.headers} onChange={v => onUpdate({ headers: v })} placeholder="Trial, Observation, Measurement, Notes" />
    </>
  ),

  comparison_chart: (config, onUpdate) => (
    <>
      <ArrayField label="Items" value={config.items} onChange={v => onUpdate({ items: v })} placeholder="Item A, Item B" />
      <ArrayField label="Criteria" value={config.criteria} onChange={v => onUpdate({ criteria: v })} placeholder="Feature 1, Feature 2, Feature 3" />
    </>
  ),

  place_value_chart: (config, onUpdate) => (
    <>
      <ArrayField label="Places" value={config.places} onChange={v => onUpdate({ places: v })} placeholder="Thousands, Hundreds, Tens, Ones" />
    </>
  ),

  conjugation_table: (config, onUpdate) => (
    <>
      <Field label="Verb" value={config.verb} onChange={v => onUpdate({ verb: v })} placeholder="hablar" />
      <ArrayField label="Pronouns" value={config.pronouns} onChange={v => onUpdate({ pronouns: v })} placeholder="yo, tu, el/ella, nosotros, vosotros, ellos" />
    </>
  ),

  conversion_table: (config, onUpdate) => (
    <>
      <Field label="Rows" type="number" value={config.rows} onChange={v => onUpdate({ rows: v })} placeholder="4" />
      <ArrayField label="Column Headers" value={config.headers} onChange={v => onUpdate({ headers: v })} placeholder="Unit, Equivalent" />
    </>
  ),

  cause_effect_chart: (config, onUpdate) => (
    <>
      <Field label="Rows" type="number" value={config.rows} onChange={v => onUpdate({ rows: v })} placeholder="3" />
    </>
  ),

  design_elements_chart: (config, onUpdate) => (
    <>
      <ArrayField label="Elements" value={config.elements} onChange={v => onUpdate({ elements: v })} placeholder="Line, Shape, Color, Texture, Space" />
    </>
  ),

  materials_table: (config, onUpdate) => (
    <>
      <Field label="Rows" type="number" value={config.rows} onChange={v => onUpdate({ rows: v })} placeholder="4" />
      <ArrayField label="Column Headers" value={config.headers} onChange={v => onUpdate({ headers: v })} placeholder="Material, Quantity, Purpose" />
    </>
  ),

  trace_table: (config, onUpdate) => (
    <>
      <Field label="Rows" type="number" value={config.rows} onChange={v => onUpdate({ rows: v })} placeholder="5" />
      <ArrayField label="Variables" value={config.variables} onChange={v => onUpdate({ variables: v })} placeholder="Step, x, y, Output" />
    </>
  ),

  declension_table: (config, onUpdate) => (
    <>
      <ArrayField label="Cases" value={config.cases} onChange={v => onUpdate({ cases: v })} placeholder="Nominative, Genitive, Dative, Accusative" />
      <ArrayField label="Genders" value={config.genders} onChange={v => onUpdate({ genders: v })} placeholder="Masculine, Feminine, Neuter" />
    </>
  ),

  case_table: (config, onUpdate) => (
    <>
      <ArrayField label="Cases" value={config.cases} onChange={v => onUpdate({ cases: v })} placeholder="Nominative, Accusative, Genitive, Dative, Ablative" />
      <ArrayField label="Numbers" value={config.numbers} onChange={v => onUpdate({ numbers: v })} placeholder="Singular, Plural" />
    </>
  ),

  periodic_table_ref: (config, onUpdate) => (
    <>
      <Field label="Elements (JSON)" value={JSON.stringify(config.elements || [], null, 2)} multiline
        onChange={v => { try { onUpdate({ elements: JSON.parse(v) }); } catch {} }} placeholder='[{"symbol":"H","number":1,"name":"Hydrogen"}]' />
    </>
  ),

  // ── Writing / Workspace ───────────────────────────────────────────────────
  work_space_grid: (config, onUpdate) => (
    <>
      <Field label="Height (px)" type="number" value={config.height} onChange={v => onUpdate({ height: v })} placeholder="120" />
    </>
  ),

  handwriting_lines: (config, onUpdate) => (
    <>
      <Field label="Lines" type="number" value={config.lines} onChange={v => onUpdate({ lines: v })} placeholder="4" />
    </>
  ),

  sketch_space: (config, onUpdate) => (
    <>
      <Field label="Prompt" value={config.prompt} onChange={v => onUpdate({ prompt: v })} placeholder="Sketch / Draw Here" />
      <Field label="Height (px)" type="number" value={config.height} onChange={v => onUpdate({ height: v })} placeholder="180" />
    </>
  ),

  construction_space: (config, onUpdate) => (
    <>
      <Field label="Height (px)" type="number" value={config.height} onChange={v => onUpdate({ height: v })} placeholder="200" />
    </>
  ),

  technical_drawing_space: (config, onUpdate) => (
    <>
      <Field label="Height (px)" type="number" value={config.height} onChange={v => onUpdate({ height: v })} placeholder="200" />
      <Field label="Scale" value={config.scale} onChange={v => onUpdate({ scale: v })} placeholder="1:1" />
    </>
  ),

  molar_calc_space: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Molar Calculation Space" />
    </>
  ),

  lab_report: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Lab Report" />
      <ArrayField label="Sections" value={config.sections} onChange={v => onUpdate({ sections: v })}
        placeholder="Purpose, Hypothesis, Materials, Procedure, Data / Observations, Analysis, Conclusion" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  observation_box: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Observations" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  writing_prompt: (config, onUpdate) => (
    <>
      <Field label="Prompt" value={config.prompt} onChange={v => onUpdate({ prompt: v })} multiline placeholder="Write about a time when..." />
      <Field label="Lines" type="number" value={config.lines} onChange={v => onUpdate({ lines: v })} placeholder="8" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  essay_prompt_wl: (config, onUpdate) => (
    <>
      <Field label="Prompt" value={config.prompt} onChange={v => onUpdate({ prompt: v })} multiline placeholder="Discuss the significance of..." />
      <Field label="Lines" type="number" value={config.lines} onChange={v => onUpdate({ lines: v })} placeholder="12" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  reflection_journal: (config, onUpdate) => (
    <>
      <Field label="Prompt 1" value={config.prompt1} onChange={v => onUpdate({ prompt1: v })} placeholder="What I learned..." />
      <Field label="Prompt 2" value={config.prompt2} onChange={v => onUpdate({ prompt2: v })} placeholder="How I can apply this..." />
      <Field label="Prompt 3" value={config.prompt3} onChange={v => onUpdate({ prompt3: v })} placeholder="Questions I still have..." />
    </>
  ),

  portfolio_reflection: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Portfolio Reflection" />
    </>
  ),

  // ── Science diagrams ──────────────────────────────────────────────────────
  punnett_square: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Punnett Square" />
      <ArrayField label="Parent 1 Alleles" value={config.parent1} onChange={v => onUpdate({ parent1: v })} placeholder="P, p" />
      <ArrayField label="Parent 2 Alleles" value={config.parent2} onChange={v => onUpdate({ parent2: v })} placeholder="P, p" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  cell_diagram: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Cell Diagram" />
      <Select label="Cell Type" value={config.type || 'animal'} options={[['animal', 'Animal'], ['plant', 'Plant']]}
        onChange={v => onUpdate({ type: v })} />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  dna_rna_sequence: (config, onUpdate) => (
    <>
      <Field label="Label" value={config.label} onChange={v => onUpdate({ label: v })} placeholder="DNA Strand" />
      <Field label="Sequence (space-separated bases)" value={config.sequence} onChange={v => onUpdate({ sequence: v })} placeholder="A T G C C G A T" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  phylogenetic_tree: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Phylogenetic Tree" />
      <ArrayField label="Species" value={config.species} onChange={v => onUpdate({ species: v })} placeholder="Species A, Species B, Species C, Species D" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  lewis_dot: (config, onUpdate) => (
    <>
      <Field label="Element Symbol" value={config.element} onChange={v => onUpdate({ element: v })} placeholder="O" />
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Lewis Dot Structure" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  electron_config: (config, onUpdate) => (
    <>
      <Field label="Element Name" value={config.element} onChange={v => onUpdate({ element: v })} placeholder="Carbon" />
      <ArrayField label="Shells" value={config.shells} onChange={v => onUpdate({ shells: v })} placeholder="1s\u00b2, 2s\u00b2, 2p\u00b2" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  free_body_diagram: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Free Body Diagram" />
      <Field label="Top Label" value={config.topLabel} onChange={v => onUpdate({ topLabel: v })} placeholder="F_N" />
      <Field label="Bottom Label" value={config.bottomLabel} onChange={v => onUpdate({ bottomLabel: v })} placeholder="F_g" />
      <Field label="Left Label" value={config.leftLabel} onChange={v => onUpdate({ leftLabel: v })} placeholder="F_f" />
      <Field label="Right Label" value={config.rightLabel} onChange={v => onUpdate({ rightLabel: v })} placeholder="F_a" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  circuit_diagram: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Circuit Diagram" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  vector_diagram: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Vector Diagram" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  diagram_label: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Label the Diagram" />
      <ArrayField label="Labels" value={config.labels} onChange={v => onUpdate({ labels: v })} placeholder="Part A, Part B, Part C, Part D" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  science_graphic_organizer: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Science Graphic Organizer" />
      <Field label="Section 1" value={config.section1} onChange={v => onUpdate({ section1: v })} placeholder="Observation" />
      <Field label="Section 2" value={config.section2} onChange={v => onUpdate({ section2: v })} placeholder="Hypothesis" />
      <Field label="Section 3" value={config.section3} onChange={v => onUpdate({ section3: v })} placeholder="Evidence" />
      <Field label="Section 4" value={config.section4} onChange={v => onUpdate({ section4: v })} placeholder="Conclusion" />
    </>
  ),

  body_diagram: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Body Diagram" />
      <ArrayField label="Labels" value={config.labels} onChange={v => onUpdate({ labels: v })} placeholder="Head, Torso, Arms, Legs" />
      <SizeSelect value={config.size} onUpdate={onUpdate} />
    </>
  ),

  // ── Analysis frames ───────────────────────────────────────────────────────
  text_evidence_chart: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Text Evidence" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  literary_analysis_frame: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Literary Analysis" />
      <ArrayField label="Section Labels" value={config.sections} onChange={v => onUpdate({ sections: v })}
        placeholder="Theme / Central Idea, Literary Device Used, Textual Evidence (quote), Analysis / Explanation" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  rhetorical_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Rhetorical Analysis" />
      <ArrayField label="Section Labels" value={config.sections} onChange={v => onUpdate({ sections: v })}
        placeholder="Speaker / Author, Audience, Purpose, Ethos / Pathos / Logos, Effectiveness" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  argument_outline: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Argument Outline" />
      <ArrayField label="Section Labels" value={config.sections} onChange={v => onUpdate({ sections: v })}
        placeholder="Thesis / Claim, Reason 1 + Evidence, Counterargument, Rebuttal, Conclusion" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  synthesis_source_chart: (config, onUpdate) => (
    <>
      <Field label="Sources Count" type="number" value={config.sources} onChange={v => onUpdate({ sources: v })} placeholder="3" />
    </>
  ),

  close_reading_guide: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Close Reading Guide" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  poetry_annotation: (config, onUpdate) => (
    <>
      <Field label="Poem Text" value={config.poem} onChange={v => onUpdate({ poem: v })} multiline placeholder="Paste poem text here for annotation..." />
    </>
  ),

  reading_comprehension_wl: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Reading Comprehension" />
    </>
  ),

  primary_source_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Primary Source Analysis" />
      <ArrayField label="Section Labels" value={config.sections} onChange={v => onUpdate({ sections: v })}
        placeholder="Source Type & Date, Author / Creator, Historical Context, Main Idea / Purpose, Point of View / Bias, Significance" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  dbq_document_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="DBQ Document Analysis" />
      <ArrayField label="Section Labels" value={config.sections} onChange={v => onUpdate({ sections: v })}
        placeholder="Document Title / Source, Historical Context, Intended Audience, Purpose, Point of View" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  amendment_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Amendment Analysis" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  court_case_brief: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Court Case Brief" />
      <ArrayField label="Section Labels" value={config.sections} onChange={v => onUpdate({ sections: v })}
        placeholder="Case Name & Year, Facts of the Case, Constitutional Question, Decision, Significance" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  policy_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Policy Analysis" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  scotus_comparison: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="SCOTUS Case Comparison" />
    </>
  ),

  leq_outline: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="LEQ Outline" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  ccot_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Continuity & Change Over Time" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  character_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Character Analysis" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  art_critique_guide: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Art Critique" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  contextual_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Contextual Analysis" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  artwork_comparison: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Artwork Comparison" />
    </>
  ),

  cultural_comparison: (config, onUpdate) => (
    <>
      <Field label="Culture 1" value={config.culture1} onChange={v => onUpdate({ culture1: v })} placeholder="Culture 1" />
      <Field label="Culture 2" value={config.culture2} onChange={v => onUpdate({ culture2: v })} placeholder="Culture 2" />
      <ArrayField label="Aspects" value={config.aspects} onChange={v => onUpdate({ aspects: v })} placeholder="Language, Customs, Values, Traditions" />
    </>
  ),

  wellness_assessment: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Wellness Assessment" />
    </>
  ),

  decision_making_model: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Decision Making Model" />
    </>
  ),

  stress_management_plan: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Stress Management Plan" />
    </>
  ),

  swot_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="SWOT Analysis" />
    </>
  ),

  cost_benefit_analysis: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Cost-Benefit Analysis" />
    </>
  ),

  business_plan_section: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Business Plan" />
      <Field label="Instructions" value={config.instructions} onChange={v => onUpdate({ instructions: v })} multiline />
    </>
  ),

  // ── Music / Creative ──────────────────────────────────────────────────────
  music_staff: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Music Staff" />
      <Field label="Number of Staves" type="number" value={config.staves} onChange={v => onUpdate({ staves: v })} placeholder="2" />
    </>
  ),

  rhythm_notation: (config, onUpdate) => (
    <>
      <Field label="Time Signature" value={config.timeSignature} onChange={v => onUpdate({ timeSignature: v })} placeholder="4/4" />
      <Field label="Beats" type="number" value={config.beats} onChange={v => onUpdate({ beats: v })} placeholder="4" />
    </>
  ),

  color_wheel: (config, onUpdate) => (
    <>
      <Field label="Title" value={config.title} onChange={v => onUpdate({ title: v })} placeholder="Color Wheel" />
    </>
  ),
};


// ─── Generic fallback editor ──────────────────────────────────────────────────
function GenericEditor({ config, onUpdate }) {
  const keys = Object.keys(config || {}).filter(k => !k.startsWith('_'));
  if (keys.length === 0) {
    return <div style={{ fontSize: 11, color: '#A8A29E', fontStyle: 'italic' }}>No editable fields</div>;
  }
  return (
    <>
      {keys.map(k => {
        const v = config[k];
        if (v === null || v === undefined || typeof v === 'object' && !Array.isArray(v)) return null;
        if (typeof v === 'boolean') {
          return <Checkbox key={k} label={k} checked={v} onChange={val => onUpdate({ [k]: val })} />;
        }
        if (typeof v === 'number') {
          return <Field key={k} label={k} type="number" value={v} onChange={val => onUpdate({ [k]: val })} />;
        }
        if (Array.isArray(v)) {
          return <ArrayField key={k} label={k} value={v} onChange={val => onUpdate({ [k]: val })} />;
        }
        // string
        const isLong = typeof v === 'string' && v.length > 50;
        return <Field key={k} label={k} value={v} onChange={val => onUpdate({ [k]: val })} multiline={isLong} />;
      })}
    </>
  );
}


// ─── Main exported component ──────────────────────────────────────────────────
function SpecialistEditor({ type, config, onUpdate }) {
  const isMathType = MATH_TYPES.has(type);
  const { handleInsert, trackFocus } = useMathInsert(onUpdate);

  const editorFn = EDITORS[type];

  return (
    <div onFocusCapture={isMathType ? trackFocus : undefined}>
      {isMathType && <MathToolbar onInsert={handleInsert} />}
      {editorFn ? editorFn(config || {}, onUpdate) : <GenericEditor config={config || {}} onUpdate={onUpdate} />}
    </div>
  );
}

export { SpecialistEditor, MathToolbar };
