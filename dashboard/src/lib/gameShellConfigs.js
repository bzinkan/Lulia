/**
 * Game shell registry — declarative config per game used by:
 *   - /games page (grid cards)
 *   - GameSetupModal (per-shell settings form)
 *   - /play + /join routing (which shell component to render)
 *
 * Pattern mirrors plannerVariants.js — each entry describes icon, copy,
 * and which settings fields to render.
 *
 * v2 (April 2026): Arcade redesigned to 9-game lineup. Dropped games:
 * Battle Royale, Tug of War, Speed Rush, Escape Room, Card Duel,
 * Wheel Spin, Tournament, Spelling Bee. New games in build queue:
 * Geo Explorer, History Quest, Word Scramble, Math Bee.
 *
 * Each entry now carries `accentColor` — the hex that drives the
 * in-cabinet marquee glow, screen border, and primary button hue
 * (see dashboard/src/styles/arcade-hud.css + CabinetStage.jsx).
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
  { id: 'REVIEW', label: 'REVIEW' },
  { id: 'SOLO', label: 'SOLO' },
  { id: 'COOP', label: 'COOP' },
  { id: 'SUBJECT', label: 'BY SUBJECT' },
];

export const GAME_SHELLS = [
  // ── Phase 1: Existing shells, refactored into the v2 arcade chrome ──
  {
    id: 'quiz_race',
    name: 'Quiz Race',
    marquee_name: 'QUIZ RACE',
    desc: 'Kahoot-style MC — fastest correct answer wins the most points.',
    arcade_tagline: 'INSERT COIN TO PLAY',
    arcade_category: 'TRIVIA',
    accentColor: '#FF3864', // neon coral
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
    accentColor: '#FFBE0B', // gold
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
    accentColor: '#FF006E', // hot pink
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
  {
    id: 'millionaire',
    name: 'Millionaire',
    marquee_name: 'MILLIONAIRE',
    desc: '15 escalating questions, 3 lifelines.',
    arcade_tagline: 'FINAL ANSWER?',
    arcade_category: 'SOLO',
    accentColor: '#3A86FF', // spotlight blue
    icon: 'game_millionaire.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1, max_players: 30, play_time_min: 15,
    best_for: 'Whole-class challenge',
    question_count_default: 15, question_count_locked: true,
  },
  {
    id: 'memory_match',
    name: 'Memory Match',
    marquee_name: 'MEMORY MATCH',
    desc: 'Match question ↔ answer pairs, speed bonus.',
    arcade_tagline: 'FIND THE PAIRS',
    arcade_category: 'SOLO',
    accentColor: '#8338EC', // purple
    icon: 'game_memory.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1, max_players: 30, play_time_min: 10,
    best_for: 'Vocabulary, concepts',
    question_count_default: 12, question_count_min: 6, question_count_max: 20,
  },

  // ── Phase 2: New shells in build queue (not yet playable) ──
  {
    id: 'geo_explorer',
    name: 'Geo Explorer',
    marquee_name: 'GEO EXPLORER',
    desc: 'Real world map. Tap the location that matches the clue — closer = more points.',
    arcade_tagline: 'FIND THE SPOT',
    arcade_category: 'SUBJECT',
    accentColor: '#2EC4B6', // atlas teal
    icon: 'game_geo.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1, max_players: 40, play_time_min: 12,
    best_for: 'Geography, social studies, science (biomes, landforms)',
    question_count_default: 12,
  },
  {
    id: 'history_quest',
    name: 'History Quest',
    marquee_name: 'HISTORY QUEST',
    desc: 'Place each event correctly. Unlock scrolls with fact cards.',
    arcade_tagline: 'INK THE TIMELINE',
    arcade_category: 'SUBJECT',
    accentColor: '#B48838', // parchment gold
    icon: 'game_history.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1, max_players: 40, play_time_min: 15,
    best_for: 'History, social studies, chronology',
    question_count_default: 15,
  },
  {
    id: 'word_scramble',
    name: 'Word Scramble',
    marquee_name: 'WORD SCRAMBLE',
    desc: 'Build a valid crossword from your tile rack. Draw rounds add new letters to your pool.',
    arcade_tagline: 'SPELL TO WIN',
    arcade_category: 'SUBJECT',
    accentColor: '#FFE14F', // warm yellow
    icon: 'game_word_scramble.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 2, max_players: 30, play_time_min: 15,
    best_for: 'ELA, vocabulary, spelling',
    question_count_default: 0, // not driven by question count
    question_count_locked: true,
    extra_settings: [
      { key: 'peel_interval_seconds', type: 'select', label: 'Draw interval',
        options: [
          { value: 45, label: 'Every 45 seconds' },
          { value: 60, label: 'Every 60 seconds' },
          { value: 90, label: 'Every 90 seconds' },
          { value: 0,  label: 'Teacher-controlled' },
        ], default: 60 },
      { key: 'round_length_minutes', type: 'select', label: 'Round length',
        options: [
          { value: 5,  label: '5 minutes' },
          { value: 10, label: '10 minutes' },
          { value: 15, label: '15 minutes' },
        ], default: 10 },
      { key: 'use_curriculum_bonus', type: 'toggle',
        label: 'Bonus points for words from class vocabulary list', default: true },
    ],
  },
  {
    id: 'math_bee',
    name: 'Math Bee',
    marquee_name: 'MATH BEE',
    desc: 'Rapid-fire math fluency — equation flashes, type the answer. Streak multipliers.',
    arcade_tagline: 'KEEP THE STREAK',
    arcade_category: 'SUBJECT',
    accentColor: '#B6FF39', // neon lime
    icon: 'game_math_bee.png',
    icon_fallback: 'gamepad.png',
    phase: 1,
    min_players: 1, max_players: 40, play_time_min: 8,
    best_for: 'Math fact fluency (K–12, grade-scaled)',
    question_count_default: 30,
    extra_settings: [
      { key: 'mode', type: 'select', label: 'Mode',
        options: [
          { value: 'ladder', label: 'Ladder — climb tiers' },
          { value: 'blitz',  label: 'Blitz — answers per minute' },
        ], default: 'blitz' },
    ],
  },
];

export function getShell(id) {
  return GAME_SHELLS.find(s => s.id === id);
}

export function playableShells() {
  return GAME_SHELLS.filter(s => s.phase === 1);
}

export function getAccentColor(id) {
  const s = getShell(id);
  return s?.accentColor || '#FFBE0B';
}
