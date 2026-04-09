"""
Reference-Grounded Generation — A/B validation test.

Runs the Assignment Crew TWICE on the same work order:
  Run A (baseline):      reference_exemplars forced to None
                         → Content Agent generates from pedagogy rules alone
  Run B (grounded):      normal retrieval pulls real exemplars from the
                         teacher_archive / teacher_reference lanes
                         → Content Agent matches exemplar structural shape

Outputs both HTML versions so you can eyeball the visual + structural
differences, and prints a side-by-side comparison of structural metadata.

Cost: ~$0.15-0.25 (2 full crew runs, ~6 Sonnet + Haiku calls each)

Default test case: 6th grade Earth Science rock cycle worksheet. Change
the fixture at the bottom to test other grade bands / topics.

Usage:
    docker compose exec api python scripts/test_reference_grounded_generation.py
"""
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("src.lms_agents.tools.pedagogy_director").setLevel(logging.INFO)
logging.getLogger("src.lms_agents.crews.assignment_crew").setLevel(logging.INFO)
logging.getLogger("src.lms_agents.tools.reference_retrieval").setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Test fixture — 6-8 Earth Science is the strongest area of the library
# ---------------------------------------------------------------------------

FIXTURE = {
    "work_order_id": "TEST-REF-GROUNDED-6SCI",
    "teacher_id": "00000000-0000-0000-0000-000000000001",
    "grade_level": "6",
    "subject": "Science",
    "output_template_id": "worksheet",
    "output_format": "html",
    "design_theme": "modern_clean",
    "standards_ids": ["MS-ESS2-1"],
    "question_count": 15,
    "difficulty_distribution": {"easy": 5, "medium": 7, "hard": 3},
    "has_kb_coverage": False,
}

# Fake curriculum output (so we don't need a live standards query for this test)
CURRICULUM_OUTPUT = {
    "subject": "Science",
    "grade_level": "6",
    "standards": [
        {
            "code": "MS-ESS2-1",
            "description": (
                "Develop a model to describe the cycling of Earth's materials "
                "and the flow of energy that drives this process. Emphasis is "
                "on the processes of melting, crystallization, weathering, "
                "deformation, and sedimentation, which act together to form "
                "minerals and rocks through the cycling of Earth's materials."
            ),
        }
    ],
}


def run_crew(work_order: dict, force_no_exemplars: bool) -> dict:
    """
    Run the Assignment Crew either with or without reference exemplars.

    When force_no_exemplars=True, we monkey-patch the exemplar fetcher
    to return None so the brief falls back to pedagogy-rules-only mode.
    """
    import src.lms_agents.crews.assignment_crew as crew_module

    if force_no_exemplars:
        original_fetch = crew_module._fetch_reference_exemplars
        crew_module._fetch_reference_exemplars = lambda wo, co: None
        try:
            return crew_module.run_assignment_crew(work_order)
        finally:
            crew_module._fetch_reference_exemplars = original_fetch
    else:
        return crew_module.run_assignment_crew(work_order)


def summarize_run(label: str, result: dict) -> dict:
    """Extract the structural signals we care about from a crew result."""
    brief = result.get("pedagogy_brief") or {}
    content = result.get("content") or {}
    questions = content.get("questions") or []

    exemplar_guidance = brief.get("reference_exemplar_guidance") or {}
    raw_exemplars = brief.get("_reference_exemplars") or []

    structural = {}
    feature_counts = {}
    for q in questions:
        v = q.get("visual") or {}
        if v and isinstance(v, dict) and v.get("type"):
            feature_counts[v["type"]] = feature_counts.get(v["type"], 0) + 1

    return {
        "label": label,
        "assignment_id": result.get("assignment_id"),
        "title": content.get("title", ""),
        "template": result.get("template"),
        "pack_id": result.get("pedagogy_pack_id"),
        "qa_score": result.get("qa_score"),
        "qa_approved": result.get("qa_approved"),
        "question_count": len(questions),
        "exemplar_count": len(raw_exemplars),
        "primary_exemplar_source": exemplar_guidance.get("primary_exemplar_source"),
        "shape_to_match": exemplar_guidance.get("shape_to_match"),
        "shape_notes": exemplar_guidance.get("notes_on_shape_matching"),
        "visual_types_used": feature_counts,
        "student_html_chars": len(result.get("student_html") or ""),
        "svg_count": (result.get("student_html") or "").count("<svg"),
        "sample_questions": [
            {
                "n": q.get("question_number"),
                "text": (q.get("question_text") or "")[:200],
                "answer": (q.get("answer") or "")[:100],
                "has_visual": bool(q.get("visual")),
                "visual_type": (q.get("visual") or {}).get("type"),
            }
            for q in questions[:3]
        ],
    }


def save_html(result: dict, path: Path) -> None:
    html = result.get("student_html") or ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def print_summary(summary: dict) -> None:
    print(f"\n  === {summary['label']} ===")
    print(f"  assignment_id:           {summary['assignment_id']}")
    print(f"  title:                   {summary['title']}")
    print(f"  template:                {summary['template']}")
    print(f"  pack_id:                 {summary['pack_id']}")
    print(f"  qa_score:                {summary['qa_score']}")
    print(f"  qa_approved:             {summary['qa_approved']}")
    print(f"  question_count:          {summary['question_count']}")
    print(f"  exemplar_count:          {summary['exemplar_count']}")
    print(f"  primary_exemplar_source: {summary['primary_exemplar_source']}")
    print(f"  shape_to_match:          {(summary['shape_to_match'] or '')[:140]}")
    if summary['shape_notes']:
        print(f"  shape_notes:             {summary['shape_notes'][:140]}")
    print(f"  visual_types_used:       {summary['visual_types_used']}")
    print(f"  student_html_chars:      {summary['student_html_chars']:,}")
    print(f"  svg_count:               {summary['svg_count']}")
    print(f"  sample questions:")
    for sq in summary["sample_questions"]:
        viz = f"  [visual: {sq['visual_type']}]" if sq["has_visual"] else ""
        print(f"    {sq['n']}. {sq['text']}{viz}")


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(2)

    print("=" * 72)
    print("REFERENCE-GROUNDED GENERATION — A/B TEST")
    print("=" * 72)
    print(f"Fixture: grade {FIXTURE['grade_level']} {FIXTURE['subject']}")
    print(f"Standard: {CURRICULUM_OUTPUT['standards'][0]['code']}")
    print(f"         {CURRICULUM_OUTPUT['standards'][0]['description'][:100]}...")

    # Patch the curriculum agent to return our fake output (skip DB lookup)
    import src.lms_agents.crews.assignment_crew as crew_module
    original_curriculum = crew_module.run_curriculum_agent
    crew_module.run_curriculum_agent = lambda client, wo: CURRICULUM_OUTPUT
    # Also patch the database store so we don't write test data to prod tables
    crew_module._store_assignment = (
        lambda wo, content_output, rubric_output, qa_output, format_output: "TEST-NO-STORE"
    )

    try:
        print("\n" + "-" * 72)
        print("RUN A — BASELINE (reference_exemplars disabled)")
        print("-" * 72)
        result_a = run_crew(dict(FIXTURE), force_no_exemplars=True)
        summary_a = summarize_run("BASELINE (no exemplars)", result_a)
        save_html(result_a, Path("/app/scripts/test_output_a_baseline.html"))
        print("  saved HTML: scripts/test_output_a_baseline.html")

        print("\n" + "-" * 72)
        print("RUN B — REFERENCE-GROUNDED (exemplars from library)")
        print("-" * 72)
        result_b = run_crew(dict(FIXTURE), force_no_exemplars=False)
        summary_b = summarize_run("REFERENCE-GROUNDED", result_b)
        save_html(result_b, Path("/app/scripts/test_output_b_grounded.html"))
        print("  saved HTML: scripts/test_output_b_grounded.html")
    finally:
        crew_module.run_curriculum_agent = original_curriculum

    print("\n" + "=" * 72)
    print("COMPARISON")
    print("=" * 72)
    print_summary(summary_a)
    print_summary(summary_b)

    # Verdict
    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)

    differences = []
    if summary_b["exemplar_count"] > 0 and summary_a["exemplar_count"] == 0:
        differences.append(
            f"[OK] Reference-grounded run used {summary_b['exemplar_count']} exemplars; "
            f"baseline used 0"
        )
    if summary_b["primary_exemplar_source"]:
        differences.append(
            f"[OK] Reference-grounded brief cites: {summary_b['primary_exemplar_source'][:70]}"
        )
    if summary_b["shape_to_match"]:
        differences.append(
            f"[OK] Reference-grounded brief has shape_to_match directive"
        )
    if summary_b["qa_score"] and summary_a["qa_score"]:
        delta = summary_b["qa_score"] - summary_a["qa_score"]
        differences.append(f"[info] QA score delta: {delta:+d}")
    if summary_b["svg_count"] != summary_a["svg_count"]:
        differences.append(
            f"[info] SVG count: baseline={summary_a['svg_count']}, grounded={summary_b['svg_count']}"
        )

    for d in differences:
        print(f"  {d}")

    if summary_b["exemplar_count"] == 0:
        print("\n  [WARN] Reference-grounded run found 0 exemplars.")
        print("         Either the library is empty for this topic, or the")
        print("         backfill is still running and relevant sources haven't")
        print("         been analyzed yet. Re-run after backfill completes.")
    else:
        print("\n  [PASS] Reference-grounded generation is functioning.")

    print()
    print("Open both HTML files side-by-side to compare the visual output:")
    print("  scripts/test_output_a_baseline.html")
    print("  scripts/test_output_b_grounded.html")


if __name__ == "__main__":
    main()
