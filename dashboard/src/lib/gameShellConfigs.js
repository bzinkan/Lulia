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

export const ARCADE_CATEGORIES = [
  { id: 'ALL', label: 'ALL' },
  { id: 'TRIVIA', label: 'TRIVIA' },
  { id: 'TEAM', label: 'TEAM' },
  { id: 'SOLO', label: 'SOLO' },
  { id: 'COOP', label: 'COOP' },
  { id: 'REVIEW', label: 'REVIEW' },
];

export const GAME_SHELLS = [
  // Phase 1 — fully playable
  {
    id: 'quiz_race',
    name: 'Quiz Race',
    marquee_name: 'QUIZ RACE',
    desc: 'Kahoot-style MC — fastest correct answer wins the most points.',
    arcade_tagline: 'INSERT COIN TO PLAY',
    arcade_category: 'TRIVIA',
    icon: 'game_quiz_race.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1,
    max_players: 40,
    play_time_min: 10,
    best_for: 'Any subject, any grade',
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
    marquee_name: 'JEOPARDY',
    desc: '5×5 category board. Students pick a value, answer the question.',
    arcade_tagline: 'CHOOSE YOUR CATEGORY',
    arcade_category: 'REVIEW',
    icon: 'game_jeopardy.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 3,
    max_players: 30,
    play_time_min: 20,
    best_for: 'Review & end of unit',
    question_count_default: 25,
    question_count_locked: true,
    needs_categories: true,
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
    marquee_name: 'BINGO BLITZ',
    desc: 'Students get a 5×5 card. Teacher calls questions; mark the answer to win.',
    arcade_tagline: 'MARK THE ANSWERS',
    arcade_category: 'TRIVIA',
    icon: 'game_bingo.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1,
    max_players: 40,
    play_time_min: 15,
    best_for: 'Vocabulary & definitions',
    question_count_default: 25,
    question_count_locked: true,
    question_count_derived_from: 'board_size',
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
  { id: 'millionaire',     name: 'Millionaire',      marquee_name: 'MILLIONAIRE',  desc: '15 escalating questions, 3 lifelines.',             arcade_tagline: 'FINAL ANSWER?',      arcade_category: 'SOLO',   icon: 'game_millionaire.png',    icon_fallback: 'gamepad.png', phase: 1, min_players: 1, max_players: 30, play_time_min: 15, best_for: 'Whole-class challenge' },
  { id: 'battle_royale',   name: 'Battle Royale',    marquee_name: 'BATTLE ROYALE',desc: 'Wrong answer = eliminated. Last student standing.', arcade_tagline: 'SURVIVE THE ROUND',  arcade_category: 'TEAM',   icon: 'game_battle_royale.png',  icon_fallback: 'gamepad.png', phase: 1, min_players: 5, max_players: 40, play_time_min: 12, best_for: 'Fast review' },
  { id: 'team_tug_of_war', name: 'Team Tug of War',  marquee_name: 'TUG OF WAR',   desc: 'Two teams pull the rope with correct answers.',     arcade_tagline: 'PULL THE ROPE',      arcade_category: 'TEAM',   icon: 'game_tug_of_war.png',     icon_fallback: 'gamepad.png', phase: 1, min_players: 6, max_players: 40, play_time_min: 15, best_for: 'Class competition' },
  { id: 'memory_match',    name: 'Memory Match',     marquee_name: 'MEMORY MATCH', desc: 'Match question ↔ answer pairs, speed bonus.',       arcade_tagline: 'FIND THE PAIRS',     arcade_category: 'SOLO',   icon: 'game_memory.png',          icon_fallback: 'gamepad.png', phase: 1, min_players: 1, max_players: 30, play_time_min: 10, best_for: 'Vocabulary, concepts' },

  // Phase 3 — coming soon
  { id: 'speed_rush',      name: 'Speed Rush',       marquee_name: 'SPEED RUSH',   desc: 'Rapid-fire sprint — finish the deck fastest.',      arcade_tagline: 'BEAT THE CLOCK',     arcade_category: 'SOLO',   icon: 'game_speed_rush.png',      icon_fallback: 'gamepad.png', phase: 1, min_players: 1, max_players: 30, play_time_min: 8,  best_for: 'Fact fluency' },
  { id: 'escape_room',     name: 'Escape Room',      marquee_name: 'ESCAPE ROOM',  desc: 'Cooperative puzzle — unlock rooms with answers.',   arcade_tagline: 'FIND THE KEY',       arcade_category: 'COOP',   icon: 'game_escape.png',          icon_fallback: 'gamepad.png', phase: 1, min_players: 2, max_players: 10, play_time_min: 25, best_for: 'Collaborative review' },
  { id: 'card_duel',       name: 'Card Duel',        marquee_name: 'CARD DUEL',    desc: '1v1 turn-based elimination.',                       arcade_tagline: 'DRAW. PLAY. WIN.',   arcade_category: 'TEAM',   icon: 'game_card_duel.png',       icon_fallback: 'gamepad.png', phase: 1, min_players: 2, max_players: 8,  play_time_min: 10, best_for: 'Math / vocabulary' },
  { id: 'wheel_spin',      name: 'Wheel Spin',       marquee_name: 'WHEEL SPIN',   desc: 'Spin for a category, answer the question.',         arcade_tagline: 'SPIN THE WHEEL',     arcade_category: 'REVIEW', icon: 'game_wheel.png',            icon_fallback: 'gamepad.png', phase: 1, min_players: 1, max_players: 30, play_time_min: 12, best_for: 'Mixed review' },
  { id: 'tournament',      name: 'Tournament',       marquee_name: 'TOURNAMENT',   desc: 'Single-elimination bracket between students.',      arcade_tagline: 'CLIMB THE BRACKET',  arcade_category: 'TEAM',   icon: 'game_tournament.png',      icon_fallback: 'gamepad.png', phase: 1, min_players: 4, max_players: 32, play_time_min: 25, best_for: 'End-of-unit event' },
];

export function getShell(id) {
  return GAME_SHELLS.find(s => s.id === id);
}

export function playableShells() {
  return GAME_SHELLS.filter(s => s.phase === 1);
}
