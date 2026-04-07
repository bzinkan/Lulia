'use client';

/**
 * WYSIWYG component renderers — each renders exactly as it will print.
 * Used on the canvas and in PDF export.
 */

// Default grade context (grade 4) if none provided
const DEFAULT_GRADE = { baseFontSize: 14, lineHeight: 1.6, mcColumns: 2, answerLines: 2 };

// ─── Shared style helpers ───────────────────────────────────────────────────
const sectionBox = (title, children, extra = {}) => (
  <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden', ...extra }}>
    <div style={{ background: '#F5F5F4', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{title}</div>
    <div style={{ padding: 10 }}>{children}</div>
  </div>
);

const labeledLines = (labels, lineH = 24) => labels.map((l, i) => (
  <div key={i} style={{ marginBottom: 6 }}>
    <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 2 }}>{l}</div>
    <div style={{ borderBottom: '1px solid #E7E5E4', height: lineH }} />
  </div>
));

const analysisFrame = (title, sections) => (
  <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
    <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{title}</div>
    <div style={{ padding: 10 }}>
      {sections.map((s, i) => (
        <div key={i} style={{ marginBottom: i < sections.length - 1 ? 10 : 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>{s}</div>
          <div style={{ borderBottom: '1px solid #E7E5E4', height: 22 }} />
          <div style={{ borderBottom: '1px solid #E7E5E4', height: 22 }} />
        </div>
      ))}
    </div>
  </div>
);

const cardBox = (title, fields) => (
  <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 12, background: '#FEF9F2' }}>
    <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', marginBottom: 8 }}>{title}</div>
    {fields.map((f, i) => (
      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: 12 }}>
        <span style={{ fontWeight: 600, color: '#78350F', fontSize: 11, minWidth: 80 }}>{f}:</span>
        <span style={{ borderBottom: '1px solid #E7E5E4', flex: 1, height: 18 }} />
      </div>
    ))}
  </div>
);

const writingArea = (title, lines = 6, gc) => {
  const lh = (gc || DEFAULT_GRADE).baseFontSize >= 16 ? 32 : 24;
  return (
    <div>
      {title && <div style={{ fontSize: 13, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>{title}</div>}
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} style={{ borderBottom: '1px solid #E7E5E4', height: lh }} />
      ))}
    </div>
  );
};

// ─── EXISTING UNIVERSAL RENDERERS ───────────────────────────────────────────

export function HeaderRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const level = config.level || 'h1';
  const align = config.alignment || 'left';
  const scale = gc.baseFontSize / 14; // scale relative to grade 4 baseline
  const sizes = { h1: Math.round(22 * scale), h2: Math.round(18 * scale), h3: Math.round(14 * scale) };
  return (
    <div style={{ textAlign: align }}>
      <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: sizes[level], color: '#1C1917', lineHeight: 1.3 }}>
        {config.text || 'Untitled'}
      </div>
      {config.subtitle && <div style={{ fontSize: Math.round(13 * scale), color: '#78716C', marginTop: 2 }}>{config.subtitle}</div>}
    </div>
  );
}

export function NameDateRenderer({ config = {} }) {
  const fields = config.fields || ['name', 'date'];
  const labels = { name: 'Name', date: 'Date', period: 'Period', class: 'Class', score: 'Score' };
  return (
    <div style={{ display: 'flex', gap: 24, fontSize: 12, color: '#78716C' }}>
      {fields.map(f => (
        <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontWeight: 600, color: '#78350F', fontSize: 11 }}>{labels[f] || f}:</span>
          <span style={{ borderBottom: '1px solid #E7E5E4', width: 120, display: 'inline-block', height: 18 }} />
        </div>
      ))}
    </div>
  );
}

export function BannerRenderer({ config = {} }) {
  return (
    <div style={{ background: config.color || '#F97316', color: 'white', padding: '8px 16px', borderRadius: 8, fontWeight: 600, fontSize: 14, textAlign: 'center' }}>
      {config.text || 'Section Title'}
    </div>
  );
}

export function MultipleChoiceRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const options = config.options || ['Option A', 'Option B', 'Option C', 'Option D'];
  const useColumns = gc.mcColumns >= 2 && options.length >= 4;
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ fontSize: gc.baseFontSize - 1, color: '#1C1917', marginBottom: 6, lineHeight: gc.lineHeight }}>{config.question || 'Question text goes here'}</div>
      <div style={{ marginLeft: 16, display: useColumns ? 'grid' : 'block', gridTemplateColumns: useColumns ? '1fr 1fr' : undefined, gap: useColumns ? '3px 16px' : undefined }}>
        {options.map((opt, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3, fontSize: gc.baseFontSize - 1, color: '#1C1917' }}>
            <span style={{ width: 18, height: 18, borderRadius: '50%', border: '2px solid #E7E5E4', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 600, color: '#78350F', flexShrink: 0 }}>
              {String.fromCharCode(65 + i)}
            </span>
            {opt}
          </div>
        ))}
      </div>
      {config.points && <div style={{ fontSize: 10, color: '#A8A29E', textAlign: 'right' }}>/{config.points} pts</div>}
    </div>
  );
}

export function FillInBlankRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const sentence = config.sentence || 'The ___ is equal to one half.';
  const blankWidth = gc.baseFontSize >= 16 ? 100 : 80;
  const rendered = sentence.replace(/___/g, `<span style="border-bottom:2px solid #F97316;display:inline-block;width:${blankWidth}px;height:${Math.round(gc.baseFontSize * 1.2)}px;margin:0 4px;"></span>`);
  return <div style={{ fontSize: gc.baseFontSize - 1, color: '#1C1917', lineHeight: gc.lineHeight + 0.4 }} dangerouslySetInnerHTML={{ __html: rendered }} />;
}

export function ShortAnswerRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const lines = config.lines || gc.answerLines;
  const lineHeight = gc.baseFontSize >= 16 ? 32 : 24;
  return (
    <div>
      <div style={{ fontSize: gc.baseFontSize - 1, color: '#1C1917', marginBottom: 6, lineHeight: gc.lineHeight }}>{config.question || 'Question'}</div>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} style={{ borderBottom: '1px solid #E7E5E4', height: lineHeight }} />
      ))}
    </div>
  );
}

export function LongAnswerRenderer({ config = {} }) {
  const height = { small: 60, medium: 120, large: 200 }[config.size || 'medium'];
  return (
    <div>
      <div style={{ fontSize: 13, color: '#1C1917', marginBottom: 6 }}>{config.question || 'Question'}</div>
      <div style={{ border: '1px solid #E7E5E4', borderRadius: 8, height, background: '#FAFAF9' }} />
    </div>
  );
}

export function TrueFalseRenderer({ config = {} }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13, color: '#1C1917' }}>
      <span style={{ display: 'flex', gap: 8 }}>
        <span style={{ width: 16, height: 16, border: '2px solid #E7E5E4', borderRadius: 3 }} />
        <span style={{ fontSize: 11, color: '#78716C' }}>T</span>
        <span style={{ width: 16, height: 16, border: '2px solid #E7E5E4', borderRadius: 3 }} />
        <span style={{ fontSize: 11, color: '#78716C' }}>F</span>
      </span>
      <span>{config.statement || 'True/false statement'}</span>
    </div>
  );
}

export function InstructionsRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div style={{ background: '#FFF7ED', borderLeft: '3px solid #F97316', padding: '8px 12px', fontSize: gc.baseFontSize - 2, color: '#78350F', borderRadius: '0 8px 8px 0', lineHeight: gc.lineHeight }}>
      <div dangerouslySetInnerHTML={{ __html: config.html || config.text || '<b>Directions:</b> Complete all problems.' }} />
    </div>
  );
}

export function TextBlockRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return <div style={{ fontSize: gc.baseFontSize - 1, color: '#4B5563', lineHeight: gc.lineHeight }}>{config.text || 'Text content'}</div>;
}

export function WordBankRenderer({ config = {} }) {
  const words = config.words || ['term 1', 'term 2', 'term 3'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: '8px 14px', background: '#FEF9F2' }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Word Bank</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {words.map((w, i) => (
          <span key={i} style={{ fontSize: 13, padding: '2px 10px', background: 'white', borderRadius: 6, border: '1px solid #FDBA74' }}>{w}</span>
        ))}
      </div>
    </div>
  );
}

export function ReadingPassageRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const text = config.text || 'Passage text goes here. This is a sample reading passage that students will read before answering comprehension questions.';
  const lines = text.split('\n').length > 1 ? text.split('\n') : text.match(/.{1,80}/g) || [text];
  return (
    <div style={{ background: '#FEF9F2', border: '1px solid #E7E5E4', borderRadius: 10, padding: 14, fontSize: gc.baseFontSize - 1, lineHeight: gc.lineHeight + 0.2 }}>
      {config.title && <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: gc.baseFontSize, marginBottom: 8 }}>{config.title}</div>}
      {lines.map((line, i) => (
        <div key={i}><span style={{ display: 'inline-block', width: 24, textAlign: 'right', marginRight: 10, color: '#A8A29E', fontSize: 10, userSelect: 'none' }}>{i + 1}</span>{line}</div>
      ))}
    </div>
  );
}

export function ImageRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  // K-2: images default larger (75%), 3-5: medium (50%), 6+: as specified
  const gradeDefaultSize = gc.baseFontSize >= 16 ? 'large' : gc.baseFontSize >= 13 ? 'medium' : 'medium';
  const sizeKey = config.size || gradeDefaultSize;
  const maxWidth = { small: '25%', medium: '50%', large: '75%', full: '100%' }[sizeKey];

  if (config.url) {
    return (
      <div style={{ textAlign: config.alignment || 'center' }}>
        <img src={config.url} alt={config.caption || ''} style={{
          maxWidth, borderRadius: 8, border: config.border ? '1px solid #E7E5E4' : 'none',
        }} />
        {config.caption && <div style={{ fontSize: gc.baseFontSize - 2, color: '#A8A29E', marginTop: 4 }}>{config.caption}</div>}
      </div>
    );
  }
  return (
    <div style={{ border: '2px dashed #FDBA74', borderRadius: 14, height: gc.baseFontSize >= 16 ? 160 : 120, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED' }}>
      <span style={{ fontSize: gc.baseFontSize - 2, color: '#FDBA74' }}>Click to add image</span>
    </div>
  );
}

export function TableRenderer({ config = {} }) {
  const rows = config.rows || 3;
  const cols = config.cols || 3;
  const headers = config.headers || Array.from({ length: cols }, (_, i) => `Column ${i + 1}`);
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      {config.showHeader !== false && (
        <thead><tr>
          {headers.map((h, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', textAlign: 'left', fontWeight: 600, color: '#78350F' }}>{h}</th>)}
        </tr></thead>
      )}
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            {Array.from({ length: cols }).map((_, c) => (
              <td key={c} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 28 }} />
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DividerRenderer({ config = {} }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '4px 0' }}>
      <div style={{ flex: 1, borderTop: '1px solid #E7E5E4' }} />
      {config.label && <span style={{ fontSize: 11, fontWeight: 600, color: '#78350F', whiteSpace: 'nowrap' }}>{config.label}</span>}
      {config.label && <div style={{ flex: 1, borderTop: '1px solid #E7E5E4' }} />}
    </div>
  );
}

export function SpacerRenderer({ config = {} }) {
  const heights = { small: 12, medium: 24, large: 48 };
  return <div style={{ height: heights[config.size || 'medium'] }} />;
}

export function MatchingRenderer({ config = {} }) {
  const pairs = config.pairs || [{ left: 'Term 1', right: 'Definition 1' }, { left: 'Term 2', right: 'Definition 2' }];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
      <div style={{ fontWeight: 600, fontSize: 11, color: '#78350F', borderBottom: '2px solid #F97316', paddingBottom: 4 }}>Terms</div>
      <div style={{ fontWeight: 600, fontSize: 11, color: '#78350F', borderBottom: '2px solid #F97316', paddingBottom: 4 }}>Definitions</div>
      {pairs.map((p, i) => (<>
        <div key={`l${i}`} style={{ fontSize: 13, padding: '4px 0', borderBottom: '1px solid #F5F5F4' }}>{String.fromCharCode(65 + i)}. {p.left}</div>
        <div key={`r${i}`} style={{ fontSize: 13, padding: '4px 0', borderBottom: '1px solid #F5F5F4' }}>___  {p.right}</div>
      </>))}
    </div>
  );
}

export function ExampleRenderer({ config = {} }) {
  return (
    <div style={{ background: '#FEF9F2', borderLeft: '3px solid #FDBA74', padding: '8px 12px', borderRadius: '0 8px 8px 0' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#F97316', marginBottom: 4 }}>Example</div>
      <div style={{ fontSize: 13, color: '#1C1917' }}>{config.text || 'Worked example steps go here'}</div>
    </div>
  );
}

export function VocabularyRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 15, color: '#1C1917' }}>{config.term || 'Term'}</div>
      <div style={{ fontSize: 12, color: '#78716C', marginTop: 2 }}>{config.definition || 'Definition goes here'}</div>
      {config.example && <div style={{ fontSize: 11, color: '#A8A29E', fontStyle: 'italic', marginTop: 4 }}>"{config.example}"</div>}
    </div>
  );
}

export function NumberLineRenderer({ config = {} }) {
  const min = config.min ?? 0;
  const max = config.max ?? 10;
  const interval = config.interval ?? 1;
  const ticks = [];
  for (let i = min; i <= max; i += interval) ticks.push(i);
  return (
    <div style={{ position: 'relative', height: 50, margin: '10px 20px' }}>
      <div style={{ position: 'absolute', top: 20, left: 0, right: 0, height: 2, background: '#1C1917' }} />
      {ticks.map((t, i) => (
        <div key={i} style={{ position: 'absolute', top: 12, left: `${((t - min) / (max - min)) * 100}%`, transform: 'translateX(-50%)' }}>
          <div style={{ width: 2, height: 16, background: '#1C1917', margin: '0 auto' }} />
          <div style={{ fontSize: 10, textAlign: 'center', marginTop: 2, color: '#78716C' }}>{t}</div>
        </div>
      ))}
    </div>
  );
}

export function GraphGridRenderer({ config = {} }) {
  return (
    <div style={{ width: 200, height: 200, border: '2px solid #1C1917', position: 'relative', margin: '0 auto' }}>
      <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1, background: '#1C1917' }} />
      <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: '#1C1917' }} />
      <span style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', fontSize: 10 }}>x</span>
      <span style={{ position: 'absolute', left: '50%', top: 4, transform: 'translateX(-50%)', fontSize: 10 }}>y</span>
    </div>
  );
}

export function MathProblemRenderer({ config = {}, theme, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const workHeight = gc.baseFontSize >= 16 ? 100 : 80;
  return (
    <div style={{ fontFamily: 'monospace', fontSize: gc.baseFontSize + 2, padding: 8, lineHeight: gc.lineHeight }}>
      <div>{config.problem || '24 \u00d7 16 = ___'}</div>
      {config.showWorkSpace && <div style={{ border: '1px solid #E7E5E4', borderRadius: 8, height: workHeight, marginTop: 8, background: '#FAFAF9' }} />}
    </div>
  );
}

export function AnswerKeyRenderer({ config = {} }) {
  return (
    <div>
      <div style={{ borderTop: '2px dashed #E7E5E4', margin: '8px 0' }} />
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', textAlign: 'center', marginBottom: 4 }}>ANSWER KEY</div>
      <div style={{ fontSize: 11, color: '#78716C' }}>{config.auto_populate ? 'Answers auto-populate from marked correct answers above.' : 'Add answers manually.'}</div>
    </div>
  );
}

// ─── GRID / GRAPH COMPONENTS ────────────────────────────────────────────────

export function CoordinatePlaneRenderer({ config = {} }) {
  const size = config.size || 260;
  const gridLines = config.gridLines ?? 10;
  const step = size / gridLines;
  const xMin = config.xMin ?? -5;
  const xMax = config.xMax ?? 5;
  const yMin = config.yMin ?? -5;
  const yMax = config.yMax ?? 5;
  const equations = config.equations || [];

  // Simple equation evaluator for plotting (supports basic f(x))
  function evalEquation(expr, x) {
    try {
      const sanitized = expr
        .replace(/\^/g, '**')
        .replace(/(\d)(x)/g, '$1*x')
        .replace(/\bx\b/g, `(${x})`);
      return Function('"use strict"; return (' + sanitized + ')')();
    } catch { return null; }
  }

  function toSvgX(x) { return ((x - xMin) / (xMax - xMin)) * size; }
  function toSvgY(y) { return size - ((y - yMin) / (yMax - yMin)) * size; }

  const colors = ['#F97316', '#2563EB', '#059669', '#7C3AED', '#E11D48'];

  return (
    <div style={{ margin: '0 auto', width: size + 30, position: 'relative' }}>
      <svg width={size} height={size} style={{ border: '1px solid #E7E5E4' }}>
        {/* Grid */}
        {Array.from({ length: gridLines + 1 }).map((_, i) => (
          <g key={i}>
            <line x1={i * step} y1={0} x2={i * step} y2={size} stroke="#F5F5F4" strokeWidth={0.5} />
            <line x1={0} y1={i * step} x2={size} y2={i * step} stroke="#F5F5F4" strokeWidth={0.5} />
          </g>
        ))}
        {/* Axes */}
        <line x1={toSvgX(0)} y1={0} x2={toSvgX(0)} y2={size} stroke="#1C1917" strokeWidth={1.5} />
        <line x1={0} y1={toSvgY(0)} x2={size} y2={toSvgY(0)} stroke="#1C1917" strokeWidth={1.5} />
        {/* Axis labels */}
        {Array.from({ length: xMax - xMin + 1 }).map((_, i) => {
          const val = xMin + i;
          if (val === 0) return null;
          return <text key={`x${val}`} x={toSvgX(val)} y={toSvgY(0) + 12} fontSize={8} fill="#A8A29E" textAnchor="middle">{val}</text>;
        })}
        {Array.from({ length: yMax - yMin + 1 }).map((_, i) => {
          const val = yMin + i;
          if (val === 0) return null;
          return <text key={`y${val}`} x={toSvgX(0) - 10} y={toSvgY(val) + 3} fontSize={8} fill="#A8A29E" textAnchor="middle">{val}</text>;
        })}
        <text x={size - 8} y={toSvgY(0) - 6} fontSize={10} fill="#78350F">x</text>
        <text x={toSvgX(0) + 8} y={12} fontSize={10} fill="#78350F">y</text>
        {/* Plot equations (only if showAnswer is true) */}
        {config.showAnswer !== false && equations.map((eq, eqIdx) => {
          if (!eq.expr) return null;
          const points = [];
          for (let px = 0; px <= size; px += 2) {
            const x = xMin + (px / size) * (xMax - xMin);
            const y = evalEquation(eq.expr, x);
            if (y !== null && isFinite(y) && y >= yMin - 2 && y <= yMax + 2) {
              points.push(`${px},${toSvgY(y)}`);
            }
          }
          return points.length > 1 ? (
            <polyline key={eqIdx} points={points.join(' ')} fill="none" stroke={colors[eqIdx % colors.length]} strokeWidth={2} />
          ) : null;
        })}
      </svg>
      {/* Equation labels */}
      {equations.length > 0 && (
        <div style={{ marginTop: 4, display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
          {equations.map((eq, i) => eq.expr && (
            <span key={i} style={{ fontSize: 10, color: colors[i % colors.length], fontFamily: 'monospace' }}>
              {eq.label || `f(x)`} = {eq.expr}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function GeometryCanvasRenderer({ config = {} }) {
  const shapes = config.shapes || [];
  const size = config.size || 280;
  const showGrid = config.showGrid !== false;
  const title = config.title || '';

  function renderShape(shape, idx) {
    const c = shape.color || '#F97316';
    const label = shape.label || '';
    switch (shape.type) {
      case 'triangle': {
        const cx = shape.x || 140; const cy = shape.y || 100; const s = shape.size || 80;
        const variant = shape.variant || 'scalene';
        // Calculate points based on triangle type
        let ax, ay, bx, by, ccx, ccy;
        if (variant === 'right') {
          // Right angle at bottom-left
          bx = cx - s / 2; by = cy + s * 0.4;
          ccx = cx + s / 2; ccy = cy + s * 0.4;
          ax = cx - s / 2; ay = cy - s * 0.5;
        } else if (variant === 'equilateral') {
          const h = s * Math.sqrt(3) / 2;
          ax = cx; ay = cy - h * 0.55;
          bx = cx - s / 2; by = cy + h * 0.45;
          ccx = cx + s / 2; ccy = cy + h * 0.45;
        } else if (variant === 'isosceles') {
          ax = cx; ay = cy - s * 0.6;
          bx = cx - s * 0.35; by = cy + s * 0.4;
          ccx = cx + s * 0.35; ccy = cy + s * 0.4;
        } else {
          ax = cx - s * 0.1; ay = cy - s * 0.55;
          bx = cx - s / 2; by = cy + s * 0.4;
          ccx = cx + s / 2; ccy = cy + s * 0.4;
        }
        const pts = `${ax},${ay} ${bx},${by} ${ccx},${ccy}`;
        const sq = 10; // right angle square size
        return <g key={idx}>
          <polygon points={pts} fill="none" stroke={c} strokeWidth={2} />
          {/* Right angle symbol */}
          {variant === 'right' && (
            <path d={`M${bx},${by - sq} L${bx + sq},${by - sq} L${bx + sq},${by}`} fill="none" stroke={c} strokeWidth={1.2} />
          )}
          {/* Tick marks for equal sides */}
          {variant === 'equilateral' && <>
            <line x1={(ax + bx) / 2 - 3} y1={(ay + by) / 2} x2={(ax + bx) / 2 + 3} y2={(ay + by) / 2 - 3} stroke={c} strokeWidth={1.5} />
            <line x1={(ax + ccx) / 2 - 3} y1={(ay + ccy) / 2} x2={(ax + ccx) / 2 + 3} y2={(ay + ccy) / 2 - 3} stroke={c} strokeWidth={1.5} />
            <line x1={(bx + ccx) / 2 - 3} y1={(by + ccy) / 2 + 2} x2={(bx + ccx) / 2 + 3} y2={(by + ccy) / 2 - 1} stroke={c} strokeWidth={1.5} />
          </>}
          {variant === 'isosceles' && <>
            <line x1={(ax + bx) / 2 - 3} y1={(ay + by) / 2} x2={(ax + bx) / 2 + 3} y2={(ay + by) / 2 - 3} stroke={c} strokeWidth={1.5} />
            <line x1={(ax + ccx) / 2 - 3} y1={(ay + ccy) / 2} x2={(ax + ccx) / 2 + 3} y2={(ay + ccy) / 2 - 3} stroke={c} strokeWidth={1.5} />
          </>}
          {label && <text x={cx} y={Math.max(by, ccy) + 14} fontSize={10} fill="#78350F" textAnchor="middle">{label}</text>}
          {shape.showAngles && <>
            <text x={ax + (variant === 'right' ? 0 : 0)} y={ay - 6} fontSize={8} fill="#A8A29E" textAnchor="middle">{shape.angleA || (variant === 'right' ? '' : 'A')}</text>
            <text x={bx - 10} y={by + 4} fontSize={8} fill="#A8A29E">{shape.angleB || (variant === 'right' ? '90°' : 'B')}</text>
            <text x={ccx + 6} y={ccy + 4} fontSize={8} fill="#A8A29E">{shape.angleC || 'C'}</text>
          </>}
          {shape.showSides && <>
            <text x={(ax + bx) / 2 - 10} y={(ay + by) / 2} fontSize={8} fill={c} textAnchor="middle">{shape.sideA || 'a'}</text>
            <text x={(bx + ccx) / 2} y={by + 22} fontSize={8} fill={c} textAnchor="middle">{shape.sideB || 'b'}</text>
            <text x={(ax + ccx) / 2 + 10} y={(ay + ccy) / 2} fontSize={8} fill={c} textAnchor="middle">{shape.sideC || 'c'}</text>
          </>}
        </g>;
      }
      case 'rectangle': {
        const x = shape.x || 60; const y = shape.y || 50;
        const w = shape.width || 120; const h = shape.height || 80;
        return <g key={idx}><rect x={x} y={y} width={w} height={h} fill="none" stroke={c} strokeWidth={2} rx={2} />
          {label && <text x={x + w / 2} y={y + h + 14} fontSize={10} fill="#78350F" textAnchor="middle">{label}</text>}
          {shape.showDimensions && <>
            <text x={x + w / 2} y={y - 4} fontSize={8} fill={c} textAnchor="middle">{shape.widthLabel || 'w'}</text>
            <text x={x - 10} y={y + h / 2 + 3} fontSize={8} fill={c} textAnchor="middle">{shape.heightLabel || 'h'}</text>
          </>}
        </g>;
      }
      case 'circle': {
        const cx = shape.x || 140; const cy = shape.y || 120; const r = shape.radius || 50;
        const sectorAngle = shape.sectorAngle || 0;
        const sectorRad = (sectorAngle * Math.PI) / 180;
        return <g key={idx}>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={c} strokeWidth={2} />
          {/* Center point */}
          {shape.showCenter && <><circle cx={cx} cy={cy} r={2.5} fill={c} />
            <text x={cx + 6} y={cy - 6} fontSize={7} fill="#A8A29E">O</text></>}
          {/* Radius */}
          {shape.showRadius && <>
            <line x1={cx} y1={cy} x2={cx + r} y2={cy} stroke={c} strokeWidth={1.5} strokeDasharray="4,2" />
            <text x={cx + r / 2} y={cy - 5} fontSize={8} fill={c} textAnchor="middle">{shape.radiusLabel || 'r'}</text>
          </>}
          {/* Diameter */}
          {shape.showDiameter && <>
            <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} stroke={c} strokeWidth={1.5} />
            <text x={cx} y={cy + 12} fontSize={8} fill={c} textAnchor="middle">{shape.diameterLabel || 'd'}</text>
          </>}
          {/* Chord */}
          {shape.showChord && <>
            <line x1={cx - r * 0.7} y1={cy - r * 0.7} x2={cx + r * 0.85} y2={cy - r * 0.5} stroke="#7C3AED" strokeWidth={1.5} />
            <text x={cx} y={cy - r * 0.65 - 4} fontSize={8} fill="#7C3AED" textAnchor="middle">{shape.chordLabel || 'chord'}</text>
          </>}
          {/* Arc + sector */}
          {sectorAngle > 0 && <>
            <line x1={cx} y1={cy} x2={cx + r} y2={cy} stroke={c} strokeWidth={1} />
            <line x1={cx} y1={cy} x2={cx + Math.cos(sectorRad) * r} y2={cy - Math.sin(sectorRad) * r} stroke={c} strokeWidth={1} />
            <path d={`M${cx + r * 0.3},${cy} A${r * 0.3},${r * 0.3} 0 ${sectorAngle > 180 ? 1 : 0},0 ${cx + Math.cos(sectorRad) * r * 0.3},${cy - Math.sin(sectorRad) * r * 0.3}`}
              fill="none" stroke={c} strokeWidth={1.2} />
            <path d={`M${cx + r},${cy} A${r},${r} 0 ${sectorAngle > 180 ? 1 : 0},0 ${cx + Math.cos(sectorRad) * r},${cy - Math.sin(sectorRad) * r}`}
              fill="none" stroke={c} strokeWidth={2.5} />
            <text x={cx + r * 0.4} y={cy - 6} fontSize={8} fill={c}>{shape.sectorLabel || `${sectorAngle}°`}</text>
          </>}
          {/* Circumference label */}
          {shape.showCircumference && <text x={cx} y={cy - r - 6} fontSize={8} fill={c} textAnchor="middle">{shape.circumferenceLabel || 'C = 2πr'}</text>}
          {/* Area label */}
          {shape.showArea && <text x={cx} y={cy + 3} fontSize={8} fill="#A8A29E" textAnchor="middle">{shape.areaLabel || 'A = πr²'}</text>}
          {label && <text x={cx} y={cy + r + 14} fontSize={10} fill="#78350F" textAnchor="middle">{label}</text>}
        </g>;
      }
      case 'line_segment': {
        const x1 = shape.x1 || 40; const y1 = shape.y1 || 140;
        const x2 = shape.x2 || 220; const y2 = shape.y2 || 60;
        return <g key={idx}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke={c} strokeWidth={2} />
          <circle cx={x1} cy={y1} r={3} fill={c} /><circle cx={x2} cy={y2} r={3} fill={c} />
          {label && <text x={(x1 + x2) / 2 + 6} y={(y1 + y2) / 2 - 6} fontSize={8} fill={c}>{label}</text>}
        </g>;
      }
      case 'angle': {
        const cx = shape.x || 140; const cy = shape.y || 140;
        const len = shape.size || 60; const deg = shape.degrees || 45;
        const rad = (deg * Math.PI) / 180;
        return <g key={idx}>
          <line x1={cx} y1={cy} x2={cx + len} y2={cy} stroke={c} strokeWidth={2} />
          <line x1={cx} y1={cy} x2={cx + Math.cos(rad) * len} y2={cy - Math.sin(rad) * len} stroke={c} strokeWidth={2} />
          <path d={`M${cx + 20},${cy} A20,20 0 0,0 ${cx + Math.cos(rad) * 20},${cy - Math.sin(rad) * 20}`} fill="none" stroke={c} strokeWidth={1.5} />
          <text x={cx + 28} y={cy - 8} fontSize={9} fill={c}>{shape.degreeLabel || `${deg}°`}</text>
        </g>;
      }
      default: return null;
    }
  }

  return (
    <div style={{ margin: '0 auto', width: size }}>
      {title && <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4, textAlign: 'center' }}>{title}</div>}
      <svg width={size} height={size * 0.75} style={{ border: '1px solid #E7E5E4', borderRadius: 8, background: '#FAFAF9' }}>
        {showGrid && Array.from({ length: 15 }).map((_, i) => (
          <g key={i}>
            <line x1={i * (size / 14)} y1={0} x2={i * (size / 14)} y2={size * 0.75} stroke="#F0EFED" strokeWidth={0.5} />
            <line x1={0} y1={i * (size * 0.75 / 14)} x2={size} y2={i * (size * 0.75 / 14)} stroke="#F0EFED" strokeWidth={0.5} />
          </g>
        ))}
        {shapes.length > 0 ? shapes.map(renderShape) : (
          <text x={size / 2} y={size * 0.375} fontSize={12} fill="#A8A29E" textAnchor="middle">Add shapes using the panel →</text>
        )}
      </svg>
      {/* Formula reference */}
      {config.showFormulas !== false && shapes.length > 0 && (
        <div style={{ fontSize: 9, color: '#A8A29E', marginTop: 4, textAlign: 'center', fontFamily: 'monospace' }}>
          {shapes.some(s => s.type === 'triangle') && 'A = ½bh  '}
          {shapes.some(s => s.type === 'rectangle') && 'A = lw  P = 2l + 2w  '}
          {shapes.some(s => s.type === 'circle') && 'A = πr²  C = 2πr  '}
        </div>
      )}
    </div>
  );
}

export function TransformationGridRenderer({ config = {} }) {
  const size = 200;
  const cells = 8;
  const step = size / cells;
  return (
    <div style={{ margin: '0 auto', width: size, height: size, position: 'relative' }}>
      <svg width={size} height={size}>
        {Array.from({ length: cells + 1 }).map((_, i) => (
          <g key={i}>
            <line x1={i * step} y1={0} x2={i * step} y2={size} stroke="#E7E5E4" strokeWidth={0.5} />
            <line x1={0} y1={i * step} x2={size} y2={i * step} stroke="#E7E5E4" strokeWidth={0.5} />
          </g>
        ))}
        <line x1={size / 2} y1={0} x2={size / 2} y2={size} stroke="#1C1917" strokeWidth={1} />
        <line x1={0} y1={size / 2} x2={size} y2={size / 2} stroke="#1C1917" strokeWidth={1} />
      </svg>
      <div style={{ textAlign: 'center', fontSize: 10, color: '#78350F', marginTop: 4 }}>Transformation Grid</div>
    </div>
  );
}

export function DistributionCurveRenderer({ config = {} }) {
  return (
    <div style={{ margin: '0 auto', width: 260, height: 140, position: 'relative' }}>
      <svg width={260} height={120} viewBox="0 0 260 120">
        <line x1={20} y1={100} x2={240} y2={100} stroke="#1C1917" strokeWidth={1.5} />
        <line x1={20} y1={10} x2={20} y2={100} stroke="#1C1917" strokeWidth={1.5} />
        <path d="M30,98 Q70,95 100,70 Q130,20 130,20 Q130,20 160,70 Q190,95 230,98" fill="none" stroke="#F97316" strokeWidth={2} />
        <text x={125} y={115} fontSize={10} fill="#78350F" textAnchor="middle">{config.xLabel || 'x'}</text>
        <text x={8} y={55} fontSize={10} fill="#78350F" textAnchor="middle" transform="rotate(-90,8,55)">{config.yLabel || 'f(x)'}</text>
      </svg>
    </div>
  );
}

export function SupplyDemandGraphRenderer({ config = {} }) {
  return (
    <div style={{ margin: '0 auto', width: 220, height: 200, position: 'relative' }}>
      <svg width={220} height={180}>
        <line x1={30} y1={10} x2={30} y2={160} stroke="#1C1917" strokeWidth={1.5} />
        <line x1={30} y1={160} x2={210} y2={160} stroke="#1C1917" strokeWidth={1.5} />
        <line x1={40} y1={20} x2={200} y2={150} stroke="#F97316" strokeWidth={2} />
        <line x1={40} y1={150} x2={200} y2={20} stroke="#78350F" strokeWidth={2} />
        <text x={200} y={146} fontSize={9} fill="#F97316">S</text>
        <text x={200} y={26} fontSize={9} fill="#78350F">D</text>
        <text x={120} y={175} fontSize={10} fill="#78716C" textAnchor="middle">Quantity</text>
        <text x={12} y={90} fontSize={10} fill="#78716C" textAnchor="middle" transform="rotate(-90,12,90)">Price</text>
      </svg>
    </div>
  );
}

export function EconomicModelRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{config.title || 'Economic Model'}</div>
      <div style={{ padding: 10, height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width={200} height={140}>
          <line x1={30} y1={10} x2={30} y2={130} stroke="#1C1917" strokeWidth={1.5} />
          <line x1={30} y1={130} x2={190} y2={130} stroke="#1C1917" strokeWidth={1.5} />
          <path d="M40,120 Q80,100 120,60 Q160,20 180,15" fill="none" stroke="#F97316" strokeWidth={2} />
          <text x={110} y={128} fontSize={9} fill="#78716C" textAnchor="middle">{config.xLabel || 'Variable X'}</text>
        </svg>
      </div>
    </div>
  );
}

// ─── TABLE / CHART COMPONENTS ───────────────────────────────────────────────

export function FunctionTableRenderer({ config = {} }) {
  const inputs = config.inputs || ['x', '1', '2', '3', '4'];
  const outputs = config.outputs || ['f(x)', '', '', '', ''];
  return (
    <table style={{ borderCollapse: 'collapse', fontSize: 12, margin: '0 auto' }}>
      <tbody>
        <tr>{inputs.map((v, i) => <td key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 14px', background: i === 0 ? '#F5F5F4' : 'white', fontWeight: i === 0 ? 600 : 400, color: i === 0 ? '#78350F' : '#1C1917' }}>{v}</td>)}</tr>
        <tr>{outputs.map((v, i) => <td key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 14px', background: i === 0 ? '#F5F5F4' : 'white', fontWeight: i === 0 ? 600 : 400, color: i === 0 ? '#78350F' : '#1C1917', height: 28 }}>{v}</td>)}</tr>
      </tbody>
    </table>
  );
}

export function TwoWayTableRenderer({ config = {} }) {
  const rowHeaders = config.rowHeaders || ['Category A', 'Category B'];
  const colHeaders = config.colHeaders || ['Yes', 'No', 'Total'];
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4' }} />
        {colHeaders.map((h, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F', fontWeight: 600 }}>{h}</th>)}
      </tr></thead>
      <tbody>
        {rowHeaders.map((r, ri) => (
          <tr key={ri}>
            <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', fontWeight: 600, color: '#78350F' }}>{r}</td>
            {colHeaders.map((_, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 28 }} />)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DataCollectionTableRenderer({ config = {} }) {
  const headers = config.headers || ['Trial', 'Observation', 'Measurement', 'Notes'];
  const rows = config.rows || 5;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        {headers.map((h, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{h}</th>)}
      </tr></thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', textAlign: 'center', color: '#78716C' }}>{r + 1}</td>
            {Array.from({ length: headers.length - 1 }).map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 28 }} />)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ComparisonChartRenderer({ config = {} }) {
  const items = config.items || ['Item A', 'Item B'];
  const criteria = config.criteria || ['Feature 1', 'Feature 2', 'Feature 3'];
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Criteria</th>
        {items.map((h, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{h}</th>)}
      </tr></thead>
      <tbody>
        {criteria.map((c, ri) => (
          <tr key={ri}>
            <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', fontWeight: 600, color: '#78350F' }}>{c}</td>
            {items.map((_, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 28 }} />)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PlaceValueChartRenderer({ config = {} }) {
  const places = config.places || ['Thousands', 'Hundreds', 'Tens', 'Ones'];
  return (
    <table style={{ margin: '0 auto', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        {places.map((p, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 14px', background: '#FFF7ED', fontWeight: 600, color: '#78350F', textAlign: 'center' }}>{p}</th>)}
      </tr></thead>
      <tbody>
        <tr>{places.map((_, i) => <td key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 14px', height: 40, width: 60, textAlign: 'center' }} />)}</tr>
      </tbody>
    </table>
  );
}

export function ConjugationTableRenderer({ config = {} }) {
  const pronouns = config.pronouns || ['yo', 'tu', 'el/ella', 'nosotros', 'vosotros', 'ellos'];
  const verb = config.verb || 'hablar';
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{verb}</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <tbody>
          {pronouns.map((p, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 10px', fontWeight: 600, color: '#78350F', width: 100 }}>{p}</td>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 10px', height: 26 }} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ConversionTableRenderer({ config = {} }) {
  const headers = config.headers || ['Unit', 'Equivalent'];
  const rows = config.rows || 4;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        {headers.map((h, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{h}</th>)}
      </tr></thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>{headers.map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 28 }} />)}</tr>
        ))}
      </tbody>
    </table>
  );
}

export function CauseEffectChartRenderer({ config = {} }) {
  const rows = config.rows || 3;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F', width: '50%' }}>Cause</th>
        <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F', width: '50%' }}>Effect</th>
      </tr></thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 32 }} />
            <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 32 }}>
              <span style={{ color: '#F97316', fontSize: 14, marginRight: 4 }}>&rarr;</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DesignElementsChartRenderer({ config = {} }) {
  const elements = config.elements || ['Line', 'Shape', 'Color', 'Texture', 'Space'];
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>Element</th>
        <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>Description</th>
        <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>Example in Work</th>
      </tr></thead>
      <tbody>
        {elements.map((e, i) => (
          <tr key={i}>
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 600, color: '#78350F' }}>{e}</td>
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MaterialsTableRenderer({ config = {} }) {
  const headers = config.headers || ['Material', 'Quantity', 'Purpose'];
  const rows = config.rows || 4;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        {headers.map((h, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{h}</th>)}
      </tr></thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>{headers.map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 28 }} />)}</tr>
        ))}
      </tbody>
    </table>
  );
}

export function TraceTableRenderer({ config = {} }) {
  const variables = config.variables || ['Step', 'x', 'y', 'Output'];
  const rows = config.rows || 5;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'monospace' }}>
      <thead><tr>
        {variables.map((v, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#F5F5F4', fontWeight: 600, color: '#78350F' }}>{v}</th>)}
      </tr></thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', textAlign: 'center', color: '#78716C' }}>{r + 1}</td>
            {Array.from({ length: variables.length - 1 }).map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DeclensionTableRenderer({ config = {} }) {
  const cases = config.cases || ['Nominative', 'Genitive', 'Dative', 'Accusative'];
  const genders = config.genders || ['Masculine', 'Feminine', 'Neuter'];
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        <th style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#F5F5F4', color: '#78350F' }}>Case</th>
        {genders.map((g, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{g}</th>)}
      </tr></thead>
      <tbody>
        {cases.map((c, ri) => (
          <tr key={ri}>
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 600, color: '#78350F' }}>{c}</td>
            {genders.map((_, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CaseTableRenderer({ config = {} }) {
  const cases = config.cases || ['Nominative', 'Accusative', 'Genitive', 'Dative', 'Ablative'];
  const numbers = config.numbers || ['Singular', 'Plural'];
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        <th style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#F5F5F4', color: '#78350F' }}>Case</th>
        {numbers.map((n, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{n}</th>)}
      </tr></thead>
      <tbody>
        {cases.map((c, ri) => (
          <tr key={ri}>
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 600, color: '#78350F' }}>{c}</td>
            {numbers.map((_, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PeriodicTableRefRenderer({ config = {} }) {
  const elements = config.elements || [
    { symbol: 'H', number: 1, name: 'Hydrogen' },
    { symbol: 'He', number: 2, name: 'Helium' },
    { symbol: 'Li', number: 3, name: 'Lithium' },
    { symbol: 'Be', number: 4, name: 'Beryllium' },
  ];
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Reference Elements</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {elements.map((el, i) => (
          <div key={i} style={{ width: 60, border: '1px solid #E7E5E4', borderRadius: 6, padding: 4, textAlign: 'center', background: '#FEF9F2' }}>
            <div style={{ fontSize: 8, color: '#A8A29E' }}>{el.number}</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#78350F' }}>{el.symbol}</div>
            <div style={{ fontSize: 7, color: '#78716C' }}>{el.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── LINED / WRITING AREA COMPONENTS ────────────────────────────────────────

export function WorkSpaceGridRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 8, height: config.height || (gc.baseFontSize >= 16 ? 160 : 120), background: 'repeating-linear-gradient(#FEF9F2, #FEF9F2 19px, #E7E5E4 19px, #E7E5E4 20px), repeating-linear-gradient(90deg, #FEF9F2, #FEF9F2 19px, #E7E5E4 19px, #E7E5E4 20px)', backgroundSize: '20px 20px' }}>
      <div style={{ fontSize: 9, color: '#A8A29E', padding: 4 }}>Work Space</div>
    </div>
  );
}

export function HandwritingLinesRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const lines = config.lines || 4;
  const lineH = gc.baseFontSize >= 16 ? 48 : 36;
  return (
    <div>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} style={{ height: lineH, position: 'relative', borderBottom: '2px solid #1C1917' }}>
          <div style={{ position: 'absolute', top: '35%', left: 0, right: 0, borderBottom: '1px dashed #FDBA74' }} />
          <div style={{ position: 'absolute', top: '65%', left: 0, right: 0, borderBottom: '1px solid #E7E5E4' }} />
        </div>
      ))}
    </div>
  );
}

export function SketchSpaceRenderer({ config = {} }) {
  return (
    <div style={{ border: '2px dashed #FDBA74', borderRadius: 14, height: config.height || 180, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED' }}>
      <span style={{ fontSize: 12, color: '#FDBA74' }}>{config.prompt || 'Sketch / Draw Here'}</span>
    </div>
  );
}

export function ConstructionSpaceRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, height: config.height || 200, background: '#FAFAF9', position: 'relative' }}>
      <div style={{ position: 'absolute', top: 6, left: 10, fontSize: 10, fontWeight: 600, color: '#78350F' }}>Construction Space</div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <span style={{ fontSize: 11, color: '#A8A29E' }}>Use compass and straightedge</span>
      </div>
    </div>
  );
}

export function TechnicalDrawingSpaceRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, height: config.height || 200, background: '#FAFAF9', position: 'relative' }}>
      <div style={{ position: 'absolute', top: 6, left: 10, fontSize: 10, fontWeight: 600, color: '#78350F' }}>Technical Drawing</div>
      <div style={{ position: 'absolute', bottom: 6, right: 10, fontSize: 9, color: '#A8A29E' }}>Scale: {config.scale || '1:1'}</div>
    </div>
  );
}

export function MolarCalcSpaceRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Molar Calculation Space</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, fontSize: 10, color: '#78716C' }}>
        <span style={{ padding: '2px 8px', background: '#FFF7ED', borderRadius: 4, border: '1px solid #FDBA74' }}>n = m / M</span>
        <span style={{ padding: '2px 8px', background: '#FFF7ED', borderRadius: 4, border: '1px solid #FDBA74' }}>M = g/mol</span>
      </div>
      {Array.from({ length: 4 }).map((_, i) => <div key={i} style={{ borderBottom: '1px solid #E7E5E4', height: 24 }} />)}
    </div>
  );
}

export function LabReportRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const sections = config.sections || ['Purpose', 'Hypothesis', 'Materials', 'Procedure', 'Data / Observations', 'Analysis', 'Conclusion'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Lab Report</div>
      <div style={{ padding: 10 }}>
        {sections.map((s, i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 2 }}>{s}</div>
            <div style={{ borderBottom: '1px solid #E7E5E4', height: 22 }} />
            <div style={{ borderBottom: '1px solid #E7E5E4', height: 22 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ObservationBoxRenderer({ config = {} }) {
  return sectionBox(config.title || 'Observations', (
    <div>
      {labeledLines(['I see...', 'I notice...', 'I wonder...'])}
      <div style={{ border: '1px dashed #FDBA74', borderRadius: 8, height: 60, marginTop: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 10, color: '#FDBA74' }}>Sketch</span>
      </div>
    </div>
  ));
}

export function WritingPromptRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div>
      <div style={{ background: '#FFF7ED', borderLeft: '3px solid #F97316', padding: '8px 12px', fontSize: gc.baseFontSize - 1, color: '#78350F', borderRadius: '0 8px 8px 0', marginBottom: 8 }}>
        {config.prompt || 'Write about a time when...'}
      </div>
      {writingArea(null, config.lines || 8, gc)}
    </div>
  );
}

export function EssayPromptWlRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div>
      <div style={{ background: '#FFF7ED', padding: '10px 14px', borderRadius: 10, border: '1px solid #FDBA74', marginBottom: 8 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: '#F97316', marginBottom: 4 }}>Essay Prompt</div>
        <div style={{ fontSize: gc.baseFontSize - 1, color: '#1C1917' }}>{config.prompt || 'Discuss the significance of...'}</div>
      </div>
      {writingArea(null, config.lines || 12, gc)}
    </div>
  );
}

export function ReflectionJournalRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Reflection Journal</div>
      <div style={{ padding: 10 }}>
        {labeledLines([config.prompt1 || 'What I learned...', config.prompt2 || 'How I can apply this...', config.prompt3 || 'Questions I still have...'], 28)}
      </div>
    </div>
  );
}

export function PortfolioReflectionRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Portfolio Reflection', [
    'Piece / Project Title',
    'What I did well',
    'What I would change',
    'Skills demonstrated',
    'Growth since last piece',
  ]);
}

// ─── MATH-SPECIFIC COMPONENTS ───────────────────────────────────────────────

export function EquationEditorRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Equation</div>
      <div style={{ fontFamily: 'monospace', fontSize: gc.baseFontSize + 2, padding: '8px 12px', background: '#FAFAF9', borderRadius: 6, minHeight: 36, border: '1px solid #E7E5E4' }}>
        {config.equation || 'y = mx + b'}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
        {['+', '-', '\u00d7', '\u00f7', '=', '\u00b2', '\u221a', '\u03c0', '\u2264', '\u2265'].map((s, i) => (
          <span key={i} style={{ fontSize: 12, padding: '2px 8px', background: '#FFF7ED', borderRadius: 4, border: '1px solid #FDBA74', color: '#78350F' }}>{s}</span>
        ))}
      </div>
    </div>
  );
}

export function FractionVisualRenderer({ config = {} }) {
  const numerator = config.numerator || 3;
  const denominator = config.denominator || 4;
  const type = config.type || 'circle';
  if (type === 'bar') {
    return (
      <div style={{ margin: '0 auto', width: 200 }}>
        <div style={{ display: 'flex', height: 30, border: '2px solid #78350F', borderRadius: 4, overflow: 'hidden' }}>
          {Array.from({ length: denominator }).map((_, i) => (
            <div key={i} style={{ flex: 1, background: i < numerator ? '#F97316' : 'white', borderRight: i < denominator - 1 ? '1px solid #78350F' : 'none' }} />
          ))}
        </div>
        <div style={{ textAlign: 'center', fontSize: 14, fontWeight: 600, color: '#78350F', marginTop: 4 }}>{numerator}/{denominator}</div>
      </div>
    );
  }
  // circle
  const r = 40;
  const sliceAngle = 360 / denominator;
  return (
    <div style={{ textAlign: 'center' }}>
      <svg width={100} height={100} viewBox="0 0 100 100">
        {Array.from({ length: denominator }).map((_, i) => {
          const startAngle = (i * sliceAngle - 90) * Math.PI / 180;
          const endAngle = ((i + 1) * sliceAngle - 90) * Math.PI / 180;
          const x1 = 50 + r * Math.cos(startAngle);
          const y1 = 50 + r * Math.sin(startAngle);
          const x2 = 50 + r * Math.cos(endAngle);
          const y2 = 50 + r * Math.sin(endAngle);
          const large = sliceAngle > 180 ? 1 : 0;
          return (
            <path key={i} d={`M50,50 L${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} Z`}
              fill={i < numerator ? '#F97316' : '#FFF7ED'} stroke="#78350F" strokeWidth={1} />
          );
        })}
      </svg>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#78350F' }}>{numerator}/{denominator}</div>
    </div>
  );
}

export function MultiplicationGridRenderer({ config = {} }) {
  const a = config.a || 12;
  const b = config.b || 14;
  const aStr = String(a);
  const bStr = String(b);
  return (
    <div style={{ margin: '0 auto' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4, textAlign: 'center' }}>{a} x {b}</div>
      <table style={{ borderCollapse: 'collapse', fontSize: 12, margin: '0 auto' }}>
        <thead>
          <tr>
            <th style={{ border: '1px solid #E7E5E4', padding: '4px 12px', background: '#F97316', color: 'white' }}>\u00d7</th>
            {bStr.split('').map((d, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '4px 12px', background: '#FFF7ED', color: '#78350F' }}>{d}{i === 0 && bStr.length > 1 ? '0'.repeat(bStr.length - 1 - i) : ''}</th>)}
          </tr>
        </thead>
        <tbody>
          {aStr.split('').map((d, ri) => (
            <tr key={ri}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 12px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{d}{ri === 0 && aStr.length > 1 ? '0'.repeat(aStr.length - 1 - ri) : ''}</td>
              {bStr.split('').map((_, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: '4px 12px', height: 28, width: 50 }} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function InequalityNumberLineRenderer({ config = {} }) {
  const min = config.min ?? -5;
  const max = config.max ?? 5;
  const ticks = [];
  for (let i = min; i <= max; i++) ticks.push(i);
  return (
    <div style={{ position: 'relative', height: 50, margin: '10px 20px' }}>
      <div style={{ position: 'absolute', top: 20, left: 0, right: 0, height: 2, background: '#1C1917' }} />
      <div style={{ position: 'absolute', top: 18, left: 0, width: 0, height: 0, borderTop: '5px solid transparent', borderBottom: '5px solid transparent', borderRight: '8px solid #1C1917' }} />
      <div style={{ position: 'absolute', top: 18, right: 0, width: 0, height: 0, borderTop: '5px solid transparent', borderBottom: '5px solid transparent', borderLeft: '8px solid #1C1917' }} />
      {ticks.map((t, i) => (
        <div key={i} style={{ position: 'absolute', top: 12, left: `${((t - min) / (max - min)) * 100}%`, transform: 'translateX(-50%)' }}>
          <div style={{ width: 2, height: 16, background: '#1C1917', margin: '0 auto' }} />
          <div style={{ fontSize: 10, textAlign: 'center', marginTop: 2, color: '#78716C' }}>{t}</div>
        </div>
      ))}
    </div>
  );
}

export function SystemOfEquationsRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const equations = config.equations || ['2x + 3y = 12', 'x - y = 1'];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ borderLeft: '2px solid #1C1917', padding: '4px 0 4px 12px' }}>
        {equations.map((eq, i) => (
          <div key={i} style={{ fontFamily: 'monospace', fontSize: gc.baseFontSize, lineHeight: 1.8, color: '#1C1917' }}>{eq}</div>
        ))}
      </div>
    </div>
  );
}

export function LimitExpressionRenderer({ config = {} }) {
  return (
    <div style={{ fontFamily: 'monospace', fontSize: 16, textAlign: 'center', padding: 12 }}>
      <span style={{ fontSize: 12, color: '#78716C' }}>lim</span>
      <span style={{ fontSize: 10, color: '#78350F', position: 'relative', top: 8, left: -20 }}>{config.variable || 'x'}&rarr;{config.approaching || '\u221e'}</span>
      <span style={{ marginLeft: 8 }}>{config.expression || 'f(x)'}</span>
      <span style={{ marginLeft: 8 }}> = </span>
      <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 40, height: 20 }} />
    </div>
  );
}

export function IntegralDerivativeRenderer({ config = {} }) {
  const type = config.type || 'integral';
  return (
    <div style={{ fontFamily: 'monospace', fontSize: 16, textAlign: 'center', padding: 12 }}>
      {type === 'integral' ? (
        <span>
          <span style={{ fontSize: 28, lineHeight: 1, color: '#78350F' }}>&int;</span>
          <span style={{ fontSize: 10, position: 'relative', top: -10 }}>{config.upper || 'b'}</span>
          <span style={{ fontSize: 10, position: 'relative', top: 10, left: -8 }}>{config.lower || 'a'}</span>
          <span style={{ marginLeft: 4 }}>{config.expression || 'f(x) dx'}</span>
        </span>
      ) : (
        <span>
          <span style={{ color: '#78350F' }}>d/d{config.variable || 'x'}</span>
          <span style={{ marginLeft: 4 }}>[{config.expression || 'f(x)'}]</span>
        </span>
      )}
      <span style={{ marginLeft: 8 }}> = </span>
      <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 60, height: 20 }} />
    </div>
  );
}

export function PiecewiseFunctionRenderer({ config = {} }) {
  const pieces = config.pieces || [
    { expression: 'x + 1', condition: 'x < 0' },
    { expression: 'x\u00b2', condition: '0 \u2264 x \u2264 2' },
    { expression: '5', condition: 'x > 2' },
  ];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 8 }}>
      <span style={{ fontFamily: 'monospace', fontSize: 14, color: '#78350F' }}>f(x) = </span>
      <div style={{ borderLeft: '2px solid #1C1917', padding: '2px 0 2px 10px' }}>
        {pieces.map((p, i) => (
          <div key={i} style={{ fontFamily: 'monospace', fontSize: 13, lineHeight: 1.8 }}>
            <span>{p.expression}</span>
            <span style={{ color: '#78716C', marginLeft: 16 }}>if {p.condition}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SeriesSummationRenderer({ config = {} }) {
  return (
    <div style={{ fontFamily: 'monospace', fontSize: 16, textAlign: 'center', padding: 12 }}>
      <span style={{ fontSize: 24, color: '#78350F' }}>&Sigma;</span>
      <span style={{ fontSize: 10, position: 'relative', top: -12 }}>{config.upper || 'n'}</span>
      <span style={{ fontSize: 10, position: 'relative', top: 10, left: -10 }}>{config.lower || 'i=1'}</span>
      <span style={{ marginLeft: 6 }}>{config.expression || 'a_i'}</span>
      <span style={{ marginLeft: 8 }}> = </span>
      <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 50, height: 20 }} />
    </div>
  );
}

export function KinematicsEquationsRenderer({ config = {} }) {
  const equations = config.equations || [
    'v = v\u2080 + at',
    '\u0394x = v\u2080t + \u00bdat\u00b2',
    'v\u00b2 = v\u2080\u00b2 + 2a\u0394x',
    '\u0394x = \u00bd(v + v\u2080)t',
  ];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10, background: '#FEF9F2' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Kinematics Equations</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        {equations.map((eq, i) => (
          <div key={i} style={{ fontFamily: 'monospace', fontSize: 12, padding: '4px 8px', background: 'white', borderRadius: 4, border: '1px solid #E7E5E4' }}>{eq}</div>
        ))}
      </div>
      <div style={{ marginTop: 8 }}>
        {Array.from({ length: 3 }).map((_, i) => <div key={i} style={{ borderBottom: '1px solid #E7E5E4', height: 24 }} />)}
      </div>
    </div>
  );
}

// ─── SCIENCE-SPECIFIC COMPONENTS ────────────────────────────────────────────

export function PunnettSquareRenderer({ config = {} }) {
  const parent1 = config.parent1 || ['P', 'p'];
  const parent2 = config.parent2 || ['P', 'p'];
  return (
    <div style={{ margin: '0 auto', width: 'fit-content' }}>
      <table style={{ borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr>
            <th style={{ border: '1px solid #E7E5E4', padding: 8, width: 40, background: '#F97316', color: 'white' }}></th>
            {parent2.map((a, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: 8, width: 50, background: '#FFF7ED', fontWeight: 700, color: '#78350F' }}>{a}</th>)}
          </tr>
        </thead>
        <tbody>
          {parent1.map((a, ri) => (
            <tr key={ri}>
              <td style={{ border: '1px solid #E7E5E4', padding: 8, background: '#FFF7ED', fontWeight: 700, color: '#78350F' }}>{a}</td>
              {parent2.map((b, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: 8, height: 40, textAlign: 'center', fontSize: 13, color: '#1C1917' }}>{a}{b}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CellDiagramRenderer({ config = {} }) {
  const type = config.type || 'animal';
  const parts = type === 'plant'
    ? ['Cell Wall', 'Cell Membrane', 'Nucleus', 'Chloroplast', 'Vacuole', 'Mitochondria']
    : ['Cell Membrane', 'Nucleus', 'Mitochondria', 'Ribosome', 'ER', 'Golgi Body'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{type === 'plant' ? 'Plant' : 'Animal'} Cell</div>
      <div style={{ display: 'flex', padding: 10, gap: 10 }}>
        <div style={{ width: 120, height: 120, borderRadius: type === 'plant' ? 8 : '50%', border: '3px solid #78350F', background: '#FEF9F2', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <div style={{ width: 30, height: 30, borderRadius: '50%', border: '2px solid #F97316', background: '#FFF7ED' }} />
        </div>
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Label the parts:</div>
          {parts.map((p, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 2, display: 'flex', gap: 4 }}>
              <span style={{ color: '#F97316' }}>{i + 1}.</span>
              <span style={{ borderBottom: '1px solid #E7E5E4', flex: 1, height: 16 }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function DnaRnaSequenceRenderer({ config = {} }) {
  const sequence = config.sequence || 'A T G C C G A T';
  const bases = sequence.split(/\s+/);
  const colors = { A: '#F97316', T: '#78350F', G: '#16A34A', C: '#2563EB', U: '#DC2626' };
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>{config.label || 'DNA Strand'}</div>
      <div style={{ display: 'flex', gap: 2, marginBottom: 6 }}>
        {bases.map((b, i) => (
          <div key={i} style={{ width: 28, height: 28, borderRadius: 4, background: colors[b] || '#78716C', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700 }}>{b}</div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: '#78350F', marginBottom: 4 }}>Complementary Strand:</div>
      <div style={{ display: 'flex', gap: 2 }}>
        {bases.map((_, i) => (
          <div key={i} style={{ width: 28, height: 28, borderRadius: 4, border: '2px solid #E7E5E4', display: 'flex', alignItems: 'center', justifyContent: 'center' }} />
        ))}
      </div>
    </div>
  );
}

export function PhylogeneticTreeRenderer({ config = {} }) {
  const species = config.species || ['Species A', 'Species B', 'Species C', 'Species D'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Phylogenetic Tree</div>
      <svg width="100%" height={species.length * 30 + 20} viewBox={`0 0 300 ${species.length * 30 + 20}`}>
        <line x1={40} y1={10} x2={40} y2={species.length * 30} stroke="#78350F" strokeWidth={2} />
        {species.map((s, i) => (
          <g key={i}>
            <line x1={40} y1={20 + i * 30} x2={100 + i * 20} y2={20 + i * 30} stroke="#78350F" strokeWidth={1.5} />
            <text x={105 + i * 20} y={24 + i * 30} fontSize={11} fill="#1C1917">{s}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export function ChemicalEquationBalancerRenderer({ config = {} }) {
  const equation = config.equation || '___ H\u2082 + ___ O\u2082 \u2192 ___ H\u2082O';
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 12, textAlign: 'center' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Balance the Equation</div>
      <div style={{ fontFamily: 'monospace', fontSize: 16, color: '#1C1917', letterSpacing: 2 }}>{equation}</div>
      <div style={{ marginTop: 8, fontSize: 10, color: '#78716C' }}>Write coefficients in the blanks</div>
    </div>
  );
}

export function LewisDotRenderer({ config = {} }) {
  const element = config.element || 'O';
  return (
    <div style={{ textAlign: 'center', padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Lewis Dot Structure</div>
      <div style={{ width: 100, height: 100, margin: '0 auto', position: 'relative', border: '1px dashed #E7E5E4', borderRadius: 8 }}>
        <span style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontSize: 24, fontWeight: 700, color: '#78350F' }}>{element}</span>
        <span style={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', fontSize: 18, color: '#F97316' }}>&bull;</span>
        <span style={{ position: 'absolute', bottom: 8, left: '50%', transform: 'translateX(-50%)', fontSize: 18, color: '#F97316' }}>&bull;</span>
        <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', fontSize: 18, color: '#F97316' }}>&bull;</span>
        <span style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', fontSize: 18, color: '#F97316' }}>&bull;</span>
      </div>
    </div>
  );
}

export function ElectronConfigRenderer({ config = {} }) {
  const element = config.element || 'Carbon';
  const shells = config.shells || ['1s\u00b2', '2s\u00b2', '2p\u00b2'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Electron Configuration: {element}</div>
      <div style={{ fontFamily: 'monospace', fontSize: 14, color: '#1C1917', padding: '6px 10px', background: '#FEF9F2', borderRadius: 6 }}>
        {shells.join(' ')}
      </div>
      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 10, color: '#78350F', marginBottom: 4 }}>Orbital Diagram:</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {shells.map((s, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ width: 24, height: 20, border: '1px solid #E7E5E4', borderRadius: 3 }} />
              <span style={{ fontSize: 8, color: '#78716C', marginTop: 2 }}>{s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function FreeBodyDiagramRenderer({ config = {} }) {
  return (
    <div style={{ textAlign: 'center', padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Free Body Diagram</div>
      <svg width={160} height={160} viewBox="0 0 160 160">
        <rect x={60} y={60} width={40} height={40} fill="#FFF7ED" stroke="#78350F" strokeWidth={2} rx={4} />
        <line x1={80} y1={60} x2={80} y2={20} stroke="#F97316" strokeWidth={2} markerEnd="url(#arrow)" />
        <line x1={80} y1={100} x2={80} y2={140} stroke="#F97316" strokeWidth={2} markerEnd="url(#arrow)" />
        <line x1={60} y1={80} x2={20} y2={80} stroke="#F97316" strokeWidth={2} markerEnd="url(#arrow)" />
        <line x1={100} y1={80} x2={140} y2={80} stroke="#F97316" strokeWidth={2} markerEnd="url(#arrow)" />
        <defs><marker id="arrow" markerWidth={8} markerHeight={8} refX={8} refY={4} orient="auto"><path d="M0,0 L8,4 L0,8" fill="#F97316" /></marker></defs>
        <text x={80} y={15} fontSize={9} fill="#78716C" textAnchor="middle">{config.topLabel || 'F_N'}</text>
        <text x={80} y={155} fontSize={9} fill="#78716C" textAnchor="middle">{config.bottomLabel || 'F_g'}</text>
        <text x={12} y={84} fontSize={9} fill="#78716C" textAnchor="middle">{config.leftLabel || 'F_f'}</text>
        <text x={148} y={84} fontSize={9} fill="#78716C" textAnchor="middle">{config.rightLabel || 'F_a'}</text>
      </svg>
    </div>
  );
}

export function CircuitDiagramRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Circuit Diagram</div>
      <svg width="100%" height={120} viewBox="0 0 240 120">
        <rect x={20} y={20} width={200} height={80} fill="none" stroke="#78350F" strokeWidth={2} rx={4} />
        {/* Battery */}
        <line x1={20} y1={60} x2={20} y2={40} stroke="#78350F" strokeWidth={3} />
        <line x1={16} y1={50} x2={24} y2={50} stroke="#78350F" strokeWidth={2} />
        <text x={6} y={54} fontSize={8} fill="#78716C">+</text>
        {/* Resistor */}
        <path d="M100,20 L110,15 L120,25 L130,15 L140,25 L150,20" fill="none" stroke="#F97316" strokeWidth={2} />
        {/* Bulb */}
        <circle cx={220} cy={60} r={12} fill="none" stroke="#F97316" strokeWidth={2} />
        <line x1={214} y1={54} x2={226} y2={66} stroke="#F97316" strokeWidth={1} />
        <line x1={226} y1={54} x2={214} y2={66} stroke="#F97316" strokeWidth={1} />
      </svg>
    </div>
  );
}

export function VectorDiagramRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Vector Diagram</div>
      <svg width={200} height={160} viewBox="0 0 200 160">
        <defs><marker id="varrow" markerWidth={8} markerHeight={8} refX={8} refY={4} orient="auto"><path d="M0,0 L8,4 L0,8" fill="#F97316" /></marker></defs>
        <line x1={20} y1={140} x2={180} y2={140} stroke="#E7E5E4" strokeWidth={1} />
        <line x1={20} y1={10} x2={20} y2={140} stroke="#E7E5E4" strokeWidth={1} />
        <line x1={20} y1={140} x2={160} y2={40} stroke="#F97316" strokeWidth={2} markerEnd="url(#varrow)" />
        <line x1={20} y1={140} x2={160} y2={140} stroke="#78350F" strokeWidth={2} markerEnd="url(#varrow)" />
        <line x1={20} y1={140} x2={20} y2={40} stroke="#78350F" strokeWidth={2} markerEnd="url(#varrow)" />
        <text x={170} y={38} fontSize={10} fill="#F97316">R</text>
        <text x={165} y={155} fontSize={10} fill="#78350F">x</text>
        <text x={6} y={38} fontSize={10} fill="#78350F">y</text>
      </svg>
    </div>
  );
}

export function DiagramLabelRenderer({ config = {} }) {
  const labels = config.labels || ['Part A', 'Part B', 'Part C', 'Part D'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{config.title || 'Label the Diagram'}</div>
      <div style={{ display: 'flex', padding: 10, gap: 10 }}>
        <div style={{ width: 140, height: 120, border: '2px dashed #FDBA74', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED', flexShrink: 0 }}>
          <span style={{ fontSize: 10, color: '#FDBA74' }}>Diagram</span>
        </div>
        <div>
          {labels.map((l, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 4, display: 'flex', gap: 4, alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#F97316' }}>{i + 1}.</span>
              <span style={{ borderBottom: '1px solid #E7E5E4', width: 100, height: 16, display: 'inline-block' }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ScienceGraphicOrganizerRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Science Graphic Organizer', [
    config.section1 || 'Observation',
    config.section2 || 'Hypothesis',
    config.section3 || 'Evidence',
    config.section4 || 'Conclusion',
  ]);
}

export function BodyDiagramRenderer({ config = {} }) {
  const labels = config.labels || ['Head', 'Torso', 'Arms', 'Legs'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{config.title || 'Body Diagram'}</div>
      <div style={{ display: 'flex', padding: 10, gap: 10 }}>
        <div style={{ width: 100, height: 160, border: '2px dashed #FDBA74', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED', flexShrink: 0 }}>
          <span style={{ fontSize: 10, color: '#FDBA74' }}>Body</span>
        </div>
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Label:</div>
          {labels.map((l, i) => (
            <div key={i} style={{ fontSize: 11, marginBottom: 4, display: 'flex', gap: 4, alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#F97316' }}>{i + 1}.</span>
              <span style={{ borderBottom: '1px solid #E7E5E4', width: 100, height: 16, display: 'inline-block' }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── STRUCTURED TEXT / ANALYSIS FRAMES ──────────────────────────────────────

export function TextEvidenceChartRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Text Evidence', [
    'Claim / Statement',
    'Evidence from Text (with page/line #)',
    'Explanation / Reasoning',
  ]);
}

export function LiteraryAnalysisFrameRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Literary Analysis', [
    'Theme / Central Idea',
    'Literary Device Used',
    'Textual Evidence (quote)',
    'Analysis / Explanation',
  ]);
}

export function RhetoricalAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Rhetorical Analysis', [
    'Speaker / Author',
    'Audience',
    'Purpose',
    'Ethos / Pathos / Logos',
    'Effectiveness',
  ]);
}

export function ArgumentOutlineRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Argument Outline', [
    'Thesis / Claim',
    'Reason 1 + Evidence',
    'Reason 2 + Evidence',
    'Counterargument',
    'Rebuttal',
    'Conclusion',
  ]);
}

export function SynthesisSourceChartRenderer({ config = {} }) {
  const sources = config.sources || 3;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Synthesis Source Chart</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Source</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Main Idea</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Key Evidence</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Connection</th>
        </tr></thead>
        <tbody>
          {Array.from({ length: sources }).map((_, r) => (
            <tr key={r}>
              <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', color: '#78716C' }}>Source {r + 1}</td>
              <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 32 }} />
              <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 32 }} />
              <td style={{ border: '1px solid #E7E5E4', padding: '6px 8px', height: 32 }} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CloseReadingGuideRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Close Reading Guide', [
    'First Read: What is the text about?',
    'Second Read: How does the author develop ideas?',
    'Third Read: What is the author\'s purpose?',
    'Key Vocabulary',
    'Questions for Discussion',
  ]);
}

export function PoetryAnnotationRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Poetry Annotation</div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 0 }}>
        <div style={{ padding: 10, borderRight: '1px solid #E7E5E4' }}>
          <div style={{ fontSize: gc.baseFontSize - 1, fontStyle: 'italic', color: '#1C1917', lineHeight: gc.lineHeight + 0.2 }}>
            {config.poem || 'Paste poem text here for annotation...'}
          </div>
        </div>
        <div style={{ padding: 10 }}>
          {labeledLines(['Rhyme Scheme', 'Meter', 'Figurative Language', 'Tone / Mood'])}
        </div>
      </div>
    </div>
  );
}

export function ReadingComprehensionWlRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Reading Comprehension</div>
      <div style={{ padding: 10 }}>
        {labeledLines([
          'Main Idea',
          'Key Details',
          'Vocabulary in Context',
          'Author\'s Purpose',
          'Personal Connection',
        ], gc.baseFontSize >= 16 ? 32 : 24)}
      </div>
    </div>
  );
}

export function PrimarySourceAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Primary Source Analysis', [
    'Source Type & Date',
    'Author / Creator',
    'Historical Context',
    'Main Idea / Purpose',
    'Point of View / Bias',
    'Significance',
  ]);
}

export function DbqDocumentAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'DBQ Document Analysis', [
    'Document Title / Source',
    'Historical Context',
    'Intended Audience',
    'Purpose',
    'Point of View',
    'How does this document support your thesis?',
  ]);
}

export function AmendmentAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Amendment Analysis', [
    'Amendment Number & Text',
    'Historical Background',
    'Original Intent',
    'Modern Application',
    'Key Court Cases',
  ]);
}

export function CourtCaseBriefRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Court Case Brief', [
    'Case Name & Year',
    'Facts of the Case',
    'Constitutional Question',
    'Decision (majority / dissent)',
    'Significance / Precedent',
  ]);
}

export function PolicyAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Policy Analysis', [
    'Policy Name / Description',
    'Problem it Addresses',
    'Stakeholders',
    'Pros',
    'Cons',
    'Recommendation',
  ]);
}

export function ScotusComparisonRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>SCOTUS Case Comparison</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Criteria</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Case 1</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Case 2</th>
        </tr></thead>
        <tbody>
          {['Facts', 'Constitutional Issue', 'Decision', 'Reasoning', 'Impact'].map((c, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 600, color: '#78350F' }}>{c}</td>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LeqOutlineRenderer({ config = {} }) {
  return analysisFrame(config.title || 'LEQ Outline', [
    'Thesis Statement',
    'Contextualization',
    'Evidence 1 + Analysis',
    'Evidence 2 + Analysis',
    'Evidence 3 + Analysis',
    'Complexity / Synthesis',
  ]);
}

export function CcotAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Continuity & Change Over Time', [
    'Time Period / Region',
    'Continuities (what stayed the same)',
    'Changes (what shifted)',
    'Causes of Change',
    'Effects / Impact',
  ]);
}

export function CharacterAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Character Analysis', [
    'Character Name',
    'Physical / Background Description',
    'Personality Traits (with evidence)',
    'Motivation',
    'Conflict',
    'Character Arc / Change',
  ]);
}

export function ArtCritiqueGuideRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Art Critique', [
    'Describe: What do you see?',
    'Analyze: How is it organized?',
    'Interpret: What does it mean?',
    'Evaluate: Is it successful? Why?',
  ]);
}

export function ContextualAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Contextual Analysis', [
    'Historical Context',
    'Social / Cultural Context',
    'Artist / Author Background',
    'Influence on the Work',
    'Modern Relevance',
  ]);
}

export function ArtworkComparisonRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Artwork Comparison</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}></th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Artwork 1</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Artwork 2</th>
        </tr></thead>
        <tbody>
          {['Title / Artist', 'Medium', 'Subject', 'Style / Movement', 'Similarities', 'Differences'].map((c, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 600, color: '#78350F' }}>{c}</td>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CulturalComparisonRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Cultural Comparison</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>Aspect</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>{config.culture1 || 'Culture 1'}</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#F5F5F4', color: '#78350F' }}>{config.culture2 || 'Culture 2'}</th>
        </tr></thead>
        <tbody>
          {(config.aspects || ['Language', 'Customs', 'Values', 'Traditions']).map((a, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 600, color: '#78350F' }}>{a}</td>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 28 }} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function WellnessAssessmentRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Wellness Assessment', [
    'Physical Health',
    'Mental / Emotional Health',
    'Social Health',
    'Goals for Improvement',
    'Action Steps',
  ]);
}

export function DecisionMakingModelRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Decision Making Model', [
    'Define the Problem',
    'List Options',
    'Weigh Pros and Cons',
    'Make a Decision',
    'Evaluate the Outcome',
  ]);
}

export function StressManagementPlanRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Stress Management Plan', [
    'Identify Stressors',
    'Physical Symptoms',
    'Emotional Responses',
    'Coping Strategies',
    'Support System',
    'Action Plan',
  ]);
}

export function SwotAnalysisRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>SWOT Analysis</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
        {[
          { label: 'Strengths', bg: '#DCFCE7' },
          { label: 'Weaknesses', bg: '#FEE2E2' },
          { label: 'Opportunities', bg: '#DBEAFE' },
          { label: 'Threats', bg: '#FEF3C7' },
        ].map((q, i) => (
          <div key={i} style={{ padding: 10, border: '1px solid #E7E5E4', minHeight: 60 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', padding: '2px 6px', background: q.bg, borderRadius: 4, display: 'inline-block', marginBottom: 4 }}>{q.label}</div>
            <div style={{ borderBottom: '1px solid #E7E5E4', height: 20 }} />
            <div style={{ borderBottom: '1px solid #E7E5E4', height: 20 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function CostBenefitAnalysisRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Cost-Benefit Analysis</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        <div style={{ padding: 10, borderRight: '1px solid #E7E5E4' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#DC2626', marginBottom: 6 }}>Costs</div>
          {Array.from({ length: 4 }).map((_, i) => <div key={i} style={{ borderBottom: '1px solid #E7E5E4', height: 22 }} />)}
        </div>
        <div style={{ padding: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#16A34A', marginBottom: 6 }}>Benefits</div>
          {Array.from({ length: 4 }).map((_, i) => <div key={i} style={{ borderBottom: '1px solid #E7E5E4', height: 22 }} />)}
        </div>
      </div>
    </div>
  );
}

export function BusinessPlanSectionRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Business Plan', [
    'Executive Summary',
    'Product / Service Description',
    'Target Market',
    'Revenue Model',
    'Marketing Strategy',
    'Financial Projections',
  ]);
}

// ─── VISUAL / CREATIVE COMPONENTS ───────────────────────────────────────────

export function ColorWheelRenderer({ config = {} }) {
  const colors = ['#FF0000', '#FF8000', '#FFFF00', '#00FF00', '#0000FF', '#8000FF'];
  const r = 50;
  return (
    <div style={{ textAlign: 'center', padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Color Wheel</div>
      <svg width={120} height={120} viewBox="0 0 120 120">
        {colors.map((c, i) => {
          const angle1 = (i * 60 - 90) * Math.PI / 180;
          const angle2 = ((i + 1) * 60 - 90) * Math.PI / 180;
          const x1 = 60 + r * Math.cos(angle1);
          const y1 = 60 + r * Math.sin(angle1);
          const x2 = 60 + r * Math.cos(angle2);
          const y2 = 60 + r * Math.sin(angle2);
          return <path key={i} d={`M60,60 L${x1},${y1} A${r},${r} 0 0,1 ${x2},${y2} Z`} fill={c} opacity={0.7} stroke="white" strokeWidth={1} />;
        })}
      </svg>
      <div style={{ display: 'flex', gap: 4, justifyContent: 'center', marginTop: 4 }}>
        {['Primary', 'Secondary', 'Tertiary'].map((l, i) => (
          <span key={i} style={{ fontSize: 9, padding: '1px 6px', background: '#FFF7ED', borderRadius: 3, border: '1px solid #FDBA74', color: '#78350F' }}>{l}</span>
        ))}
      </div>
    </div>
  );
}

export function MusicStaffRenderer({ config = {} }) {
  const lines = 5;
  const staffH = 60;
  return (
    <div style={{ padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>{config.title || 'Music Staff'}</div>
      {Array.from({ length: config.staves || 2 }).map((_, s) => (
        <div key={s} style={{ position: 'relative', height: staffH, marginBottom: 20 }}>
          {Array.from({ length: lines }).map((_, i) => (
            <div key={i} style={{ position: 'absolute', top: i * (staffH / (lines - 1)), left: 0, right: 0, height: 1, background: '#1C1917' }} />
          ))}
          <span style={{ position: 'absolute', left: 4, top: 2, fontSize: 28, color: '#78350F' }}>&#119070;</span>
        </div>
      ))}
    </div>
  );
}

export function RhythmNotationRenderer({ config = {} }) {
  const beats = config.beats || 4;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Rhythm Notation</div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'center', padding: '8px 0' }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: '#78350F' }}>{config.timeSignature || '4/4'}</span>
        {Array.from({ length: beats }).map((_, i) => (
          <div key={i} style={{ width: 40, height: 40, border: '2px solid #E7E5E4', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: '#A8A29E' }}>{i + 1}</div>
        ))}
      </div>
    </div>
  );
}

export function NoteIdentificationRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Note Identification</div>
      <div style={{ position: 'relative', height: 60, marginBottom: 10 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{ position: 'absolute', top: i * 15, left: 0, right: 0, height: 1, background: '#1C1917' }} />
        ))}
        <div style={{ position: 'absolute', top: 22, left: 40, width: 14, height: 10, borderRadius: '50%', background: '#1C1917' }}>
          <div style={{ position: 'absolute', right: -2, top: -28, width: 2, height: 30, background: '#1C1917' }} />
        </div>
      </div>
      <div style={{ fontSize: 12, color: '#1C1917' }}>Name this note: <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 60, height: 16 }} /></div>
    </div>
  );
}

export function ChordProgressionRenderer({ config = {} }) {
  const chords = config.chords || ['I', 'IV', 'V', 'I'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Chord Progression</div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
        {chords.map((c, i) => (
          <div key={i} style={{ width: 50, height: 50, border: '2px solid #FDBA74', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED' }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#78350F' }}>{c}</span>
          </div>
        ))}
      </div>
      <div style={{ textAlign: 'center', fontSize: 10, color: '#78716C', marginTop: 6 }}>Key: {config.key || 'C Major'}</div>
    </div>
  );
}

export function IntervalIdentificationRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Interval Identification</div>
      <div style={{ position: 'relative', height: 60, margin: '0 20px 10px' }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{ position: 'absolute', top: i * 15, left: 0, right: 0, height: 1, background: '#1C1917' }} />
        ))}
        <div style={{ position: 'absolute', top: 22, left: 40, width: 14, height: 10, borderRadius: '50%', background: '#1C1917' }} />
        <div style={{ position: 'absolute', top: 7, left: 80, width: 14, height: 10, borderRadius: '50%', background: '#1C1917' }} />
      </div>
      <div style={{ fontSize: 12, color: '#1C1917' }}>Interval: <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 80, height: 16 }} /></div>
    </div>
  );
}

export function KeySignatureExerciseRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Key Signature Exercise</div>
      <div style={{ position: 'relative', height: 60, margin: '0 20px 10px' }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{ position: 'absolute', top: i * 15, left: 0, right: 0, height: 1, background: '#1C1917' }} />
        ))}
        <span style={{ position: 'absolute', left: 4, top: 2, fontSize: 28, color: '#78350F' }}>&#119070;</span>
      </div>
      <div style={{ fontSize: 12, color: '#1C1917' }}>
        Key: <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 60, height: 16 }} />
        {' '}# of sharps/flats: <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 40, height: 16 }} />
      </div>
    </div>
  );
}

export function FourPartHarmonyRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Four-Part Harmony</div>
      {['Soprano', 'Alto', 'Tenor', 'Bass'].map((voice, vi) => (
        <div key={vi} style={{ position: 'relative', height: 40, marginBottom: 8 }}>
          <span style={{ position: 'absolute', left: 0, top: 0, fontSize: 9, color: '#78350F', fontWeight: 600 }}>{voice}</span>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={{ position: 'absolute', top: 4 + i * 9, left: 50, right: 0, height: 1, background: '#E7E5E4' }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function AuralSkillsExerciseRenderer({ config = {} }) {
  return cardBox(config.title || 'Aural Skills Exercise', [
    'Interval heard',
    'Chord quality',
    'Rhythmic pattern',
    'Melodic dictation',
  ]);
}

export function DrawingPromptRenderer({ config = {} }) {
  return (
    <div>
      <div style={{ background: '#FFF7ED', borderLeft: '3px solid #F97316', padding: '8px 12px', fontSize: 13, color: '#78350F', borderRadius: '0 8px 8px 0', marginBottom: 8 }}>
        {config.prompt || 'Draw your response to the following...'}
      </div>
      <div style={{ border: '2px dashed #FDBA74', borderRadius: 14, height: config.height || 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED' }}>
        <span style={{ fontSize: 12, color: '#FDBA74' }}>Drawing Space</span>
      </div>
    </div>
  );
}

export function ArtVocabularyRenderer({ config = {} }) {
  const terms = config.terms || [
    { term: 'Composition', definition: '' },
    { term: 'Contrast', definition: '' },
    { term: 'Perspective', definition: '' },
  ];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Art Vocabulary</div>
      <div style={{ padding: 10 }}>
        {terms.map((t, i) => (
          <div key={i} style={{ marginBottom: 6 }}>
            <span style={{ fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#1C1917' }}>{t.term}: </span>
            <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 200, height: 16 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ArtistStudyRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Artist Study', [
    'Artist Name & Time Period',
    'Art Movement / Style',
    'Notable Works',
    'Techniques & Materials',
    'Influence / Legacy',
  ]);
}

export function BlockingDiagramRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Stage Blocking Diagram</div>
      <div style={{ padding: 10, position: 'relative' }}>
        <div style={{ height: 140, border: '2px solid #78350F', borderTop: '4px solid #F97316', borderRadius: '0 0 8px 8px', position: 'relative', background: '#FAFAF9' }}>
          <span style={{ position: 'absolute', top: -14, left: '50%', transform: 'translateX(-50%)', fontSize: 9, color: '#F97316', fontWeight: 600 }}>AUDIENCE</span>
          <span style={{ position: 'absolute', top: 4, left: 4, fontSize: 8, color: '#A8A29E' }}>SR</span>
          <span style={{ position: 'absolute', top: 4, right: 4, fontSize: 8, color: '#A8A29E' }}>SL</span>
          <span style={{ position: 'absolute', bottom: 4, left: '50%', transform: 'translateX(-50%)', fontSize: 8, color: '#A8A29E' }}>UPSTAGE</span>
        </div>
      </div>
    </div>
  );
}

export function ScriptFormatRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 12, fontFamily: "'Courier New', monospace" }}>
      <div style={{ textAlign: 'center', fontSize: 12, fontWeight: 700, marginBottom: 8, color: '#78350F' }}>{config.title || 'SCENE 1'}</div>
      <div style={{ fontSize: 11, color: '#78716C', marginBottom: 8, fontStyle: 'italic' }}>{config.stageDirection || '(Stage direction goes here)'}</div>
      <div style={{ marginBottom: 4 }}>
        <span style={{ fontWeight: 700, color: '#78350F', fontSize: 11 }}>{config.character || 'CHARACTER'}:</span>
      </div>
      <div style={{ borderBottom: '1px solid #E7E5E4', height: 22, marginBottom: 4 }} />
      <div style={{ borderBottom: '1px solid #E7E5E4', height: 22 }} />
    </div>
  );
}

// ─── SIMPLE LABELED BOX / CARD COMPONENTS ───────────────────────────────────

export function VocabularyFlashcardRenderer({ config = {} }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      <div style={{ border: '2px solid #FDBA74', borderRadius: 10, padding: 14, textAlign: 'center', background: '#FFF7ED', minHeight: 60 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#F97316', marginBottom: 4 }}>FRONT</div>
        <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 16, color: '#1C1917' }}>{config.term || 'Term'}</div>
      </div>
      <div style={{ border: '2px solid #E7E5E4', borderRadius: 10, padding: 14, textAlign: 'center', minHeight: 60 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>BACK</div>
        <div style={{ fontSize: 12, color: '#78716C' }}>{config.definition || 'Definition goes here'}</div>
      </div>
    </div>
  );
}

export function DialogueBubbleRenderer({ config = {} }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#FFF7ED', border: '2px solid #FDBA74', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 700, color: '#78350F', flexShrink: 0 }}>
        {(config.speaker || 'A')[0]}
      </div>
      <div style={{ background: '#FFF7ED', border: '1px solid #FDBA74', borderRadius: '12px 12px 12px 0', padding: '8px 12px', flex: 1 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 2 }}>{config.speaker || 'Speaker'}</div>
        <div style={{ borderBottom: '1px solid #E7E5E4', height: 20 }} />
      </div>
    </div>
  );
}

export function SentenceBuilderRenderer({ config = {} }) {
  const parts = config.parts || ['Subject', 'Verb', 'Object'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Sentence Builder</div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {parts.map((p, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ width: 80, height: 28, border: '2px solid #FDBA74', borderRadius: 6, background: '#FFF7ED' }} />
            <span style={{ fontSize: 9, color: '#78350F', marginTop: 2 }}>{p}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AccentPracticeRenderer({ config = {} }) {
  const words = config.words || ['cafe\u0301', 'resume\u0301', 'naive\u0308'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Accent Practice</div>
      {words.map((w, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#1C1917', width: 100 }}>{w}</span>
          <span style={{ borderBottom: '1px solid #E7E5E4', flex: 1, height: 18 }} />
        </div>
      ))}
    </div>
  );
}

export function PictureVocabularyRenderer({ config = {} }) {
  const items = config.items || 4;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} style={{ border: '1px solid #E7E5E4', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ height: 60, background: '#FFF7ED', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 10, color: '#FDBA74' }}>Image {i + 1}</span>
          </div>
          <div style={{ padding: '4px 8px', textAlign: 'center' }}>
            <span style={{ borderBottom: '1px solid #E7E5E4', display: 'inline-block', width: 80, height: 16 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function BasicPhrasesRenderer({ config = {} }) {
  const phrases = config.phrases || ['Hello', 'Thank you', 'Please', 'Goodbye'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Basic Phrases</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr>
          <th style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#FFF7ED', color: '#78350F' }}>English</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#FFF7ED', color: '#78350F' }}>Translation</th>
        </tr></thead>
        <tbody>
          {phrases.map((p, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px' }}>{p}</td>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RecipeCardRenderer({ config = {} }) {
  return cardBox(config.title || 'Recipe', [
    'Recipe Name',
    'Servings',
    'Prep Time',
    'Cook Time',
    'Ingredients',
    'Instructions',
  ]);
}

export function KitchenSafetyChecklistRenderer({ config = {} }) {
  const items = config.items || ['Wash hands', 'Tie back hair', 'Check equipment', 'Clean workspace', 'Proper knife handling'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', marginBottom: 8 }}>Kitchen Safety Checklist</div>
      {items.map((item, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontSize: 12 }}>
          <span style={{ width: 16, height: 16, border: '2px solid #E7E5E4', borderRadius: 3, flexShrink: 0 }} />
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

export function HealthyHabitsChecklistRenderer({ config = {} }) {
  const items = config.items || ['Drink 8 glasses of water', 'Eat fruits/vegetables', '60 min physical activity', '8+ hours of sleep', 'Practice mindfulness'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', marginBottom: 8 }}>Healthy Habits Checklist</div>
      {items.map((item, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontSize: 12 }}>
          <span style={{ width: 16, height: 16, border: '2px solid #E7E5E4', borderRadius: 3, flexShrink: 0 }} />
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

export function MovementActivityRenderer({ config = {} }) {
  return cardBox(config.title || 'Movement Activity', [
    'Activity Name',
    'Equipment Needed',
    'Duration',
    'Instructions',
    'Modifications',
  ]);
}

export function FitnessLogRenderer({ config = {} }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        {['Exercise', 'Sets', 'Reps', 'Weight', 'Notes'].map((h, i) => (
          <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{h}</th>
        ))}
      </tr></thead>
      <tbody>
        {Array.from({ length: config.rows || 5 }).map((_, r) => (
          <tr key={r}>{Array.from({ length: 5 }).map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />)}</tr>
        ))}
      </tbody>
    </table>
  );
}

export function NutritionChartRenderer({ config = {} }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        {['Food Item', 'Calories', 'Protein', 'Carbs', 'Fat'].map((h, i) => (
          <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{h}</th>
        ))}
      </tr></thead>
      <tbody>
        {Array.from({ length: config.rows || 5 }).map((_, r) => (
          <tr key={r}>{Array.from({ length: 5 }).map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />)}</tr>
        ))}
      </tbody>
    </table>
  );
}

export function GoalSettingFormRenderer({ config = {} }) {
  return cardBox(config.title || 'Goal Setting', [
    'Goal',
    'Why is this important?',
    'Steps to achieve',
    'Timeline',
    'How will I measure success?',
  ]);
}

export function WorkoutPlanRenderer({ config = {} }) {
  const days = config.days || ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Workout Plan</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr>
          <th style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#F5F5F4', color: '#78350F' }}>Day</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#F5F5F4', color: '#78350F' }}>Activity</th>
          <th style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#F5F5F4', color: '#78350F' }}>Duration</th>
        </tr></thead>
        <tbody>
          {days.map((d, i) => (
            <tr key={i}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 600, color: '#78350F' }}>{d}</td>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TrainingLogRenderer({ config = {} }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        {['Date', 'Activity', 'Duration', 'Intensity', 'How I Felt'].map((h, i) => (
          <th key={i} style={{ border: '1px solid #E7E5E4', padding: '6px 8px', background: '#FFF7ED', fontWeight: 600, color: '#78350F' }}>{h}</th>
        ))}
      </tr></thead>
      <tbody>
        {Array.from({ length: config.rows || 5 }).map((_, r) => (
          <tr key={r}>{Array.from({ length: 5 }).map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />)}</tr>
        ))}
      </tbody>
    </table>
  );
}

export function SkillsRubricRenderer({ config = {} }) {
  const skills = config.skills || ['Skill 1', 'Skill 2', 'Skill 3'];
  const levels = config.levels || ['Beginning', 'Developing', 'Proficient', 'Advanced'];
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
      <thead><tr>
        <th style={{ border: '1px solid #E7E5E4', padding: '4px 6px', background: '#F5F5F4', color: '#78350F' }}>Skill</th>
        {levels.map((l, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '4px 6px', background: '#FFF7ED', color: '#78350F' }}>{l}</th>)}
      </tr></thead>
      <tbody>
        {skills.map((s, ri) => (
          <tr key={ri}>
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 6px', fontWeight: 600, color: '#78350F' }}>{s}</td>
            {levels.map((_, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: '4px 6px', height: 24 }} />)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SportStrategyDiagramRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>{config.title || 'Strategy Diagram'}</div>
      <div style={{ height: 160, background: '#16A34A', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: '80%', height: '80%', border: '2px solid white', borderRadius: 4, position: 'relative' }}>
          <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, borderTop: '1px dashed white' }} />
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', borderLeft: '1px dashed white' }} />
        </div>
      </div>
    </div>
  );
}

export function ProjectPlannerRenderer({ config = {} }) {
  return cardBox(config.title || 'Project Planner', [
    'Project Title',
    'Objective',
    'Materials Needed',
    'Timeline / Milestones',
    'Team Members / Roles',
    'Success Criteria',
  ]);
}

export function RubricBuilderRenderer({ config = {} }) {
  const criteria = config.criteria || ['Criteria 1', 'Criteria 2', 'Criteria 3'];
  const scores = config.scores || ['4', '3', '2', '1'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Rubric</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead><tr>
          <th style={{ border: '1px solid #E7E5E4', padding: '4px 6px', background: '#F5F5F4', color: '#78350F' }}>Criteria</th>
          {scores.map((s, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '4px 6px', background: '#F5F5F4', color: '#78350F' }}>{s}</th>)}
        </tr></thead>
        <tbody>
          {criteria.map((c, ri) => (
            <tr key={ri}>
              <td style={{ border: '1px solid #E7E5E4', padding: '4px 6px', fontWeight: 600, color: '#78350F' }}>{c}</td>
              {scores.map((_, ci) => <td key={ci} style={{ border: '1px solid #E7E5E4', padding: '4px 6px', height: 28 }} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CodeBlockRenderer({ config = {} }) {
  return (
    <div style={{ background: '#1C1917', borderRadius: 8, padding: 12, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 10, color: '#A8A29E' }}>{config.language || 'python'}</span>
      </div>
      <pre style={{ fontFamily: "'Courier New', monospace", fontSize: 12, color: '#E7E5E4', margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
        {config.code || '# Write your code here\n\n'}
      </pre>
    </div>
  );
}

export function FlowchartRenderer({ config = {} }) {
  const steps = config.steps || ['Start', 'Process', 'Decision', 'End'];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      {steps.map((s, i) => (
        <div key={i}>
          <div style={{
            padding: '6px 20px',
            border: '2px solid #78350F',
            borderRadius: i === 0 || i === steps.length - 1 ? 20 : (s === 'Decision' ? 0 : 6),
            background: '#FFF7ED',
            fontSize: 12,
            fontWeight: 600,
            color: '#78350F',
            textAlign: 'center',
            transform: s === 'Decision' ? 'rotate(45deg)' : 'none',
            minWidth: s === 'Decision' ? 60 : 'auto',
          }}>
            <span style={{ display: 'inline-block', transform: s === 'Decision' ? 'rotate(-45deg)' : 'none' }}>{s}</span>
          </div>
          {i < steps.length - 1 && (
            <div style={{ textAlign: 'center', color: '#78350F', fontSize: 16, lineHeight: 1 }}>&darr;</div>
          )}
        </div>
      ))}
    </div>
  );
}

export function PseudocodeEditorRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 8, overflow: 'hidden' }}>
      <div style={{ background: '#F5F5F4', padding: '4px 10px', fontSize: 10, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Pseudocode</div>
      <pre style={{ fontFamily: "'Courier New', monospace", fontSize: 12, padding: 10, margin: 0, background: '#FAFAF9', minHeight: 80, lineHeight: 1.8, color: '#1C1917' }}>
        {config.code || 'BEGIN\n  // Write steps here\nEND'}
      </pre>
    </div>
  );
}

export function ClassDiagramRenderer({ config = {} }) {
  const className = config.className || 'MyClass';
  const fields = config.fields || ['- name: String', '- age: int'];
  const methods = config.methods || ['+ getName(): String', '+ setAge(int): void'];
  return (
    <div style={{ border: '2px solid #78350F', borderRadius: 4, width: 'fit-content', margin: '0 auto', minWidth: 180, fontFamily: "'Courier New', monospace", fontSize: 11 }}>
      <div style={{ padding: '6px 10px', background: '#FFF7ED', borderBottom: '2px solid #78350F', fontWeight: 700, textAlign: 'center', color: '#78350F' }}>{className}</div>
      <div style={{ padding: '6px 10px', borderBottom: '1px solid #E7E5E4' }}>
        {fields.map((f, i) => <div key={i} style={{ color: '#1C1917' }}>{f}</div>)}
      </div>
      <div style={{ padding: '6px 10px' }}>
        {methods.map((m, i) => <div key={i} style={{ color: '#1C1917' }}>{m}</div>)}
      </div>
    </div>
  );
}

export function BudgetSpreadsheetRenderer({ config = {} }) {
  const categories = config.categories || ['Item', 'Estimated Cost', 'Actual Cost', 'Difference'];
  const rows = config.rows || 5;
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Budget</div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr>
          {categories.map((c, i) => <th key={i} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#F5F5F4', color: '#78350F', fontWeight: 600 }}>{c}</th>)}
        </tr></thead>
        <tbody>
          {Array.from({ length: rows }).map((_, r) => (
            <tr key={r}>{categories.map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', height: 24 }} />)}</tr>
          ))}
          <tr>
            <td style={{ border: '1px solid #E7E5E4', padding: '4px 8px', fontWeight: 700, color: '#78350F' }}>Total</td>
            {categories.slice(1).map((_, c) => <td key={c} style={{ border: '1px solid #E7E5E4', padding: '4px 8px', background: '#FFF7ED', height: 24 }} />)}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function DesignProcessChartRenderer({ config = {} }) {
  const steps = config.steps || ['Define', 'Research', 'Ideate', 'Prototype', 'Test', 'Implement'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Design Process</div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'center' }}>
        {steps.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 60, height: 60, borderRadius: '50%', border: '2px solid #FDBA74', background: '#FFF7ED', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
              <div>
                <div style={{ fontSize: 8, color: '#F97316', fontWeight: 600 }}>{i + 1}</div>
                <div style={{ fontSize: 9, color: '#78350F', fontWeight: 600 }}>{s}</div>
              </div>
            </div>
            {i < steps.length - 1 && <span style={{ color: '#FDBA74', fontSize: 14 }}>&rarr;</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SPECIALIZED STRUCTURES ─────────────────────────────────────────────────

export function TimelineRenderer({ config = {} }) {
  const events = config.events || [
    { date: '1776', label: 'Event 1' },
    { date: '1789', label: 'Event 2' },
    { date: '1804', label: 'Event 3' },
    { date: '1812', label: 'Event 4' },
  ];
  return (
    <div style={{ position: 'relative', padding: '20px 0' }}>
      <div style={{ position: 'absolute', top: 30, left: 20, right: 20, height: 3, background: '#F97316', borderRadius: 2 }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 20px' }}>
        {events.map((e, i) => (
          <div key={i} style={{ textAlign: 'center', position: 'relative', zIndex: 1 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>{e.date}</div>
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#F97316', border: '2px solid white', margin: '0 auto' }} />
            <div style={{ fontSize: 10, color: '#78716C', marginTop: 4, maxWidth: 60 }}>{e.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MapAnalysisRenderer({ config = {} }) {
  return analysisFrame(config.title || 'Map Analysis', [
    'Title / Region Shown',
    'Type of Map',
    'Key Features / Legend',
    'What does this map show?',
    'Historical Significance',
  ]);
}

export function MapSkillsExerciseRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Map Skills</div>
      <div style={{ display: 'flex', padding: 10, gap: 10 }}>
        <div style={{ width: 160, height: 120, border: '2px dashed #FDBA74', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED', flexShrink: 0, position: 'relative' }}>
          <span style={{ fontSize: 10, color: '#FDBA74' }}>Map</span>
          <span style={{ position: 'absolute', top: 4, right: 6, fontSize: 10, color: '#78350F' }}>N &uarr;</span>
        </div>
        <div style={{ flex: 1 }}>
          {labeledLines(['Compass Rose', 'Scale', 'Latitude / Longitude', 'Legend Items'])}
        </div>
      </div>
    </div>
  );
}

export function CommunityMapRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Community Map</div>
      <div style={{ height: 160, background: '#FAFAF9', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
        <span style={{ fontSize: 12, color: '#A8A29E' }}>Draw your community map here</span>
        <span style={{ position: 'absolute', top: 4, right: 6, fontSize: 10, color: '#78350F' }}>N &uarr;</span>
      </div>
      <div style={{ padding: 8 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>Key:</div>
        <div style={{ display: 'flex', gap: 12 }}>
          {['School', 'Park', 'Home', 'Store'].map((l, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#78716C' }}>
              <div style={{ width: 10, height: 10, border: '1px solid #E7E5E4', borderRadius: 2 }} />
              {l}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function BiographyFrameRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '8px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 14, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Biography</div>
      <div style={{ display: 'flex', padding: 10, gap: 10 }}>
        <div style={{ width: 80, height: 80, border: '2px dashed #FDBA74', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED', flexShrink: 0 }}>
          <span style={{ fontSize: 9, color: '#FDBA74' }}>Photo</span>
        </div>
        <div style={{ flex: 1 }}>
          {labeledLines(['Name', 'Born / Died', 'Known For', 'Key Accomplishments', 'Interesting Fact'])}
        </div>
      </div>
    </div>
  );
}

export function BranchesDiagramRenderer({ config = {} }) {
  const branches = config.branches || ['Legislative', 'Executive', 'Judicial'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontFamily: "'DM Serif Display', serif", fontSize: 13, color: '#78350F', borderBottom: '1px solid #E7E5E4', textAlign: 'center' }}>{config.title || 'Branches of Government'}</div>
      <div style={{ display: 'flex', gap: 8, padding: 10, justifyContent: 'center' }}>
        {branches.map((b, i) => (
          <div key={i} style={{ flex: 1, border: '1px solid #E7E5E4', borderRadius: 8, padding: 8, textAlign: 'center' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 4 }}>{b}</div>
            <div style={{ borderBottom: '1px solid #E7E5E4', height: 18, marginBottom: 4 }} />
            <div style={{ borderBottom: '1px solid #E7E5E4', height: 18 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProbabilityTreeRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Probability Tree</div>
      <svg width="100%" height={120} viewBox="0 0 300 120">
        <circle cx={30} cy={60} r={6} fill="#F97316" />
        <line x1={36} y1={55} x2={140} y2={25} stroke="#78350F" strokeWidth={1.5} />
        <line x1={36} y1={65} x2={140} y2={95} stroke="#78350F" strokeWidth={1.5} />
        <circle cx={145} cy={25} r={6} fill="#FDBA74" />
        <circle cx={145} cy={95} r={6} fill="#FDBA74" />
        <line x1={151} y1={20} x2={240} y2={10} stroke="#78350F" strokeWidth={1} />
        <line x1={151} y1={30} x2={240} y2={40} stroke="#78350F" strokeWidth={1} />
        <line x1={151} y1={90} x2={240} y2={80} stroke="#78350F" strokeWidth={1} />
        <line x1={151} y1={100} x2={240} y2={110} stroke="#78350F" strokeWidth={1} />
        <circle cx={245} cy={10} r={4} fill="#E7E5E4" />
        <circle cx={245} cy={40} r={4} fill="#E7E5E4" />
        <circle cx={245} cy={80} r={4} fill="#E7E5E4" />
        <circle cx={245} cy={110} r={4} fill="#E7E5E4" />
        <text x={250} y={14} fontSize={9} fill="#78716C">{config.label1 || 'P = ___'}</text>
        <text x={250} y={44} fontSize={9} fill="#78716C">{config.label2 || 'P = ___'}</text>
        <text x={250} y={84} fontSize={9} fill="#78716C">{config.label3 || 'P = ___'}</text>
        <text x={250} y={114} fontSize={9} fill="#78716C">{config.label4 || 'P = ___'}</text>
      </svg>
    </div>
  );
}

export function BoxPlotRenderer({ config = {} }) {
  return (
    <div style={{ padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Box Plot</div>
      <div style={{ position: 'relative', height: 60, margin: '0 30px' }}>
        {/* Number line */}
        <div style={{ position: 'absolute', top: 40, left: 0, right: 0, height: 1, background: '#1C1917' }} />
        {[0, 25, 50, 75, 100].map((p, i) => (
          <div key={i} style={{ position: 'absolute', top: 36, left: `${p}%`, transform: 'translateX(-50%)' }}>
            <div style={{ width: 1, height: 10, background: '#1C1917' }} />
            <div style={{ fontSize: 9, textAlign: 'center', marginTop: 2, color: '#78716C' }}>{config[`q${i}`] || ''}</div>
          </div>
        ))}
        {/* Box */}
        <div style={{ position: 'absolute', top: 8, left: '25%', width: '50%', height: 24, border: '2px solid #F97316', background: '#FFF7ED' }}>
          <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 2, background: '#F97316' }} />
        </div>
        {/* Whiskers */}
        <div style={{ position: 'absolute', top: 20, left: 0, width: '25%', height: 1, background: '#F97316' }} />
        <div style={{ position: 'absolute', top: 20, right: 0, width: '25%', height: 1, background: '#F97316' }} />
        <div style={{ position: 'absolute', top: 14, left: 0, width: 1, height: 12, background: '#F97316' }} />
        <div style={{ position: 'absolute', top: 14, right: 0, width: 1, height: 12, background: '#F97316' }} />
      </div>
    </div>
  );
}

export function TwoColumnProofRenderer({ config = {} }) {
  const rows = config.rows || 5;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead><tr>
        <th style={{ border: '2px solid #78350F', padding: '6px 10px', background: '#FFF7ED', color: '#78350F', fontWeight: 600, width: '50%' }}>Statements</th>
        <th style={{ border: '2px solid #78350F', padding: '6px 10px', background: '#FFF7ED', color: '#78350F', fontWeight: 600, width: '50%' }}>Reasons</th>
      </tr></thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            <td style={{ border: '1px solid #E7E5E4', padding: '6px 10px', height: 28 }}><span style={{ color: '#78716C', fontSize: 10 }}>{r + 1}.</span></td>
            <td style={{ border: '1px solid #E7E5E4', padding: '6px 10px', height: 28 }}><span style={{ color: '#78716C', fontSize: 10 }}>{r + 1}.</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function AnnotationLayerRenderer({ config = {} }) {
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ background: '#FFF7ED', padding: '6px 12px', fontSize: 12, fontWeight: 600, color: '#78350F', borderBottom: '1px solid #E7E5E4' }}>Annotation</div>
      <div style={{ padding: 10 }}>
        <div style={{ background: '#FAFAF9', border: '1px solid #E7E5E4', borderRadius: 8, padding: 10, minHeight: 60, fontSize: 13, color: '#1C1917', lineHeight: 1.8 }}>
          {config.text || 'Text to annotate goes here...'}
        </div>
        <div style={{ marginTop: 8 }}>
          {labeledLines(['Notes / Annotations'])}
        </div>
      </div>
    </div>
  );
}

export function GrammarExerciseRenderer({ config = {}, gradeContext }) {
  const gc = gradeContext || DEFAULT_GRADE;
  const sentences = config.sentences || ['The dog (run/runs) fast.', 'She (is/are) happy.'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>Grammar Exercise</div>
      {sentences.map((s, i) => (
        <div key={i} style={{ fontSize: gc.baseFontSize - 1, color: '#1C1917', marginBottom: 6, lineHeight: gc.lineHeight }}>
          {i + 1}. {s}
        </div>
      ))}
    </div>
  );
}

export function PhonicsExerciseRenderer({ config = {} }) {
  const words = config.words || ['cat', 'bat', 'hat', 'mat', 'sat'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 6 }}>{config.title || 'Phonics Practice'}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {words.map((w, i) => (
          <div key={i} style={{ padding: '6px 14px', border: '2px solid #FDBA74', borderRadius: 8, background: '#FFF7ED', fontSize: 16, fontWeight: 600, color: '#78350F', letterSpacing: 2 }}>{w}</div>
        ))}
      </div>
    </div>
  );
}

export function SightWordPracticeRenderer({ config = {} }) {
  const words = config.words || ['the', 'and', 'is', 'it', 'was', 'for'];
  return (
    <div style={{ border: '1px solid #E7E5E4', borderRadius: 10, padding: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#78350F', marginBottom: 8 }}>Sight Words</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {words.map((w, i) => (
          <div key={i} style={{ width: 70, height: 40, border: '2px solid #F97316', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700, color: '#78350F', background: '#FFF7ED' }}>{w}</div>
        ))}
      </div>
    </div>
  );
}

// ─── RENDERER REGISTRY ──────────────────────────────────────────────────────

export const RENDERERS = {
  // Universal (existing)
  header: HeaderRenderer,
  name_date_line: NameDateRenderer,
  banner: BannerRenderer,
  multiple_choice: MultipleChoiceRenderer,
  fill_in_blank: FillInBlankRenderer,
  short_answer: ShortAnswerRenderer,
  long_answer: LongAnswerRenderer,
  true_false: TrueFalseRenderer,
  matching: MatchingRenderer,
  math_problem: MathProblemRenderer,
  instructions: InstructionsRenderer,
  text_block: TextBlockRenderer,
  word_bank: WordBankRenderer,
  reading_passage: ReadingPassageRenderer,
  example: ExampleRenderer,
  vocabulary: VocabularyRenderer,
  image: ImageRenderer,
  table: TableRenderer,
  number_line: NumberLineRenderer,
  graph_grid: GraphGridRenderer,
  divider: DividerRenderer,
  spacer: SpacerRenderer,
  answer_key: AnswerKeyRenderer,

  // Grid / Graph
  coordinate_plane: CoordinatePlaneRenderer,
  geometry_canvas: GeometryCanvasRenderer,
  transformation_grid: TransformationGridRenderer,
  distribution_curve: DistributionCurveRenderer,
  supply_demand_graph: SupplyDemandGraphRenderer,
  economic_model: EconomicModelRenderer,

  // Table / Chart
  function_table: FunctionTableRenderer,
  two_way_table: TwoWayTableRenderer,
  data_collection_table: DataCollectionTableRenderer,
  comparison_chart: ComparisonChartRenderer,
  place_value_chart: PlaceValueChartRenderer,
  conjugation_table: ConjugationTableRenderer,
  conversion_table: ConversionTableRenderer,
  cause_effect_chart: CauseEffectChartRenderer,
  design_elements_chart: DesignElementsChartRenderer,
  materials_table: MaterialsTableRenderer,
  trace_table: TraceTableRenderer,
  declension_table: DeclensionTableRenderer,
  case_table: CaseTableRenderer,
  periodic_table_ref: PeriodicTableRefRenderer,

  // Lined / Writing
  work_space_grid: WorkSpaceGridRenderer,
  handwriting_lines: HandwritingLinesRenderer,
  sketch_space: SketchSpaceRenderer,
  construction_space: ConstructionSpaceRenderer,
  technical_drawing_space: TechnicalDrawingSpaceRenderer,
  molar_calc_space: MolarCalcSpaceRenderer,
  lab_report: LabReportRenderer,
  observation_box: ObservationBoxRenderer,
  writing_prompt: WritingPromptRenderer,
  essay_prompt_wl: EssayPromptWlRenderer,
  reflection_journal: ReflectionJournalRenderer,
  portfolio_reflection: PortfolioReflectionRenderer,

  // Math-specific
  equation_editor: EquationEditorRenderer,
  fraction_visual: FractionVisualRenderer,
  multiplication_grid: MultiplicationGridRenderer,
  inequality_number_line: InequalityNumberLineRenderer,
  system_of_equations: SystemOfEquationsRenderer,
  limit_expression: LimitExpressionRenderer,
  integral_derivative: IntegralDerivativeRenderer,
  piecewise_function: PiecewiseFunctionRenderer,
  series_summation: SeriesSummationRenderer,
  kinematics_equations: KinematicsEquationsRenderer,

  // Science-specific
  punnett_square: PunnettSquareRenderer,
  cell_diagram: CellDiagramRenderer,
  dna_rna_sequence: DnaRnaSequenceRenderer,
  phylogenetic_tree: PhylogeneticTreeRenderer,
  chemical_equation_balancer: ChemicalEquationBalancerRenderer,
  lewis_dot: LewisDotRenderer,
  electron_config: ElectronConfigRenderer,
  free_body_diagram: FreeBodyDiagramRenderer,
  circuit_diagram: CircuitDiagramRenderer,
  vector_diagram: VectorDiagramRenderer,
  diagram_label: DiagramLabelRenderer,
  science_graphic_organizer: ScienceGraphicOrganizerRenderer,
  body_diagram: BodyDiagramRenderer,

  // Structured text / Analysis frames
  text_evidence_chart: TextEvidenceChartRenderer,
  literary_analysis_frame: LiteraryAnalysisFrameRenderer,
  rhetorical_analysis: RhetoricalAnalysisRenderer,
  argument_outline: ArgumentOutlineRenderer,
  synthesis_source_chart: SynthesisSourceChartRenderer,
  close_reading_guide: CloseReadingGuideRenderer,
  poetry_annotation: PoetryAnnotationRenderer,
  reading_comprehension_wl: ReadingComprehensionWlRenderer,
  primary_source_analysis: PrimarySourceAnalysisRenderer,
  dbq_document_analysis: DbqDocumentAnalysisRenderer,
  amendment_analysis: AmendmentAnalysisRenderer,
  court_case_brief: CourtCaseBriefRenderer,
  policy_analysis: PolicyAnalysisRenderer,
  scotus_comparison: ScotusComparisonRenderer,
  leq_outline: LeqOutlineRenderer,
  ccot_analysis: CcotAnalysisRenderer,
  character_analysis: CharacterAnalysisRenderer,
  art_critique_guide: ArtCritiqueGuideRenderer,
  contextual_analysis: ContextualAnalysisRenderer,
  artwork_comparison: ArtworkComparisonRenderer,
  cultural_comparison: CulturalComparisonRenderer,
  wellness_assessment: WellnessAssessmentRenderer,
  decision_making_model: DecisionMakingModelRenderer,
  stress_management_plan: StressManagementPlanRenderer,
  swot_analysis: SwotAnalysisRenderer,
  cost_benefit_analysis: CostBenefitAnalysisRenderer,
  business_plan_section: BusinessPlanSectionRenderer,

  // Visual / Creative
  color_wheel: ColorWheelRenderer,
  music_staff: MusicStaffRenderer,
  rhythm_notation: RhythmNotationRenderer,
  note_identification: NoteIdentificationRenderer,
  chord_progression: ChordProgressionRenderer,
  interval_identification: IntervalIdentificationRenderer,
  key_signature_exercise: KeySignatureExerciseRenderer,
  four_part_harmony: FourPartHarmonyRenderer,
  aural_skills_exercise: AuralSkillsExerciseRenderer,
  drawing_prompt: DrawingPromptRenderer,
  art_vocabulary: ArtVocabularyRenderer,
  artist_study: ArtistStudyRenderer,
  blocking_diagram: BlockingDiagramRenderer,
  script_format: ScriptFormatRenderer,

  // Simple labeled box / Card
  vocabulary_flashcard: VocabularyFlashcardRenderer,
  dialogue_bubble: DialogueBubbleRenderer,
  sentence_builder: SentenceBuilderRenderer,
  accent_practice: AccentPracticeRenderer,
  picture_vocabulary: PictureVocabularyRenderer,
  basic_phrases: BasicPhrasesRenderer,
  recipe_card: RecipeCardRenderer,
  kitchen_safety_checklist: KitchenSafetyChecklistRenderer,
  healthy_habits_checklist: HealthyHabitsChecklistRenderer,
  movement_activity: MovementActivityRenderer,
  fitness_log: FitnessLogRenderer,
  nutrition_chart: NutritionChartRenderer,
  goal_setting_form: GoalSettingFormRenderer,
  workout_plan: WorkoutPlanRenderer,
  training_log: TrainingLogRenderer,
  skills_rubric: SkillsRubricRenderer,
  sport_strategy_diagram: SportStrategyDiagramRenderer,
  project_planner: ProjectPlannerRenderer,
  rubric_builder: RubricBuilderRenderer,
  code_block: CodeBlockRenderer,
  flowchart: FlowchartRenderer,
  pseudocode_editor: PseudocodeEditorRenderer,
  class_diagram: ClassDiagramRenderer,
  budget_spreadsheet: BudgetSpreadsheetRenderer,
  design_process_chart: DesignProcessChartRenderer,

  // Specialized
  timeline: TimelineRenderer,
  map_analysis: MapAnalysisRenderer,
  map_skills_exercise: MapSkillsExerciseRenderer,
  community_map: CommunityMapRenderer,
  biography_frame: BiographyFrameRenderer,
  branches_diagram: BranchesDiagramRenderer,
  probability_tree: ProbabilityTreeRenderer,
  box_plot: BoxPlotRenderer,
  two_column_proof: TwoColumnProofRenderer,
  annotation_layer: AnnotationLayerRenderer,
  grammar_exercise: GrammarExerciseRenderer,
  phonics_exercise: PhonicsExerciseRenderer,
  sight_word_practice: SightWordPracticeRenderer,
};
