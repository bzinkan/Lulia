"""
K-2 Pedagogy Director — live end-to-end test against the Anthropic API.

Exercises the full grade-band expert pipeline with real Sonnet calls:

  Phase 1 — Cheap brief-only test for all 4 K-2 subjects (4 Sonnet calls).
            Validates routing, pack merging, and brief schema compliance.

  Phase 2 — Optional full Assignment Crew run for 1st grade math
            (~6 Sonnet calls). Validates Content Agent honors the brief
            and QA Agent enforces it. Pass --full to enable.

Usage:
    docker compose exec api python scripts/test_k2_pedagogy_live.py
    docker compose exec api python scripts/test_k2_pedagogy_live.py --full

Cost estimate:
    Phase 1 only:      ~$0.04 (4 brief calls)
    Phase 1 + Phase 2: ~$0.15 (4 brief + 6 crew calls)
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, "/app")

# Quiet down noisy loggers so the test report is readable
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("src.lms_agents.tools.pedagogy_director").setLevel(logging.INFO)
logging.getLogger("src.lms_agents.crews.assignment_crew").setLevel(logging.INFO)

from src.lms_agents.tools.pedagogy_director import generate_brief, load_pack


# ---------------------------------------------------------------------------
# Test fixtures — one per K-2 subject
# ---------------------------------------------------------------------------

K2_FIXTURES = [
    {
        "name": "1st grade math: adding within 20",
        "work_order": {
            "work_order_id": "TEST-K2-MATH-1",
            "grade_level": "1",
            "subject": "math",
            "output_template_id": "worksheet",
            "question_count": 10,
            "difficulty_distribution": {"easy": 4, "medium": 4, "hard": 2},
        },
        "curriculum_output": {
            "subject": "math",
            "grade_level": "1",
            "standards": [
                {
                    "code": "1.OA.6",
                    "description": "Add and subtract within 20, demonstrating fluency for addition and subtraction within 10.",
                }
            ],
        },
        "expected_pack_id": "k2_math",
        "must_ban_terms": ["regrouping", "algorithm", "variable"],
        "max_problems_cap": 8,
    },
    {
        "name": "Kindergarten ELA: short-a CVC words",
        "work_order": {
            "work_order_id": "TEST-K2-ELA-K",
            "grade_level": "K",
            "subject": "ela",
            "output_template_id": "worksheet",
            "question_count": 10,
            "difficulty_distribution": {"easy": 6, "medium": 4, "hard": 0},
        },
        "curriculum_output": {
            "subject": "ela",
            "grade_level": "K",
            "standards": [
                {
                    "code": "RF.K.2.D",
                    "description": "Isolate and pronounce the initial, medial vowel, and final sounds in three-phoneme (CVC) words.",
                }
            ],
        },
        "expected_pack_id": "k2_ela",
        "must_ban_terms": ["phoneme", "metaphor", "literary_device"],
        "max_problems_cap": 8,
    },
    {
        "name": "2nd grade science: solid/liquid/gas observable properties",
        "work_order": {
            "work_order_id": "TEST-K2-SCI-2",
            "grade_level": "2",
            "subject": "science",
            "output_template_id": "worksheet",
            "question_count": 10,
            "difficulty_distribution": {"easy": 4, "medium": 4, "hard": 2},
        },
        "curriculum_output": {
            "subject": "science",
            "grade_level": "2",
            "standards": [
                {
                    "code": "2-PS1-1",
                    "description": "Plan and conduct an investigation to describe and classify different kinds of materials by their observable properties.",
                }
            ],
        },
        "expected_pack_id": "k2_science",
        "must_ban_terms": ["hypothesis", "molecule", "atom", "ecosystem"],
        "max_problems_cap": 8,
    },
    {
        "name": "1st grade social studies: needs vs wants",
        "work_order": {
            "work_order_id": "TEST-K2-SOC-1",
            "grade_level": "1",
            "subject": "social studies",
            "output_template_id": "worksheet",
            "question_count": 10,
            "difficulty_distribution": {"easy": 5, "medium": 5, "hard": 0},
        },
        "curriculum_output": {
            "subject": "social studies",
            "grade_level": "1",
            "standards": [
                {
                    "code": "C3.D2.Eco.1.K-2",
                    "description": "Explain how scarcity necessitates decision making.",
                }
            ],
        },
        "expected_pack_id": "k2_social",
        "must_ban_terms": ["constitution", "amendment", "legislature", "ideology"],
        "max_problems_cap": 8,
    },
]


# ---------------------------------------------------------------------------
# Brief validators
# ---------------------------------------------------------------------------

REQUIRED_BRIEF_SECTIONS = [
    "developmental_constraints",
    "layout_directives",
    "template_recommendation",
    "content_rules",
    "scaffolds_required",
    "assessment_modes_preferred",
    "lesson_plan_spec",
    "video_spec",
    "pedagogy_notes",
]


def validate_brief(brief: dict, fixture: dict) -> list[str]:
    """Return a list of human-readable failures. Empty list = pass."""
    failures = []

    if not brief:
        return ["brief is None — director failed to generate"]

    # Pack id must match the expected k2_* pack
    if brief.get("_pack_id") != fixture["expected_pack_id"]:
        failures.append(
            f"_pack_id mismatch: expected {fixture['expected_pack_id']}, got {brief.get('_pack_id')}"
        )

    # Required sections present
    for section in REQUIRED_BRIEF_SECTIONS:
        if section not in brief:
            failures.append(f"missing required section: {section}")

    # K-2 specific layout sanity checks
    layout = brief.get("layout_directives", {}) or {}
    if layout.get("min_font_size_pt", 0) < 18:
        failures.append(
            f"min_font_size_pt is {layout.get('min_font_size_pt')} — too small for K-2 (need >=18, base says 22)"
        )
    if layout.get("max_problems_per_page", 99) > fixture["max_problems_cap"]:
        failures.append(
            f"max_problems_per_page is {layout.get('max_problems_per_page')} — exceeds K-2 cap of {fixture['max_problems_cap']}"
        )
    if layout.get("mascot_required") is False:
        failures.append("mascot_required=False — K-2 base requires Lulings mascot")

    # Developmental constraints
    dev = brief.get("developmental_constraints", {}) or {}
    lex = dev.get("max_reading_level_lexile")
    if lex is not None and lex > 600:
        failures.append(f"max_reading_level_lexile={lex} too high for K-2 (need <=600)")
    span = dev.get("attention_span_min")
    if span is not None and span > 15:
        failures.append(f"attention_span_min={span} too long for K-2 (need <=15)")

    # Vocabulary tier caps — K-2 should be Tier 1 dominant
    rules = brief.get("content_rules", {}) or {}
    tiers = rules.get("vocabulary_tier_caps", {}) or {}
    t1 = tiers.get("tier_1_pct", 0)
    if t1 < 70:
        failures.append(f"tier_1_pct={t1}% — K-2 must be >=70% Tier 1")

    # Banned-term enforcement
    banned = set(rules.get("banned_terms", []) or [])
    for term in fixture["must_ban_terms"]:
        if term not in banned:
            failures.append(f"banned_terms missing required term: {term}")

    # Video spec K-2 sanity
    vspec = brief.get("video_spec", {}) or {}
    if vspec.get("length_max", 0) > 5:
        failures.append(
            f"video length_max={vspec.get('length_max')} too long for K-2 (need <=5)"
        )
    if vspec.get("mascot_required") is False:
        failures.append("video mascot_required=False — K-2 needs mascot")

    # Lesson plan duration K-2 sanity
    lp = brief.get("lesson_plan_spec", {}) or {}
    if lp.get("total_duration_min", 0) > 60:
        failures.append(
            f"lesson total_duration_min={lp.get('total_duration_min')} too long for K-2 (need <=60)"
        )

    # Template recommendation must be present
    tr = brief.get("template_recommendation", {}) or {}
    if not tr.get("primary"):
        failures.append("template_recommendation.primary is empty")

    return failures


# ---------------------------------------------------------------------------
# Phase 1 — Brief generation only
# ---------------------------------------------------------------------------

def run_phase_1() -> bool:
    print("=" * 70)
    print("PHASE 1: Pedagogy Director — live brief generation for all 4 K-2 subjects")
    print("=" * 70)

    all_passed = True

    for fixture in K2_FIXTURES:
        print(f"\n--- {fixture['name']} ---")

        # Sanity: pack must exist before we even call the LLM
        pack = load_pack(fixture["work_order"]["grade_level"], fixture["work_order"]["subject"])
        if pack is None:
            print(f"  [FAIL] pack not found for this fixture")
            all_passed = False
            continue
        print(f"  pack loaded: {pack['_pack_id']}")

        # Generate the brief via the live API
        brief = generate_brief(
            work_order=fixture["work_order"],
            curriculum_output=fixture["curriculum_output"],
            kb_chunks=None,
            class_intel_prompt=None,
        )

        if brief is None:
            print(f"  [FAIL] generate_brief returned None")
            all_passed = False
            continue

        failures = validate_brief(brief, fixture)
        if failures:
            print(f"  [FAIL] {len(failures)} validation failure(s):")
            for f in failures:
                print(f"    - {f}")
            all_passed = False
        else:
            tr = brief.get("template_recommendation", {})
            layout = brief.get("layout_directives", {})
            vspec = brief.get("video_spec", {})
            lp = brief.get("lesson_plan_spec", {})
            print(f"  [PASS]")
            print(f"    template          = {tr.get('primary')}")
            print(f"    max_problems      = {layout.get('max_problems_per_page')}")
            print(f"    min_font_size_pt  = {layout.get('min_font_size_pt')}")
            print(f"    mascot_required   = {layout.get('mascot_required')}")
            print(f"    video length      = {vspec.get('length_min')}-{vspec.get('length_max')} min")
            print(f"    lesson duration   = {lp.get('total_duration_min')} min")
            print(f"    tier_1_pct        = {brief.get('content_rules', {}).get('vocabulary_tier_caps', {}).get('tier_1_pct')}%")
            notes = brief.get("pedagogy_notes", "")
            if notes:
                print(f"    pedagogy_notes    = {notes[:150]}{'...' if len(notes) > 150 else ''}")

    print("\n" + "=" * 70)
    print(f"PHASE 1 RESULT: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 70)
    return all_passed


# ---------------------------------------------------------------------------
# Phase 2 — Full Assignment Crew run for 1st grade math
# ---------------------------------------------------------------------------

def run_phase_2() -> bool:
    print("\n" + "=" * 70)
    print("PHASE 2: Full Assignment Crew — 1st grade math worksheet")
    print("=" * 70)
    print("This invokes Curriculum -> Director -> Content -> Rubric -> QA -> Format")
    print("Standards lookup will hit Postgres; content gen will hit Sonnet.\n")

    from src.lms_agents.crews.assignment_crew import run_assignment_crew

    work_order = {
        "work_order_id": "TEST-K2-FULL-1",
        # No class_id — skips storage and class intelligence; tests pure crew flow
        "teacher_id": "00000000-0000-0000-0000-000000000001",
        "grade_level": "1",
        "subject": "math",
        "output_template_id": "worksheet",
        "output_format": "html",
        "design_theme": "modern_clean",
        "standards_ids": ["1.OA.6"],
        "question_count": 10,
        "difficulty_distribution": {"easy": 4, "medium": 4, "hard": 2},
        "has_kb_coverage": False,
    }

    try:
        result = run_assignment_crew(work_order)
    except Exception as e:
        print(f"  [FAIL] crew raised: {e}")
        return False

    failures = []

    # Brief was generated and tagged
    brief = result.get("pedagogy_brief")
    pack_id = result.get("pedagogy_pack_id")
    if not brief:
        failures.append("result.pedagogy_brief is missing — director did not run")
    if pack_id != "k2_math":
        failures.append(f"pedagogy_pack_id is {pack_id}, expected k2_math")

    # Question count was capped at the brief's max_problems_per_page (<=8 for K-2)
    qcount = result.get("question_count", 0)
    if qcount > 8:
        failures.append(
            f"question_count={qcount} exceeds K-2 cap of 8 — Content Agent ignored brief"
        )

    # QA score should be reasonable
    qa_score = result.get("qa_score", 0)
    if qa_score < 60:
        failures.append(f"qa_score={qa_score} too low — content quality issue")

    # Content checks — scan the generated questions for K-2 banned terms
    content = result.get("content", {}) or {}
    questions = content.get("questions", []) or []
    if not questions:
        failures.append("no questions generated")
    else:
        all_text = " ".join(
            (q.get("question_text", "") or "") + " " + (q.get("answer", "") or "")
            for q in questions
        ).lower()
        for banned_term in ["regrouping", "algorithm", "variable", "numerator"]:
            if banned_term in all_text:
                failures.append(f"banned K-2 math term '{banned_term}' appeared in generated content")

        # Structured visuals check — K-2 math brief should produce visuals on questions
        import re
        bracket_re = re.compile(
            r"\[(?:image|picture|diagram|illustration|graphic|visual|drawing|figure|photo|chart)[^\]]*\]",
            re.IGNORECASE,
        )
        bracket_hits = []
        visual_count = 0
        visual_types_seen = set()
        for q in questions:
            qtext = q.get("question_text", "") or ""
            if bracket_re.search(qtext):
                bracket_hits.append(q.get("question_number", "?"))
            v = q.get("visual")
            if v and isinstance(v, dict) and v.get("type"):
                visual_count += 1
                visual_types_seen.add(v.get("type"))

        if bracket_hits:
            failures.append(
                f"bracketed image references in questions {bracket_hits} — "
                f"structured visuals fix not honored"
            )

        # K-2 math brief mandates every_question_needs_image=True,
        # so every question should have a structured visual.
        if visual_count < len(questions) // 2:
            failures.append(
                f"only {visual_count}/{len(questions)} questions have structured visuals — "
                f"expected most questions to have visual objects for K-2 math"
            )

        # Render the visuals and confirm SVG output appears in the student HTML
        student_html = result.get("student_html", "")
        svg_count = student_html.count("<svg")
        if visual_count > 0 and svg_count == 0:
            failures.append(
                f"content had {visual_count} structured visuals but student_html has 0 <svg> elements"
            )

    # Report
    print(f"\n  assignment_id   = {result.get('assignment_id')}")
    print(f"  title           = {result.get('title')}")
    print(f"  pack_id         = {pack_id}")
    print(f"  question_count  = {qcount} (cap is 8 for K-2)")
    print(f"  qa_score        = {qa_score}")
    print(f"  qa_approved     = {result.get('qa_approved')}")
    if questions:
        print(f"\n  Sample question (first):")
        q = questions[0]
        print(f"    Q: {q.get('question_text', '(empty)')}")
        print(f"    A: {q.get('answer', '(empty)')}")
        print(f"    standard: {q.get('standard_code')}")
        v = q.get("visual")
        if v:
            print(f"    visual: {v}")
        else:
            print(f"    visual: (none)")

    # Structured visuals summary
    print(f"\n  Structured visuals:")
    print(f"    questions with visuals: {visual_count}/{len(questions)}")
    print(f"    visual types used:      {sorted(visual_types_seen) if visual_types_seen else '(none)'}")
    print(f"    bracketed refs found:   {len(bracket_hits)}")
    print(f"    <svg> tags in HTML:     {result.get('student_html', '').count('<svg')}")
    if brief:
        tr = brief.get("template_recommendation", {})
        print(f"\n  Brief template recommendation: {tr.get('primary')} ({tr.get('rationale', '')[:100]})")

    # Print the QA report so we can see what the QA agent flagged
    qa_report = result.get("qa_report", {}) or {}
    print(f"\n  QA report:")
    print(f"    approved = {qa_report.get('approved')}")
    print(f"    score    = {qa_report.get('score')}")
    checks = qa_report.get("checks", {}) or {}
    for check_name, check in checks.items():
        if isinstance(check, dict):
            status = "PASS" if check.get("pass") else "FAIL"
            note = check.get("notes", "")[:100]
            print(f"    [{status}] {check_name}: {note}")
    issues = qa_report.get("issues", []) or []
    if issues:
        print(f"  Issues flagged:")
        for issue in issues[:5]:
            print(f"    - {issue}")

    if failures:
        print(f"\n  [FAIL] {len(failures)} test issue(s):")
        for f in failures:
            print(f"    - {f}")
        result_status = False
    else:
        print(f"\n  [PASS]")
        result_status = True

    print("\n" + "=" * 70)
    print(f"PHASE 2 RESULT: {'PASS' if result_status else 'FAIL'}")
    print("=" * 70)
    return result_status


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also run Phase 2 (full Assignment Crew, ~$0.10 extra)",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set in the environment.")
        sys.exit(2)

    p1 = run_phase_1()
    p2 = True
    if args.full:
        p2 = run_phase_2()

    print()
    if p1 and p2:
        print(">>> ALL TESTS PASSED <<<")
        sys.exit(0)
    else:
        print(">>> TESTS FAILED <<<")
        sys.exit(1)


if __name__ == "__main__":
    main()
