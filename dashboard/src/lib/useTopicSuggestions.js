'use client';
import { useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';

/**
 * Debounced Haiku-backed topic suggestions.
 *
 * Fires 500ms after the teacher stops typing, only when the topic is long
 * enough to be ambiguous (3+ chars) but not already specific (< 4 words).
 * Cancels in-flight requests on every new keystroke. Fails silent — bad
 * network or rate limit just returns [] and never blocks the user.
 *
 * Usage:
 *   const { suggestions, loading } = useTopicSuggestions({
 *     activityType: 'crossword_interactive',
 *     topic: 'fractions',
 *     classId: 'uuid',
 *   });
 */
export function useTopicSuggestions({ activityType, topic, classId, teacherId }) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef(null);
  const timerRef = useRef(null);
  const lastQueryRef = useRef(null);

  useEffect(() => {
    // Cancel any pending debounce + in-flight request
    if (timerRef.current) clearTimeout(timerRef.current);
    if (abortRef.current) { try { abortRef.current.abort(); } catch {} abortRef.current = null; }

    const t = (topic || '').trim();

    // Gate: too short, or already specific (4+ whitespace tokens)
    if (t.length < 3) {
      setSuggestions([]);
      setLoading(false);
      return;
    }
    if (t.split(/\s+/).filter(Boolean).length >= 4) {
      setSuggestions([]);
      setLoading(false);
      return;
    }

    const queryKey = `${activityType}|${classId || ''}|${t.toLowerCase()}`;
    if (queryKey === lastQueryRef.current) return; // don't re-fetch the exact same thing

    timerRef.current = setTimeout(async () => {
      lastQueryRef.current = queryKey;
      setLoading(true);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/assistant/topic-suggestions`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              activity_type: activityType,
              partial_topic: t,
              class_id: classId,
              teacher_id: teacherId,
            }),
            signal: controller.signal,
          }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!controller.signal.aborted) {
          setSuggestions(Array.isArray(data.suggestions) ? data.suggestions : []);
        }
      } catch (e) {
        if (e?.name !== 'AbortError') {
          // Silent fail — don't block the user
          setSuggestions([]);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 500);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (abortRef.current) { try { abortRef.current.abort(); } catch {} }
    };
  }, [activityType, topic, classId, teacherId]);

  return { suggestions, loading };
}
