/**
 * Game shell registry — declarative config per game used by:
 *   - /games page (grid cards)
 *   - GameSetupModal (per-shell settings form)
 *   - /join routing (which shell component to render for students)
 *
 * Pattern mirrors plannerVariants.js — each entry describes icon, copy,
 * and which settings fields to render.
 */

// Field types the GameSetupModal knows how to render
// { type: 'number'|'select'|'toggle'|'text', label, default, options?, min?, max? }

export const BASE_SETTINGS = [
  { key: 'question_count', type: 'number', label: 'Number of questions', default: 15, min: 5, max: 50 },
  { key: 'timer_seconds',  type: 'select', label: 'Timer per question',
    options: [
      { value: 10, label: '10 seconds' },
      { value: 20, label: '20 seconds' },
      { value: 30, label: '30 seconds' },
      { value: 60, label: '60 seconds' },
      { value: 0,  label: 'No timer' },
    ],
    default: 20,
  },
  { key: 'shuffle', type: 'toggle', label: 'Randomize question order', default: true },
];

export const GAME_SHELLS = [
  // Phase 1 — fully playable
  {
    id: 'quiz_race',
    name: 'Quiz Race',
    desc: 'Kahoot-style MC — fastest correct answer wins the most points.',
    icon: 'game_quiz_race.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1,
    max_players: 40,
    play_time_min: 10,
    best_for: 'Any subject, any grade',
    // Teacher controls question_count freely
    question_count_default: 15,
    question_count_min: 5,
    question_count_max: 50,
    question_count_locked: false,
    needs_categories: false,
    extra_settings: [],
  },
  {
    id: 'jeopardy',
    name: 'Jeopardy',
    desc: '5×5 category board. Students pick a value, answer the question.',
    icon: 'game_jeopardy.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 3,
    max_players: 30,
    play_time_min: 20,
    best_for: 'Review & end of unit',
    // Jeopardy is locked to 25 (5 categories × 5 values). Teacher can't change this.
    question_count_default: 25,
    question_count_locked: true,
    needs_categories: true,  // modal shows a "Suggest" button next to the category field
    extra_settings: [
      { key: 'categories', type: 'text', label: 'Category names (5, comma-separated)',
        default: 'Vocab, Facts, Events, People, Dates',
        placeholder: 'Vocab, Facts, Events, People, Dates',
        suggestable: true },
      { key: 'daily_double', type: 'toggle', label: 'Include Daily Double tile', default: true },
    ],
  },
  {
    id: 'bingo_blitz',
    name: 'Bingo Blitz',
    desc: 'Students get a 5×5 card. Teacher calls questions; mark the answer to win.',
    icon: 'game_bingo.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1,
    max_players: 40,
    play_time_min: 15,
    best_for: 'Vocabulary & definitions',
    // Bingo question_count is derived from board_size (set in GameSetupModal)
    question_count_default: 25,
    question_count_locked: true,
    question_count_derived_from: 'board_size',  // modal computes board_size² on change
    needs_categories: false,
    extra_settings: [
      { key: 'board_size', type: 'select', label: 'Board size',
        options: [
          { value: 3, label: '3×3 (fast, 9 terms)' },
          { value: 4, label: '4×4 (16 terms)' },
          { value: 5, label: '5×5 (25 terms, classic)' },
        ],
        default: 5 },
      { key: 'free_space', type: 'toggle', label: 'Include a free space (center)', default: true },
    ],
  },

  // Phase 2 — coming soon
  { id: 'millionaire',     name: 'Millionaire',      desc: '15 escalating questions, 3 lifelines.',             icon: 'game_millionaire.png',    icon_fallback: 'gamepad.png', phase: 2, min_players: 1, max_players: 30, play_time_min: 15, best_for: 'Whole-class challenge' },
  { id: 'battle_royale',   name: 'Battle Royale',    desc: 'Wrong answer = eliminated. Last student standing.', icon: 'game_battle_royale.png',  icon_fallback: 'gamepad.png', phase: 2, min_players: 5, max_players: 40, play_time_min: 12, best_for: 'Fast review' },
  { id: 'team_tug_of_war', name: 'Team Tug of War',  desc: 'Two teams pull the rope with correct answers.',     icon: 'game_tug_of_war.png',     icon_fallback: 'gamepad.png', phase: 2, min_players: 6, max_players: 40, play_time_min: 15, best_for: 'Class competition' },
  { id: 'memory_match',    name: 'Memory Match',     desc: 'Match question ↔ answer pairs, speed bonus.',       icon: 'game_memory.png',          icon_fallback: 'gamepad.png', phase: 2, min_players: 1, max_players: 30, play_time_min: 10, best_for: 'Vocabulary, concepts' },

  // Phase 3 — coming soon
  { id: 'speed_rush',      name: 'Speed Rush',       desc: 'Rapid-fire sprint — finish the deck fastest.',      icon: 'game_speed_rush.png',      icon_fallback: 'gamepad.png', phase: 3, min_players: 1, max_players: 30, play_time_min: 8,  best_for: 'Fact fluency' },
  { id: 'escape_room',     name: 'Escape Room',      desc: 'Cooperative puzzle — unlock rooms with answers.',   icon: 'game_escape.png',          icon_fallback: 'gamepad.png', phase: 3, min_players: 2, max_players: 10, play_time_min: 25, best_for: 'Collaborative review' },
  { id: 'card_duel',       name: 'Card Duel',        desc: '1v1 turn-based elimination.',                        icon: 'game_card_duel.png',       icon_fallback: 'gamepad.png', phase: 3, min_players: 2, max_players: 8,  play_time_min: 10, best_for: 'Math / vocabulary' },
  { id: 'wheel_spin',      name: 'Wheel Spin',       desc: 'Spin for a category, answer the question.',          icon: 'game_wheel.png',            icon_fallback: 'gamepad.png', phase: 3, min_players: 1, max_players: 30, play_time_min: 12, best_for: 'Mixed review' },
  { id: 'tournament',      name: 'Tournament',       desc: 'Single-elimination bracket between students.',       icon: 'game_tournament.png',      icon_fallback: 'gamepad.png', phase: 3, min_players: 4, max_players: 32, play_time_min: 25, best_for: 'End-of-unit event' },
];

export function getShell(id) {
  return GAME_SHELLS.find(s => s.id === id);
}

export function playableShells() {
  return GAME_SHELLS.filter(s => s.phase === 1);
}
