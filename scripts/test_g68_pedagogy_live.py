"""
Grade 6-8 Pedagogy Director — live brief generation test against the live API.

Phase 1 only: generates one brief per 6-8 subject with real Sonnet calls.

Usage:
    docker compose exec api python scripts/test_g68_pedagogy_live.py

Cost: ~$0.04 (4 Sonnet calls)
"""
import logging
import os
import sys

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("src.lms_agents.tools.pedagogy_director").setLevel(logging.INFO)

from src.lms_agents.tools.pedagogy_director import generate_brief, load_pack


G68_FIXTURES = [
    {
        "name": "7th grade math: solving two-step equations",
        "work_order": {
            "work_order_id": "TEST-G68-MATH-7",
            "grade_level": "7",
            "subject": "math",
            "output_template_id": "worksheet",
            "question_count": 15,
            "difficulty_distribution": {"easy": 4, "medium": 7, "hard": 4},
        },
        "curriculum_output": {
            "subject": "math",
            "grade_level": "7",
            "standards": [
                {
                    "code": "7.EE.4",
                    "description": "Use variables to represent quantities in a real-world or mathematical problem, and construct simple equations and inequalities to solve problems by reasoning about the quantities.",
                }
            ],
        },
        "expected_pack_id": "g68_math",
        "must_ban_terms": ["logarithm", "sine", "derivative"],
        "max_problems_cap": 24,
    },
    {
        "name": "8th grade ELA: argumentative writing with counterclaim",
        "work_order": {
            "work_order_id": "TEST-G68-ELA-8",
            "grade_level": "8",
            "subject": "ela",
            "output_template_id": "writing_prompt",
            "question_count": 5,
            "difficulty_distribution": {"easy": 1, "medium": 3, "hard": 1},
        },
        "curriculum_output": {
            "subject": "ela",
            "grade_level": "8",
            "standards": [
                {
                    "code": "W.8.1",
                    "description": "Write arguments to support claims with clear reasons and relevant evidence; introduce claim(s), acknowledge and distinguish the claim(s) from alternate or opposing claims.",
                }
            ],
        },
        "expected_pack_id": "g68_ela",
        "must_ban_terms": ["literary_theory", "deconstruction"],
        "max_problems_cap": 24,
    },
    {
        "name": "6th grade science: cell structure and function",
        "work_order": {
            "work_order_id": "TEST-G68-SCI-6",
            "grade_level": "6",
            "subject": "science",
            "output_template_id": "lab_activity",
            "question_count": 8,
            "difficulty_distribution": {"easy": 3, "medium": 4, "hard": 1},
        },
        "curriculum_output": {
            "subject": "science",
            "grade_level": "6",
            "standards": [
                {
                    "code": "MS-LS1-2",
                    "description": "Develop and use a model to describe the function of a cell as a whole and ways the parts of cells contribute to the function.",
                }
            ],
        },
        "expected_pack_id": "g68_science",
        "must_ban_terms": ["quantum mechanics", "string theory"],
        "max_problems_cap": 24,
    },
    {
        "name": "8th grade social studies: causes of the American Revolution",
        "work_order": {
            "work_order_id": "TEST-G68-SOC-8",
            "grade_level": "8",
            "subject": "social studies",
            "output_template_id": "primary_source_analysis",
            "question_count": 6,
            "difficulty_distribution": {"easy": 2, "medium": 3, "hard": 1},
        },
        "curriculum_output": {
            "subject": "social studies",
            "grade_level": "8",
            "standards": [
                {
                    "code": "USH.8.1",
                    "description": "Analyze the political, economic, and ideological causes of the American Revolution from multiple perspectives.",
                }
            ],
        },
        "expected_pack_id": "g68_social",
        "must_ban_terms": ["neoliberalism", "marxist_critique_advanced"],
        "max_problems_cap": 24,
    },
]


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
    """Return human-readable failures. Empty list = pass."""
    failures = []
    if not brief:
        return ["brief is None — director failed"]

    if brief.get("_pack_id") != fixture["expected_pack_id"]:
        failures.append(
            f"_pack_id mismatch: expected {fixture['expected_pack_id']}, got {brief.get('_pack_id')}"
        )

    for section in REQUIRED_BRIEF_SECTIONS:
        if section not in brief:
            failures.append(f"missing required section: {section}")

    layout = brief.get("layout_directives", {}) or {}
    fs = layout.get("min_font_size_pt")
    if fs is not None and (fs < 10 or fs > 14):
        failures.append(f"min_font_size_pt={fs} out of 6-8 range (10-14)")
    mp = layout.get("max_problems_per_page")
    if mp is not None and mp > fixture["max_problems_cap"]:
        failures.append(f"max_problems_per_page={mp} exceeds 6-8 cap {fixture['max_problems_cap']}")
    # Mascot should NOT be required for 6-8 (developmentally inappropriate)
    if layout.get("mascot_required") is True:
        failures.append("mascot_required=True — middle schoolers don't want mascots")

    dev = brief.get("developmental_constraints", {}) or {}
    lex = dev.get("max_reading_level_lexile")
    if lex is not None and (lex < 800 or lex > 1300):
        failures.append(f"max_reading_level_lexile={lex} out of 6-8 range (800-1300)")
    span = dev.get("attention_span_min")
    if span is not None and (span < 20 or span > 50):
        failures.append(f"attention_span_min={span} out of 6-8 range (20-50)")

    # 6-8 should have heavy academic vocab (T2 + T3 combined >= 50%)
    rules = brief.get("content_rules", {}) or {}
    tiers = rules.get("vocabulary_tier_caps", {}) or {}
    t1 = tiers.get("tier_1_pct", 100)
    if t1 > 55:
        failures.append(f"tier_1_pct={t1}% — 6-8 needs <55% Tier 1 (more academic vocab)")

    banned = set(rules.get("banned_terms", []) or [])
    for term in fixture["must_ban_terms"]:
        if term not in banned:
            failures.append(f"banned_terms missing required term: {term}")

    vspec = brief.get("video_spec", {}) or {}
    lmax = vspec.get("length_max", 0)
    if lmax > 12:
        failures.append(f"video length_max={lmax} too long for 6-8 (need <=12)")
    if lmax < 4:
        failures.append(f"video length_max={lmax} too short for 6-8 (need >=4)")

    lp = brief.get("lesson_plan_spec", {}) or {}
    dur = lp.get("total_duration_min", 0)
    if dur > 100:
        failures.append(f"lesson total_duration_min={dur} too long for 6-8")
    if dur < 40:
        failures.append(f"lesson total_duration_min={dur} too short for 6-8")

    tr = brief.get("template_recommendation", {}) or {}
    if not tr.get("primary"):
        failures.append("template_recommendation.primary is empty")

    return failures


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(2)

    print("=" * 70)
    print("6-8 PEDAGOGY DIRECTOR — live brief test (4 subjects)")
    print("=" * 70)

    all_passed = True

    for fixture in G68_FIXTURES:
        print(f"\n--- {fixture['name']} ---")

        pack = load_pack(fixture["work_order"]["grade_level"], fixture["work_order"]["subject"])
        if pack is None:
            print("  [FAIL] pack not found")
            all_passed = False
            continue
        print(f"  pack loaded: {pack['_pack_id']}")

        brief = generate_brief(
            work_order=fixture["work_order"],
            curriculum_output=fixture["curriculum_output"],
            kb_chunks=None,
            class_intel_prompt=None,
        )

        if brief is None:
            print("  [FAIL] generate_brief returned None")
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
            tiers = brief.get("content_rules", {}).get("vocabulary_tier_caps", {})
            print(f"  [PASS]")
            print(f"    template          = {tr.get('primary')}")
            print(f"    max_problems      = {layout.get('max_problems_per_page')}")
            print(f"    min_font_size_pt  = {layout.get('min_font_size_pt')}")
            print(f"    mascot_required   = {layout.get('mascot_required')}")
            print(f"    video length      = {vspec.get('length_min')}-{vspec.get('length_max')} min")
            print(f"    lesson duration   = {lp.get('total_duration_min')} min")
            print(f"    vocab T1/T2/T3    = {tiers.get('tier_1_pct')}/{tiers.get('tier_2_pct')}/{tiers.get('tier_3_pct')}%")
            notes = brief.get("pedagogy_notes", "")
            if notes:
                print(f"    pedagogy_notes    = {notes[:170]}{'...' if len(notes) > 170 else ''}")

    print("\n" + "=" * 70)
    print(f"6-8 LIVE TEST: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 70)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
