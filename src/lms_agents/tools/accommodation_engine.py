"""
Accommodation Engine — generates modified versions of assignments for
students with IEP/504/ELL/Gifted accommodations.

Key principle: ALL versions use the SAME template and design theme (dignity).
Only the content changes — not the visual design.

Three layers:
  1. Toggle: teacher enables/disables accommodation generation per assignment
  2. Profiles: reusable modification sets (built-in defaults + custom)
  3. Per-student: individual students linked to profiles with optional overrides
"""
import json
import logging
import os
import re
from copy import deepcopy
from uuid import uuid4

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

SONNET = "claude-sonnet-4-20250514"
HAIKU = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Default profiles — teachers can customize or create their own
# ---------------------------------------------------------------------------

DEFAULT_PROFILES = {
    "iep_reading_reduced": {
        "name": "IEP — Reading/Reduced",
        "type": "iep",
        "modifications": {
            "reduce_questions_pct": 50,
            "simplify_language": True,
            "grade_level_adjust": -2,
            "larger_font": True,
            "font_size_min": 16,
            "reduce_answer_choices": 3,
            "extra_answer_space": True,
            "visual_supports": True,
        },
    },
    "504_extended_time": {
        "name": "504 — Extended Time",
        "type": "504",
        "modifications": {
            "reduce_questions_pct": 25,
            "larger_font": True,
            "font_size_min": 14,
            "checklist_format": True,
        },
    },
    "ell_beginner": {
        "name": "ELL — Beginner",
        "type": "ell",
        "modifications": {
            "vocabulary_glossary": True,
            "visual_supports": True,
            "simplify_language": True,
            "sentence_starters": True,
        },
    },
    "ell_intermediate": {
        "name": "ELL — Intermediate",
        "type": "ell",
        "modifications": {
            "vocabulary_glossary": True,
            "sentence_starters": True,
        },
    },
    "gifted_enriched": {
        "name": "Gifted — Enriched",
        "type": "gifted",
        "modifications": {
            "increase_difficulty": True,
            "grade_level_adjust": 1,
            "add_extension_questions": 3,
            "depth_of_knowledge": "3-4",
            "real_world_application": True,
        },
    },
}


def get_profile(profile_id: str, teacher_id: str | None = None) -> dict | None:
    """Get a profile by ID — checks custom DB profiles first, then defaults."""
    if teacher_id:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM accommodation_profiles WHERE profile_id = %s",
            (profile_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return dict(row)

    return DEFAULT_PROFILES.get(profile_id)


def get_all_profiles(teacher_id: str) -> list[dict]:
    """Get all profiles — defaults + teacher's custom profiles."""
    profiles = []
    for pid, p in DEFAULT_PROFILES.items():
        profiles.append({"profile_id": pid, "is_default": True, **p})

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM accommodation_profiles WHERE teacher_id = %s::uuid ORDER BY name",
        (teacher_id,),
    )
    for row in cur.fetchall():
        profiles.append({**dict(row), "is_default": False})
    cur.close()
    conn.close()
    return profiles


def apply_modifications(
    original_content: dict,
    profile: dict,
    subject: str = "",
    grade: str = "",
) -> dict:
    """
    Use Claude to apply accommodation modifications to content.

    The Content Agent regenerates the content with the modifications applied.
    This is the core of the accommodation system.
    """
    mods = profile.get("modifications", {})
    profile_name = profile.get("name", "accommodation")
    content = deepcopy(original_content)

    # Build modification instructions for Claude
    instructions = []

    if mods.get("reduce_questions_pct"):
        pct = mods["reduce_questions_pct"]
        instructions.append(f"Reduce the number of questions by {pct}% — keep the easier ones, remove the hardest ones")

    if mods.get("simplify_language"):
        adj = mods.get("grade_level_adjust", -2)
        instructions.append(f"Simplify all language to {abs(adj)} grade levels below (grade {int(grade or 4) + adj}). Use shorter sentences, simpler vocabulary")

    if mods.get("reduce_answer_choices"):
        n = mods["reduce_answer_choices"]
        instructions.append(f"For multiple choice questions, reduce to {n} answer choices (remove the least plausible distractor)")

    if mods.get("visual_supports"):
        instructions.append("Add visual cues: [DRAWING] placeholders where helpful, describe simple diagrams students could draw")

    if mods.get("vocabulary_glossary"):
        instructions.append("Add a vocabulary glossary at the top with key terms and simple definitions")

    if mods.get("sentence_starters"):
        instructions.append("For any open-ended questions, provide sentence starters (e.g. 'The answer is ___ because...')")

    if mods.get("checklist_format"):
        instructions.append("Break multi-step problems into numbered checklists with checkboxes")

    if mods.get("increase_difficulty"):
        adj = mods.get("grade_level_adjust", 1)
        instructions.append(f"Increase difficulty by {adj} grade level(s). Use more complex scenarios and multi-step problems")

    if mods.get("add_extension_questions"):
        n = mods["add_extension_questions"]
        instructions.append(f"Add {n} extension/challenge questions that require higher-order thinking (DOK 3-4, real-world application)")

    if mods.get("real_world_application"):
        instructions.append("Frame problems in real-world contexts (money, measurement, engineering, etc.)")

    if not instructions:
        return content  # No modifications needed

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    system = (
        f"You are modifying educational content for a {profile_name} accommodation. "
        f"Subject: {subject}, Grade: {grade}. "
        f"Keep the same topic and standards alignment. Only change what the modifications require."
    )

    user = f"""Modify this assignment content according to these accommodation requirements:

ACCOMMODATION PROFILE: {profile_name}
MODIFICATIONS:
{chr(10).join(f'- {inst}' for inst in instructions)}

ORIGINAL CONTENT:
{json.dumps(content, indent=2)}

Generate the modified version as a JSON object with the SAME structure:
{{
  "title": "same title with accommodation note",
  "instructions": "modified instructions",
  "questions": [
    {{
      "question_number": 1,
      "question_text": "modified question",
      "answer": "answer",
      "difficulty": "easy|medium|hard",
      "standard_code": "keep same standard",
      "explanation": "explanation"
    }}
  ],
  "vocabulary_glossary": [  // only if vocabulary_glossary modification is requested
    {{"term": "word", "definition": "simple definition"}}
  ]
}}

IMPORTANT:
- Keep all standard_code values the same
- Keep the same topic/theme
- Only apply the specific modifications listed above
- Do NOT change the template type or overall structure

Respond with ONLY the JSON object."""

    resp = client.messages.create(
        model=HAIKU, max_tokens=4096, system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = resp.content[0].text

    # Parse JSON from response
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
        if match:
            try:
                result = json.loads(match.group(1))
            except json.JSONDecodeError:
                result = None
        else:
            for sc, ec in [("{", "}"), ("[", "]")]:
                start = text.find(sc)
                if start >= 0:
                    depth = 0
                    for i in range(start, len(text)):
                        if text[i] == sc:
                            depth += 1
                        elif text[i] == ec:
                            depth -= 1
                            if depth == 0:
                                try:
                                    result = json.loads(text[start:i + 1])
                                except json.JSONDecodeError:
                                    pass
                                break
                    if result:
                        break

    if result is None:
        log.warning(f"[Accommodation] Failed to parse modified content for {profile_name}")
        return content

    # Apply font size metadata
    if mods.get("larger_font"):
        result["_font_size_min"] = mods.get("font_size_min", 14)
    if mods.get("extra_answer_space"):
        result["_extra_answer_space"] = True

    log.info(f"[Accommodation] Modified content for {profile_name}: {len(result.get('questions', []))} questions")
    return result
