/**
 * Per-activity-type refinement chips.
 *
 * Each chip `id` maps to a server-side REFINE_INSTRUCTIONS key in
 * interactive_generator.py. Only instructions that make sense for the
 * activity type appear in that type's list — e.g. Word Search doesn't
 * get "Add visuals" because the activity is pure text grid.
 *
 * Each activity type also gets the universal "Change something else..."
 * escape hatch which opens a free-text textarea for custom instructions.
 */

export const REFINEMENT_CHIPS = {
  multiple_choice_quiz: [
    { label: 'Make it harder',         id: 'make_harder' },
    { label: 'Simpler vocabulary',     id: 'simpler_vocabulary' },
    { label: 'Trickier distractors',   id: 'trickier_distractors' },
    { label: 'Different examples',     id: 'different_examples' },
  ],
  fill_in_blank: [
    { label: 'Make it harder',         id: 'make_harder' },
    { label: 'Simpler vocabulary',     id: 'simpler_vocabulary' },
    { label: 'More sentences',         id: 'more_items' },
    { label: 'Different examples',     id: 'different_examples' },
  ],
  drag_drop_sort: [
    { label: 'More items',             id: 'more_items' },
    { label: 'Add visual cues',        id: 'visual_cues' },
    { label: 'Trickier categories',    id: 'make_harder' },
    { label: 'Simpler options',        id: 'simpler_vocabulary' },
  ],
  drag_drop_sequence: [
    { label: 'More steps',             id: 'more_items' },
    { label: 'Simpler wording',        id: 'simpler_vocabulary' },
    { label: 'Add visual cues',        id: 'visual_cues' },
    { label: 'Different example',      id: 'different_examples' },
  ],
  category_sort: [
    { label: 'More items',             id: 'more_items' },
    { label: 'Trickier items',         id: 'make_harder' },
    { label: 'Add visual cues',        id: 'visual_cues' },
    { label: 'Simpler vocabulary',     id: 'simpler_vocabulary' },
  ],
  matching_pairs: [
    { label: 'More pairs',             id: 'more_pairs' },
    { label: 'Visual cues',            id: 'visual_cues' },
    { label: 'Trickier matches',       id: 'trickier_matches' },
    { label: 'Simpler pairs',          id: 'simpler_pairs' },
  ],
  click_to_reveal: [
    { label: 'More cards',             id: 'more_items' },
    { label: 'Fewer cards',            id: 'fewer_items' },
    { label: 'Simpler vocabulary',     id: 'simpler_vocabulary' },
    { label: 'Different examples',     id: 'different_examples' },
  ],
  flash_cards_interactive: [
    { label: 'More cards',             id: 'more_items' },
    { label: 'Simpler definitions',    id: 'simpler_vocabulary' },
    { label: 'Add visual cues',        id: 'visual_cues' },
    { label: 'Different vocabulary',   id: 'different_examples' },
  ],
  word_search_interactive: [
    { label: 'More words',             id: 'more_items' },
    { label: 'Fewer words',            id: 'fewer_items' },
    { label: 'Different vocabulary',   id: 'different_examples' },
    { label: 'Simpler words',          id: 'simpler_vocabulary' },
  ],
  crossword_interactive: [
    { label: 'More clues',             id: 'more_clues' },
    { label: 'Simpler clues',          id: 'simpler_clues' },
    { label: 'Picture clues',          id: 'picture_clues' },
    { label: 'Different words',        id: 'different_examples' },
  ],
  number_line: [
    { label: 'More values',            id: 'more_items' },
    { label: 'Trickier range',         id: 'make_harder' },
    { label: 'Simpler values',         id: 'simpler_vocabulary' },
    { label: 'Different examples',     id: 'different_examples' },
  ],
  slider_estimation: [
    { label: 'More items',             id: 'more_items' },
    { label: 'Trickier estimates',     id: 'make_harder' },
    { label: 'Easier estimates',       id: 'simpler_vocabulary' },
    { label: 'Different scenarios',    id: 'different_examples' },
  ],
  timeline_builder: [
    { label: 'More events',            id: 'more_items' },
    { label: 'Trickier dates',         id: 'make_harder' },
    { label: 'Simpler events',         id: 'simpler_vocabulary' },
    { label: 'Different era',          id: 'different_examples' },
  ],
  whiteboard_response: [
    { label: 'Harder prompt',          id: 'make_harder' },
    { label: 'Simpler prompt',         id: 'simpler_vocabulary' },
    { label: 'Different angle',        id: 'different_examples' },
    { label: 'Add visual',             id: 'add_visuals' },
  ],
  hotspot_labeling: [
    { label: 'More labels',            id: 'more_labels' },
    { label: 'Simpler terminology',    id: 'simpler_vocabulary' },
    { label: 'Different diagram',      id: 'different_diagram' },
    { label: 'Fewer labels',           id: 'fewer_items' },
  ],
};

export const UNIVERSAL_CHIP = { label: 'Change something else…', id: 'custom', opensTextarea: true };

export function chipsForTemplate(templateId) {
  return [...(REFINEMENT_CHIPS[templateId] || []), UNIVERSAL_CHIP];
}
