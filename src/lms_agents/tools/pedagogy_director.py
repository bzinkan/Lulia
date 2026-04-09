"""
Pedagogy Director — grade-band expert agent router.

Loads YAML pedagogy packs (grade-band base + subject overlay), merges them,
and generates a Pedagogy Brief via Sonnet. The brief is a structured JSON
specification that downstream agents (Content, Rubric, QA, Format, Planning,
Video) must honor.

Architecture:
    Work Order (grade=1, subject=math)
        → _grade_to_band("1") = "k2"
        → _normalize_subject("math") = "math"
        → load_pack("1", "math") merges k2.yaml + k2_math.yaml
        → generate_brief(...) makes ONE Sonnet call
        → returns Pedagogy Brief JSON

The brief shapes everything downstream: content difficulty, vocabulary,
layout, templates, video length, lesson pacing.

Falls back gracefully if a pack doesn't exist — the crew still runs, just
without developmental constraints.
"""
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import anthropic
import yaml

log = logging.getLogger(__name__)

# Match the model IDs used elsewhere in the assignment crew for consistency.
SONNET = "claude-sonnet-4-20250514"

PACKS_DIR = Path(__file__).parent.parent / "config" / "pedagogy_packs"
GRADE_BANDS_DIR = PACKS_DIR / "grade_bands"
SUBJECTS_DIR = PACKS_DIR / "subjects"


# ---------------------------------------------------------------------------
# Routing: grade + subject → pack identifiers
# ---------------------------------------------------------------------------

def _grade_to_band(grade: str) -> str:
    """Map a grade level string to a grade band identifier."""
    g = str(grade).strip().upper()
    if g in ("K", "KINDERGARTEN", "0", "1", "2"):
        return "k2"
    if g in ("3", "4", "5"):
        return "g35"
    if g in ("6", "7", "8"):
        return "g68"
    if g in ("9", "10", "11", "12"):
        return "g912"
    # Default to the closest band for edge cases
    log.warning(f"[PedagogyDirector] Unknown grade '{grade}', defaulting to g35")
    return "g35"


def _normalize_subject(subject: str) -> str:
    """Map a subject string to a canonical subject identifier."""
    s = (subject or "").lower().strip()
    if any(k in s for k in ("math", "algebra", "geometry", "calculus", "stat")):
        return "math"
    if any(k in s for k in ("english", "ela", "language art", "reading", "writing", "literature")):
        return "ela"
    if any(k in s for k in ("science", "biology", "physics", "chemistry", "earth")):
        return "science"
    if any(k in s for k in ("social", "history", "civic", "geograph", "economic", "government")):
        return "social"
    return "generalist"


# ---------------------------------------------------------------------------
# Pack loading & merging
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, overlay: dict) -> dict:
    """
    Merge overlay onto base.

    Rules:
    - Dicts are recursively merged. Inner keys present only in base survive
      unless explicitly overwritten by overlay.
    - Lists in overlay replace lists in base (not concatenated). This lets
      a subject overlay redefine an entire phase structure without inheriting
      stale phases from the base.
    - Keys ending in `_override` or `_overrides` deep-merge their fields into
      the corresponding base section (e.g. `video_overrides` deep-merges into
      `video_defaults`), so unstated fields stay inherited from the base.
    - All other keys: overlay wins.
    """
    result = dict(base)
    for key, value in overlay.items():
        # Override semantics — deep-merge into the target section
        if key.endswith("_overrides") or key.endswith("_override"):
            suffix = "_overrides" if key.endswith("_overrides") else "_override"
            stem = key[: -len(suffix)]
            target = stem + "_defaults"
            if target not in result:
                target = stem
            base_section = result.get(target, {}) if isinstance(result.get(target), dict) else {}
            if isinstance(value, dict):
                result[target] = _deep_merge(base_section, value)
            else:
                result[target] = value
            result[key] = value  # keep the original key too for traceability
            continue

        # Recursive dict merge
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@lru_cache(maxsize=64)
def load_pack(grade: str, subject: str) -> Optional[dict]:
    """
    Load and merge the pedagogy pack for a (grade, subject) pair.

    Returns the merged dict, or None if no base pack exists for this grade band.
    Caches results per (grade, subject) — packs are static until reloaded.
    """
    band = _grade_to_band(grade)
    subj = _normalize_subject(subject)

    base_path = GRADE_BANDS_DIR / f"{band}.yaml"
    overlay_path = SUBJECTS_DIR / f"{band}_{subj}.yaml"

    if not base_path.exists():
        log.warning(f"[PedagogyDirector] No grade band pack at {base_path}")
        return None

    with open(base_path, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f) or {}

    if overlay_path.exists():
        with open(overlay_path, "r", encoding="utf-8") as f:
            overlay = yaml.safe_load(f) or {}
        merged = _deep_merge(base, overlay)
        merged["_pack_id"] = f"{band}_{subj}"
        merged["_has_subject_overlay"] = True
        log.info(f"[PedagogyDirector] Loaded pack: {band}_{subj}")
    else:
        merged = dict(base)
        merged["_pack_id"] = band
        merged["_has_subject_overlay"] = False
        log.info(f"[PedagogyDirector] Loaded base pack only: {band} (no {subj} overlay)")

    return merged


def clear_pack_cache() -> None:
    """Clear the pack cache. Call this after editing YAML files at runtime."""
    load_pack.cache_clear()


# ---------------------------------------------------------------------------
# Brief generation
# ---------------------------------------------------------------------------

_BRIEF_SYSTEM_TEMPLATE = """You are the {pack_id} Pedagogy Expert for Lulia, an AI-powered K-12 LMS.

You are an absolute expert in teaching {subject} to {grade_band} students. A veteran teacher of this exact grade band and subject would look at what you specify and say: "Yes — this is right for my students. This is what my worksheets, videos, and lessons look like."

Your job is NOT to generate the content. Your job is to translate a teacher's request into a DEVELOPMENTALLY CORRECT specification — a Pedagogy Brief — that downstream content generation agents will honor as authoritative.

Your expertise is derived from the following Pedagogy Pack. This pack is your source of truth. Every rule in it was authored with reference to peer-reviewed authorities (NAEYC, NCTM, NCTE, NSTA, NGSS, CCSS, C3, NCSS, Science of Reading research, etc.):

--- PEDAGOGY PACK ({pack_id}) ---
{pack_yaml}
--- END PEDAGOGY PACK ---

CRITICAL RULES:
1. You respect the three-tier standards hierarchy (Custom > State > National). You never override the teacher's standards — you shape presentation around them.
2. If teacher curriculum chunks are provided, you ground your brief in that specific source's terminology, manipulatives, and sequence.
3. If class intelligence is provided, you adjust pacing and vocabulary based on what's already taught to that specific class.
4. You output a single JSON object — the Pedagogy Brief — with no prose, no markdown fences, no commentary.
5. Your brief is the authoritative specification. The Content Agent, Format Agent, and QA Agent will all check their outputs against it.

SAFETY CONTRACT — banned terms and hard bans:
The downstream Content Agent will NEVER see the raw Pedagogy Pack — only your brief. This means the brief is the ONLY safety net against the Content Agent using developmentally inappropriate vocabulary or content.

You MUST copy through the FULL `vocabulary.banned_terms` list from the pack into your brief's `content_rules.banned_terms` field. Do not filter, summarize, or "select the relevant ones." Every banned term in the pack must appear in your brief verbatim. The same applies to `hard_bans` — copy the entire list into `hard_bans_inherited`.

You MAY add additional banned terms specific to the work order if you spot any, but you may NEVER drop a term that was in the pack.
"""


_BRIEF_SCHEMA = """{
  "grade_band": "K-2 | 3-5 | 6-8 | 9-12",
  "grade_level": "<specific grade from the work order>",
  "subject": "<canonical subject>",
  "pack_id": "<the pack id used>",

  "developmental_constraints": {
    "cognitive_stage": "<short phrase>",
    "attention_span_min": <int>,
    "max_reading_level_lexile": <int>,
    "max_sentence_length_words": <int>,
    "working_memory_instruction_cap": <int>
  },

  "layout_directives": {
    "min_font_size_pt": <int>,
    "body_font_size_pt": <int>,
    "max_problems_per_page": <int>,
    "min_whitespace_pct": <int>,
    "answer_box_min_height_in": <float>,
    "every_question_needs_image": <bool>,
    "mascot_required": <bool>,
    "equation_orientation": "<vertical_stacked | horizontal | n/a>",
    "handwriting_lines_required": <bool>
  },

  "template_recommendation": {
    "primary": "<template_id>",
    "alternatives": ["<template_id>", "<template_id>"],
    "banned_for_this_task": ["<template_id>", ...],
    "rationale": "<one sentence why this template fits the standard + grade>"
  },

  "content_rules": {
    "vocabulary_tier_caps": {"tier_1_pct": <int>, "tier_2_pct": <int>, "tier_3_pct": <int>},
    "allowed_tier_3_terms": ["<term>", ...],
    "banned_terms": ["<term>", ...],
    "word_problem_contexts_allowed": ["<context>", ...],
    "word_problem_contexts_banned": ["<context>", ...],
    "character_name_pool": ["<name>", ...],
    "subject_specific_requirements": ["<requirement>", ...]
  },

  "scaffolds_required": ["<scaffold>", ...],

  "assessment_modes_preferred": ["<mode>", ...],
  "assessment_modes_banned": ["<mode>", ...],

  "lesson_plan_spec": {
    "total_duration_min": <int>,
    "structure": [{"phase": "<name>", "duration_min": <int>, "description": "<short>"}],
    "manipulatives_required": <bool>,
    "transitions_every_min": <int>
  },

  "video_spec": {
    "length_min": <int>,
    "length_max": <int>,
    "narrator_style": "<style>",
    "narrator_pace_wpm": <int>,
    "mascot_required": <bool>,
    "concepts_per_video": <int>,
    "on_screen_visual_required": <bool>
  },

  "curriculum_grounding": {
    "recognized_curriculum": "<curriculum name if identifiable from KB chunks, else null>",
    "terminology_match_required": <bool>,
    "kb_chunks_used_count": <int>
  },

  "class_intelligence_adjustments": {
    "vocab_already_taught_honored": <bool>,
    "standards_already_covered_honored": <bool>,
    "pacing_note": "<short note or empty string>"
  },

  "reference_exemplar_guidance": {
    "primary_exemplar_source": "<source name of the reference exemplar the Content Agent should match, or null>",
    "shape_to_match": "<short description of the structural shape — question count, feature mix, scaffold pattern — pulled directly from the exemplar, or null>",
    "exemplar_count": <int — how many reference exemplars were available>,
    "notes_on_shape_matching": "<1-2 sentences telling the Content Agent how to honor the reference shape while generating fresh content>"
  },

  "hard_bans_inherited": ["<ban>", ...],

  "pedagogy_notes": "<2-4 sentences explaining the key developmental choices for this specific work order — why this template, why these constraints, what a veteran teacher of this grade would want to see>"
}"""


def _build_user_prompt(
    work_order: dict,
    curriculum_output: dict,
    kb_chunks: Optional[list],
    class_intel_prompt: Optional[str],
    reference_exemplars: Optional[list] = None,
) -> str:
    """Build the user message for the Sonnet brief generator."""
    standards_text = "\n".join(
        f"- {s['code']}: {s['description']}"
        for s in curriculum_output.get("standards", [])
    ) or "(none provided — infer from subject + grade)"

    kb_section = ""
    if kb_chunks:
        kb_section = "\n\nTEACHER CURRICULUM CHUNKS (from RAG KB — ground your brief in this source):\n"
        for i, chunk in enumerate(kb_chunks[:5], 1):
            source = chunk.get("source_name", "unknown")
            content = chunk.get("content", "")[:500]
            kb_section += f"\n[Chunk {i}] Source: {source}\n{content}\n"
    else:
        kb_section = "\n\nTEACHER CURRICULUM CHUNKS: (none — teacher did not upload curriculum for this request)\n"

    class_section = ""
    if class_intel_prompt:
        class_section = f"\n\nCLASS INTELLIGENCE CONTEXT:\n{class_intel_prompt}\n"
    else:
        class_section = "\n\nCLASS INTELLIGENCE: (none — no prior class context available)\n"

    exemplar_section = ""
    if reference_exemplars:
        from src.lms_agents.tools.reference_retrieval import format_exemplars_for_prompt
        exemplar_section = "\n\n" + format_exemplars_for_prompt(reference_exemplars) + "\n"
        exemplar_section += (
            "\nIMPORTANT: Use the reference exemplars above to populate the "
            "`reference_exemplar_guidance` section of your brief. Pick the "
            "exemplar from the highest-priority lane as the `primary_exemplar_source` "
            "and describe its structural shape in `shape_to_match`. The Content "
            "Agent will match this shape when generating the assignment.\n"
        )
    else:
        exemplar_section = (
            "\n\nREFERENCE EXEMPLARS: (none found in the library for this topic "
            "+ grade band — the Content Agent will generate from pedagogy rules alone)\n"
            "\nIn the brief, set reference_exemplar_guidance.primary_exemplar_source "
            "to null and exemplar_count to 0.\n"
        )

    return f"""Generate a Pedagogy Brief for the following assignment request.

WORK ORDER:
- Grade Level: {work_order.get('grade_level', '?')}
- Subject: {work_order.get('subject', '?')}
- Output Template Requested: {work_order.get('output_template_id', 'worksheet')}
- Question Count Requested: {work_order.get('question_count', 10)}
- Difficulty Distribution: {json.dumps(work_order.get('difficulty_distribution', {}))}

ALIGNED STANDARDS (respect the three-tier hierarchy — these are authoritative):
{standards_text}
{kb_section}
{class_section}
{exemplar_section}

Your task: produce a single JSON object matching exactly this schema. Fill every field. Use the pack as your source of truth. Do not include markdown fences or any prose outside the JSON.

SCHEMA:
{_BRIEF_SCHEMA}

Remember: a veteran {work_order.get('grade_level', '?')}-grade {work_order.get('subject', '?')} teacher should look at your brief and recognize it as exactly right for their students."""


def _extract_json(text: str) -> Optional[dict]:
    """Extract a JSON object from a Claude response that may have fences or prose."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Find the first {...} block via brace matching
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def generate_brief(
    work_order: dict,
    curriculum_output: dict,
    kb_chunks: Optional[list] = None,
    class_intel_prompt: Optional[str] = None,
    reference_exemplars: Optional[list] = None,
    client: Optional[anthropic.Anthropic] = None,
) -> Optional[dict]:
    """
    Generate a Pedagogy Brief for a work order.

    Args:
        work_order: the work order dict (must contain grade_level, subject)
        curriculum_output: output from the Curriculum Agent (standards + metadata)
        kb_chunks: optional list of RAG KB chunks from teacher's uploaded curriculum
        class_intel_prompt: optional AI context string from class_intelligence tool
        reference_exemplars: optional list of reference exemplars from the
            reference_retrieval module — real worksheets/slide decks/etc. from
            the teacher lanes whose structural shape the Content Agent will match
        client: optional pre-initialized Anthropic client

    Returns:
        Pedagogy Brief dict, or None if no pack exists for this grade band.
        The crew falls back to un-constrained generation when None is returned.
    """
    grade = str(work_order.get("grade_level", ""))
    subject = work_order.get("subject", "")

    pack = load_pack(grade, subject)
    if pack is None:
        log.warning(
            f"[PedagogyDirector] No pack for grade={grade}, subject={subject} — "
            f"crew will run without a brief"
        )
        return None

    pack_id = pack.get("_pack_id", "unknown")
    grade_band = pack.get("grade_band", "?")

    log.info(f"[PedagogyDirector] Generating brief via {pack_id}")

    if client is None:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Strip internal metadata before serializing the pack into the prompt
    prompt_pack = {k: v for k, v in pack.items() if not k.startswith("_")}
    pack_yaml = yaml.safe_dump(prompt_pack, sort_keys=False, allow_unicode=True)

    system = _BRIEF_SYSTEM_TEMPLATE.format(
        pack_id=pack_id,
        subject=subject,
        grade_band=grade_band,
        pack_yaml=pack_yaml,
    )
    user = _build_user_prompt(
        work_order, curriculum_output, kb_chunks, class_intel_prompt, reference_exemplars
    )

    try:
        resp = client.messages.create(
            model=SONNET,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text
    except Exception as e:
        log.error(f"[PedagogyDirector] Sonnet call failed: {e}")
        return None

    brief = _extract_json(text)
    if brief is None:
        log.warning("[PedagogyDirector] Failed to parse JSON from Sonnet response")
        return None

    # Tag the brief with its source pack for traceability downstream
    brief["_pack_id"] = pack_id
    brief["_grade_band"] = grade_band
    # Attach the raw exemplars to the brief so downstream agents can access
    # the full excerpts + metadata, not just the summarized guidance.
    if reference_exemplars:
        brief["_reference_exemplars"] = reference_exemplars

    log.info(
        f"[PedagogyDirector] Brief generated: template={brief.get('template_recommendation', {}).get('primary', '?')}, "
        f"max_problems={brief.get('layout_directives', {}).get('max_problems_per_page', '?')}, "
        f"exemplars={len(reference_exemplars) if reference_exemplars else 0}"
    )
    return brief


# ---------------------------------------------------------------------------
# Helper: format brief for inclusion in downstream agent prompts
# ---------------------------------------------------------------------------

def format_brief_for_prompt(brief: dict) -> str:
    """
    Render a brief as a compact constraint block for injection into
    Content Agent or QA Agent prompts. Keeps the most rule-bearing sections.
    """
    if not brief:
        return ""

    sections = []
    sections.append(f"=== PEDAGOGY BRIEF (authoritative — {brief.get('_pack_id', '?')}) ===")

    if "developmental_constraints" in brief:
        sections.append(f"DEVELOPMENTAL CONSTRAINTS: {json.dumps(brief['developmental_constraints'])}")
    if "layout_directives" in brief:
        sections.append(f"LAYOUT DIRECTIVES: {json.dumps(brief['layout_directives'])}")
    if "template_recommendation" in brief:
        sections.append(f"TEMPLATE: {json.dumps(brief['template_recommendation'])}")
    if "content_rules" in brief:
        sections.append(f"CONTENT RULES: {json.dumps(brief['content_rules'])}")
    if "scaffolds_required" in brief:
        sections.append(f"SCAFFOLDS REQUIRED: {json.dumps(brief['scaffolds_required'])}")
    if "assessment_modes_preferred" in brief:
        sections.append(f"ASSESSMENT MODES (preferred): {json.dumps(brief['assessment_modes_preferred'])}")
    if "assessment_modes_banned" in brief:
        sections.append(f"ASSESSMENT MODES (BANNED): {json.dumps(brief['assessment_modes_banned'])}")
    if "hard_bans_inherited" in brief:
        sections.append(f"HARD BANS: {json.dumps(brief['hard_bans_inherited'])}")
    if "pedagogy_notes" in brief:
        sections.append(f"PEDAGOGY NOTES: {brief['pedagogy_notes']}")

    sections.append("=== END PEDAGOGY BRIEF ===")
    return "\n".join(sections)
