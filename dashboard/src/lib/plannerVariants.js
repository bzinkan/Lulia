// Catalog of refinement options used by the planner's Refine step.
// Keyed by material category + subject (normalized lowercase).

export const WORKSHEET_VARIANTS = {
  standard: [
    { id: 'worksheet', label: 'Worksheet' },
    { id: 'task_cards', label: 'Task Cards' },
    { id: 'quiz_test', label: 'Quiz / Test' },
    { id: 'exit_ticket', label: 'Exit Ticket' },
    { id: 'flashcards', label: 'Flashcards' },
    { id: 'bingo', label: 'BINGO' },
    { id: 'morning_work', label: 'Morning Work' },
    { id: 'study_guide', label: 'Study Guide' },
    { id: 'reading_comprehension', label: 'Reading Comprehension' },
    { id: 'graphic_organizer', label: 'Graphic Organizer' },
    { id: 'vocabulary_cards', label: 'Vocabulary Cards' },
    { id: 'anchor_chart', label: 'Anchor Chart' },
    { id: 'homework_packet', label: 'Homework Packet' },
  ],
  science: [
    { id: 'lab_procedure', label: 'Lab Procedure' },
    { id: 'observation_journal', label: 'Observation Journal' },
    { id: 'data_table', label: 'Data Table' },
    { id: 'cer_writing_frame', label: 'CER Writing Frame' },
  ],
};

export function worksheetVariantsFor(subject) {
  const subj = (subject || '').toLowerCase();
  const std = WORKSHEET_VARIANTS.standard;
  if (subj.includes('science')) {
    return [
      { group: 'Standard', items: std },
      { group: 'Science', items: WORKSHEET_VARIANTS.science },
    ];
  }
  return [{ group: 'Standard', items: std }];
}

export const INTERACTIVE_TYPES = [
  { id: 'matching', label: 'Matching Pairs' },
  { id: 'drag_sort', label: 'Drag to Sort' },
  { id: 'hotspot', label: 'Hotspot / Label' },
  { id: 'sequence', label: 'Sequence' },
  { id: 'fill_blank', label: 'Fill in the Blank' },
  { id: 'card_sort', label: 'Card Sort' },
];

export const SLIDES_LAYOUTS = [
  { id: 'lecture', label: 'Lecture' },
  { id: 'guided_notes', label: 'Guided Notes' },
  { id: 'discussion', label: 'Discussion Prompts' },
  { id: 'warmup_to_close', label: 'Warm-up → Close' },
];

export const GAME_FORMATS = [
  { id: 'jeopardy', label: 'Jeopardy' },
  { id: 'kahoot_style', label: 'Kahoot-style' },
  { id: 'team_quest', label: 'Team Quest' },
];

export const DIFFICULTY_LEVELS = [
  { id: 'easy', label: 'Easy' },
  { id: 'medium', label: 'Medium' },
  { id: 'hard', label: 'Hard' },
];

export const FORM_QUESTION_TYPES = [
  { id: 'mcq', label: 'Multiple Choice' },
  { id: 'short_answer', label: 'Short Answer' },
  { id: 'checkbox', label: 'Checkboxes' },
  { id: 'true_false', label: 'True / False' },
];

export const ACCOMMODATION_OPTIONS = [
  { id: 'iep_reduced',     label: 'IEP — Reduced',     color: '#3B82F6', desc: 'Fewer items, simpler language' },
  { id: '504_extended',    label: '504 — Extended',    color: '#8B5CF6', desc: 'Same content, more space and time cues' },
  { id: 'ell_beginner',    label: 'ELL — Beginner',    color: '#F59E0B', desc: 'Sentence frames, visuals, glossary' },
  { id: 'gifted_enriched', label: 'Gifted — Enriched', color: '#10B981', desc: 'Extension questions, open-ended prompts' },
];

// Map an output_template_id to a refinement category.
// Used by RefineDayModal to pick which refiner component to render.
export function categoryForTemplate(templateId) {
  if (!templateId) return 'worksheet';
  const t = templateId.toLowerCase();
  if (t.includes('slides') || t.includes('gemini_slides')) return 'slides';
  if (t.includes('forms') || t.includes('quiz_form')) return 'forms';
  if (t.includes('interactive') || t.includes('activity')) return 'interactive';
  if (t.includes('game')) return 'game';
  if (t.includes('video')) return 'video';
  if (t.includes('quiz') || t.includes('test') || t.includes('assessment')) return 'quiz';
  return 'worksheet';
}
