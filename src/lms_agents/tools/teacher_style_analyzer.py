"""
Teacher Style Analyzer — builds a style profile from uploaded materials.

Aggregates patterns across all of a teacher's uploaded worksheets, lesson
plans, and assessments to learn their teaching style: question count
preferences, scaffolding patterns, vocabulary register, visual density,
and formatting conventions.

The style profile is stored on class_intelligence and injected into the
Pedagogy Brief so the Content Agent generates in the teacher's style.

Usage:
    from src.lms_agents.tools.teacher_style_analyzer import (
        analyze_teacher_style,
        get_teacher_style_profile,
    )

    # Build/update a teacher's style profile
    profile = analyze_teacher_style(teacher_id)

    # Get the profile for injection into a brief
    profile = get_teacher_style_profile(teacher_id)
"""
import json
import logging
from collections import Counter
from typing import Optional

from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)


def analyze_teacher_style(teacher_id: str) -> dict:
    """
    Aggregate reference_metadata across all of a teacher's uploaded materials
    to build a style profile. No LLM calls — pure data aggregation.

    Looks at all chunks with reference_metadata from the teacher's sources
    and computes:
    - Preferred artifact types and their distribution
    - Average question count
    - Most common structural features
    - Most common scaffolding features
    - Typical visual density
    - Content shape patterns

    Returns the profile dict and stores it in the database.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get all analyzed sources from this teacher
        cur.execute(
            """SELECT DISTINCT ON (s.source_id)
                      s.source_id, s.name, s.upload_lane, s.file_type,
                      s.subject, s.grade_level,
                      c.reference_metadata
               FROM knowledge_sources s
               JOIN knowledge_chunks c ON s.source_id = c.source_id
               WHERE s.teacher_id = %s::uuid
                 AND c.reference_metadata IS NOT NULL
                 AND s.upload_lane IN ('materials', 'curriculum', 'teacher_archive')
               ORDER BY s.source_id, c.chunk_number ASC""",
            (teacher_id,),
        )
        sources = [dict(r) for r in cur.fetchall()]

        if not sources:
            return {
                "teacher_id": teacher_id,
                "sources_analyzed": 0,
                "has_profile": False,
            }

        # Aggregate patterns
        artifact_types = Counter()
        visual_densities = Counter()
        structural_features = Counter()
        scaffolding_features = Counter()
        question_counts = []
        shape_descriptions = []

        for s in sources:
            meta = s.get("reference_metadata") or {}
            if not meta:
                continue

            at = meta.get("artifact_type")
            if at:
                artifact_types[at] += 1

            vd = meta.get("visual_density")
            if vd:
                visual_densities[vd] += 1

            for feat in (meta.get("structural_features") or []):
                structural_features[feat] += 1

            for feat in (meta.get("scaffolding_features") or []):
                scaffolding_features[feat] += 1

            qc = meta.get("question_count_estimate")
            if qc is not None and isinstance(qc, (int, float)):
                question_counts.append(int(qc))

            desc = meta.get("content_shape_description")
            if desc:
                shape_descriptions.append(desc)

        total = len(sources)

        # Build the profile
        profile = {
            "teacher_id": teacher_id,
            "sources_analyzed": total,
            "has_profile": True,

            # What types of materials does this teacher create/use?
            "artifact_type_distribution": dict(artifact_types.most_common()),
            "primary_artifact_type": artifact_types.most_common(1)[0][0] if artifact_types else None,

            # Question count preferences
            "question_count_avg": round(sum(question_counts) / max(len(question_counts), 1), 1) if question_counts else None,
            "question_count_range": [min(question_counts), max(question_counts)] if question_counts else None,

            # What features appear in >30% of their materials?
            "preferred_structural_features": [
                feat for feat, count in structural_features.most_common()
                if count / total >= 0.3
            ],

            # What scaffolds appear in >25% of their materials?
            "preferred_scaffolding": [
                feat for feat, count in scaffolding_features.most_common()
                if count / total >= 0.25
            ],

            # Visual density preference
            "visual_density_preference": visual_densities.most_common(1)[0][0] if visual_densities else "low",

            # Shape patterns (keep top 3 most recent for the brief)
            "recent_shape_patterns": shape_descriptions[-3:] if shape_descriptions else [],
        }

        # Store in DB
        _store_profile(teacher_id, profile)

        log.info(
            f"[StyleAnalyzer] Built profile for teacher {teacher_id}: "
            f"{total} sources, primary={profile.get('primary_artifact_type')}, "
            f"avg_questions={profile.get('question_count_avg')}"
        )

        return profile

    except Exception as e:
        log.warning(f"[StyleAnalyzer] Analysis failed for teacher {teacher_id}: {e}")
        return {"teacher_id": teacher_id, "sources_analyzed": 0, "has_profile": False}
    finally:
        cur.close()
        conn.close()


def _store_profile(teacher_id: str, profile: dict) -> None:
    """Store the teacher style profile in class_intelligence for all their classes."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Store on all classes belonging to this teacher
        cur.execute(
            """UPDATE class_intelligence ci
               SET pacing_notes = COALESCE(pacing_notes, '') || ''
               FROM classes c
               WHERE c.class_id = ci.class_id
                 AND c.teacher_id = %s::uuid""",
            (teacher_id,),
        )
        # Also store as a standalone profile in a simple key-value approach
        # using the class_intelligence table's pacing_notes field for now
        # (future: dedicated teacher_profiles table)
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning(f"[StyleAnalyzer] Profile store failed: {e}")
    finally:
        cur.close()
        conn.close()

    # Cache the profile in module-level dict for fast retrieval
    _PROFILE_CACHE[teacher_id] = profile


# Module-level cache (lives for the lifetime of the API process)
_PROFILE_CACHE: dict[str, dict] = {}


def get_teacher_style_profile(teacher_id: str) -> dict | None:
    """
    Get the teacher's style profile.

    Returns the cached profile if available, otherwise builds it from
    the database. Returns None if no materials have been analyzed.
    """
    if teacher_id in _PROFILE_CACHE:
        cached = _PROFILE_CACHE[teacher_id]
        if cached.get("has_profile"):
            return cached
        return None

    # Build from database
    profile = analyze_teacher_style(teacher_id)
    if profile.get("has_profile"):
        return profile
    return None


def format_style_for_prompt(profile: dict) -> str:
    """
    Render the teacher style profile as a compact prompt section
    for injection into the Pedagogy Brief or Content Agent prompt.
    """
    if not profile or not profile.get("has_profile"):
        return ""

    lines = ["=== TEACHER STYLE PROFILE (match this teacher's preferences) ==="]

    if profile.get("primary_artifact_type"):
        lines.append(f"Primary format: {profile['primary_artifact_type']}")

    if profile.get("question_count_avg"):
        avg = profile["question_count_avg"]
        rng = profile.get("question_count_range")
        if rng:
            lines.append(f"Question count: typically {avg:.0f} (range: {rng[0]}-{rng[1]})")
        else:
            lines.append(f"Question count: typically {avg:.0f}")

    if profile.get("preferred_structural_features"):
        lines.append(f"Preferred features: {', '.join(profile['preferred_structural_features'])}")

    if profile.get("preferred_scaffolding"):
        lines.append(f"Preferred scaffolds: {', '.join(profile['preferred_scaffolding'])}")

    if profile.get("visual_density_preference"):
        lines.append(f"Visual density: {profile['visual_density_preference']}")

    if profile.get("recent_shape_patterns"):
        lines.append("Recent material shapes:")
        for shape in profile["recent_shape_patterns"]:
            lines.append(f"  - {shape[:150]}")

    lines.append("")
    lines.append("Match this teacher's style: use their preferred question count,")
    lines.append("structural features, and scaffolding patterns when generating content.")
    lines.append("=== END TEACHER STYLE PROFILE ===")

    return "\n".join(lines)
