"""
Grade 3-5 Pedagogy Director — live brief generation test against the live API.

Phase 1 only (cheap): generates one brief per K-2 subject with real Sonnet
calls and validates the result against developmental constraints.

Usage:
    docker compose exec api python scripts/test_g35_pedagogy_live.py

Cost: ~$0.04 (4 Sonnet calls)
"""
import logging
import os
import sys

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("src.lms_agents.tools.pedagogy_director").setLevel(logging.INFO)

from src.lms_agents.tools.pedagogy_director import generate_brief, load_pack


G35_FIXTURES = [
    {
        "name": "4th grade math: multi-digit multiplication strategies",
        "work_order": {
            "work_order_id": "TEST-G35-MATH-4",
            "grade_level": "4",
            "subject": "math",
            "output_template_id": "worksheet",
            "question_count": 12,
            "difficulty_distribution": {"easy": 4, "medium": 5, "hard": 3},
        },
        "curriculum_output": {
            "subject": "math",
            "grade_level": "4",
            "standards": [
                {
                    "code": "4.NBT.5",
                    "description": "Multiply a whole number of up to four digits by a one-digit whole number, and multiply two two-digit numbers, using strategies based on place value and the properties of operations.",
                }
            ],
        },
        "expected_pack_id": "g35_math",
        "must_ban_terms": ["variable", "ratio", "percent"],
        "max_problems_cap": 16,
        "min_problems_floor": 5,
    },
    {
        "name": "5th grade ELA: theme from details in literary text",
        "work_order": {
            "work_order_id": "TEST-G35-ELA-5",
            "grade_level": "5",
            "subject": "ela",
            "output_template_id": "reading_comprehension",
            "question_count": 8,
            "difficulty_distribution": {"easy": 3, "medium": 4, "hard": 1},
        },
        "curriculum_output": {
            "subject": "ela",
            "grade_level": "5",
            "standards": [
                {
                    "code": "RL.5.2",
                    "description": "Determine a theme of a story, drama, or poem from details in the text, including how characters in a story or drama respond to challenges; summarize the text.",
                }
            ],
        },
        "expected_pack_id": "g35_ela",
        "must_ban_terms": ["thesis statement", "counterclaim", "rhetorical strategy"],
        "max_problems_cap": 16,
        "min_problems_floor": 1,  # passages allow as few as 1
    },
    {
        "name": "3rd grade science: forces and motion",
        "work_order": {
            "work_order_id": "TEST-G35-SCI-3",
            "grade_level": "3",
            "subject": "science",
            "output_template_id": "lab_activity",
            "question_count": 8,
            "difficulty_distribution": {"easy": 3, "medium": 4, "hard": 1},
        },
        "curriculum_output": {
            "subject": "science",
            "grade_level": "3",
            "standards": [
                {
                    "code": "3-PS2-1",
                    "description": "Plan and conduct an investigation to provide evidence of the effects of balanced and unbalanced forces on the motion of an object.",
                }
            ],
        },
        "expected_pack_id": "g35_science",
        "must_ban_terms": ["molecule", "atom", "covalent_bond"],
        "max_problems_cap": 16,
        "min_problems_floor": 1,
    },
    {
        "name": "5th grade social studies: branches of federal government",
        "work_order": {
            "work_order_id": "TEST-G35-SOC-5",
            "grade_level": "5",
            "subject": "social studies",
            "output_template_id": "graphic_organizer",
            "question_count": 6,
            "difficulty_distribution": {"easy": 2, "medium": 3, "hard": 1},
        },
        "curriculum_output": {
            "subject": "social studies",
            "grade_level": "5",
            "standards": [
                {
                    "code": "C3.D2.Civ.4.3-5",
                    "description": "Explain how groups of people make rules to create responsibilities and protect freedoms.",
                }
            ],
        },
        "expected_pack_id": "g35_social",
        "must_ban_terms": ["ideology", "geopolitics", "fascism"],
        "max_problems_cap": 16,
        "min_problems_floor": 1,
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
    # 3-5 layout sanity — font 14pt+, max 16/page
    fs = layout.get("min_font_size_pt")
    if fs is not None and (fs < 12 or fs > 16):
        failures.append(f"min_font_size_pt={fs} out of 3-5 range (12-16)")
    mp = layout.get("max_problems_per_page")
    if mp is not None and mp > fixture["max_problems_cap"]:
        failures.append(f"max_problems_per_page={mp} exceeds 3-5 cap {fixture['max_problems_cap']}")

    # 3-5 developmental — Lexile up to 1010 by end of 5th
    dev = brief.get("developmental_constraints", {}) or {}
    lex = dev.get("max_reading_level_lexile")
    if lex is not None and (lex < 400 or lex > 1100):
        failures.append(f"max_reading_level_lexile={lex} out of 3-5 range (400-1100)")
    span = dev.get("attention_span_min")
    if span is not None and (span < 10 or span > 30):
        failures.append(f"attention_span_min={span} out of 3-5 range (10-30)")

    # Vocabulary — 3-5 should have substantial Tier 2 (academic language)
    rules = brief.get("content_rules", {}) or {}
    tiers = rules.get("vocabulary_tier_caps", {}) or {}
    t2 = tiers.get("tier_2_pct", 0)
    if t2 < 15:
        failures.append(f"tier_2_pct={t2}% — 3-5 needs strong academic vocab focus (>=15%)")

    # Banned terms enforced
    banned = set(rules.get("banned_terms", []) or [])
    for term in fixture["must_ban_terms"]:
        if term not in banned:
            failures.append(f"banned_terms missing required term: {term}")

    # Video spec — 3-5 is 4-8 min
    vspec = brief.get("video_spec", {}) or {}
    lmax = vspec.get("length_max", 0)
    if lmax > 10:
        failures.append(f"video length_max={lmax} too long for 3-5 (need <=10)")

    # Lesson plan duration — 3-5 typically 45-90 min
    lp = brief.get("lesson_plan_spec", {}) or {}
    dur = lp.get("total_duration_min", 0)
    if dur > 100:
        failures.append(f"lesson total_duration_min={dur} too long for 3-5")

    tr = brief.get("template_recommendation", {}) or {}
    if not tr.get("primary"):
        failures.append("template_recommendation.primary is empty")

    return failures


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(2)

    print("=" * 70)
    print("3-5 PEDAGOGY DIRECTOR — live brief test (4 subjects)")
    print("=" * 70)

    all_passed = True

    for fixture in G35_FIXTURES:
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
    print(f"3-5 LIVE TEST: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 70)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
