'use client';

/**
 * WYSIWYG component renderers — each renders exactly as it will print.
 * Used on the canvas and in PDF export.
 */

export function HeaderRenderer({ config = {}, theme }) {
  const level = config.level || 'h1';
  const align = config.alignment || 'left';
  const sizes = { h1: 22, h2: 18, h3: 14 };
  return (
    <div style={{ textAlign: align }}>
      <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: sizes[level], color: '#1C1917', lineHeight: 1.3 }}>
        {config.text || 'Untitled'}
      </div>
      {config.subtitle && <div style={{ fontSize: 13, color: '#78716C', marginTop: 2 }}>{config.subtitle}</div>}
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

export function MultipleChoiceRenderer({ config = {} }) {
  const options = config.options || ['Option A', 'Option B', 'Option C', 'Option D'];
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ fontSize: 13, color: '#1C1917', marginBottom: 6 }}>{config.question || 'Question text goes here'}</div>
      <div style={{ marginLeft: 16 }}>
        {options.map((opt, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3, fontSize: 13, color: '#1C1917' }}>
            <span style={{ width: 18, height: 18, borderRadius: '50%', border: '2px solid #E7E5E4', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 600, color: '#78350F' }}>
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

export function FillInBlankRenderer({ config = {} }) {
  const sentence = config.sentence || 'The ___ is equal to one half.';
  const rendered = sentence.replace(/___/g, '<span style="border-bottom:2px solid #F97316;display:inline-block;width:80px;height:16px;margin:0 4px;"></span>');
  return <div style={{ fontSize: 13, color: '#1C1917', lineHeight: 2 }} dangerouslySetInnerHTML={{ __html: rendered }} />;
}

export function ShortAnswerRenderer({ config = {} }) {
  const lines = config.lines || 2;
  return (
    <div>
      <div style={{ fontSize: 13, color: '#1C1917', marginBottom: 6 }}>{config.question || 'Question'}</div>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} style={{ borderBottom: '1px solid #E7E5E4', height: 24 }} />
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

export function InstructionsRenderer({ config = {} }) {
  return (
    <div style={{ background: '#FFF7ED', borderLeft: '3px solid #F97316', padding: '8px 12px', fontSize: 12, color: '#78350F', borderRadius: '0 8px 8px 0' }}>
      <div dangerouslySetInnerHTML={{ __html: config.html || config.text || '<b>Directions:</b> Complete all problems.' }} />
    </div>
  );
}

export function TextBlockRenderer({ config = {} }) {
  return <div style={{ fontSize: 13, color: '#4B5563', lineHeight: 1.6 }}>{config.text || 'Text content'}</div>;
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

export function ReadingPassageRenderer({ config = {} }) {
  const text = config.text || 'Passage text goes here. This is a sample reading passage that students will read before answering comprehension questions.';
  const lines = text.split('\n').length > 1 ? text.split('\n') : text.match(/.{1,80}/g) || [text];
  return (
    <div style={{ background: '#FEF9F2', border: '1px solid #E7E5E4', borderRadius: 10, padding: 14, fontSize: 13, lineHeight: 1.8 }}>
      {config.title && <div style={{ fontFamily: "'DM Serif Display', serif", fontSize: 14, marginBottom: 8 }}>{config.title}</div>}
      {lines.map((line, i) => (
        <div key={i}><span style={{ display: 'inline-block', width: 24, textAlign: 'right', marginRight: 10, color: '#A8A29E', fontSize: 10, userSelect: 'none' }}>{i + 1}</span>{line}</div>
      ))}
    </div>
  );
}

export function ImageRenderer({ config = {} }) {
  if (config.url) {
    return (
      <div style={{ textAlign: config.alignment || 'center' }}>
        <img src={config.url} alt={config.caption || ''} style={{
          maxWidth: { small: '25%', medium: '50%', large: '75%', full: '100%' }[config.size || 'medium'],
          borderRadius: 8, border: config.border ? '1px solid #E7E5E4' : 'none',
        }} />
        {config.caption && <div style={{ fontSize: 10, color: '#A8A29E', marginTop: 4 }}>{config.caption}</div>}
      </div>
    );
  }
  return (
    <div style={{ border: '2px dashed #FDBA74', borderRadius: 14, height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFF7ED' }}>
      <span style={{ fontSize: 12, color: '#FDBA74' }}>Click to add image</span>
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

export function MathProblemRenderer({ config = {} }) {
  return (
    <div style={{ fontFamily: 'monospace', fontSize: 16, padding: 8 }}>
      <div>{config.problem || '24 × 16 = ___'}</div>
      {config.showWorkSpace && <div style={{ border: '1px solid #E7E5E4', borderRadius: 8, height: 80, marginTop: 8, background: '#FAFAF9' }} />}
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

// Renderer registry
export const RENDERERS = {
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
};
