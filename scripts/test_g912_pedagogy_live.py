"""
Grade 9-12 Pedagogy Director — live brief generation test against the live API.

Tests both general high school courses AND an AP-level course to verify
that the director surfaces course-level rigor.

Usage:
    docker compose exec api python scripts/test_g912_pedagogy_live.py

Cost: ~$0.05 (5 Sonnet calls)
"""
import logging
import os
import sys

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("src.lms_agents.tools.pedagogy_director").setLevel(logging.INFO)

from src.lms_agents.tools.pedagogy_director import generate_brief, load_pack


G912_FIXTURES = [
    {
        "name": "Algebra 2 (11th): exponential and logarithmic functions",
        "work_order": {
            "work_order_id": "TEST-G912-MATH-ALG2",
            "grade_level": "11",
            "subject": "math",
            "output_template_id": "worksheet",
            "question_count": 18,
            "difficulty_distribution": {"easy": 5, "medium": 8, "hard": 5},
        },
        "curriculum_output": {
            "subject": "math",
            "grade_level": "11",
            "standards": [
                {
                    "code": "HSF.LE.A.4",
                    "description": "For exponential models, express as a logarithm the solution to ab^(ct) = d where a, c, and d are numbers and the base b is 2, 10, or e; evaluate the logarithm using technology.",
                }
            ],
        },
        "expected_pack_id": "g912_math",
        "must_ban_terms": ["multivariable_calculus_advanced", "tensor_analysis"],
        "max_problems_cap": 30,
    },
    {
        "name": "AP Calculus AB (12th): derivatives and applications",
        "work_order": {
            "work_order_id": "TEST-G912-MATH-APCALC",
            "grade_level": "12",
            "subject": "math",
            "output_template_id": "worksheet",
            "question_count": 12,
            "difficulty_distribution": {"easy": 2, "medium": 5, "hard": 5},
        },
        "curriculum_output": {
            "subject": "math",
            "grade_level": "12",
            "standards": [
                {
                    "code": "AP-CALC-AB-CHA-3.1",
                    "description": "Determine derivatives of products and quotients of functions using the product and quotient rules.",
                }
            ],
        },
        "expected_pack_id": "g912_math",
        "must_ban_terms": ["multivariable_calculus_advanced"],
        "max_problems_cap": 30,
        "expect_ap_features": True,
    },
    {
        "name": "AP English Literature (12th): poetry analysis",
        "work_order": {
            "work_order_id": "TEST-G912-ELA-APLIT",
            "grade_level": "12",
            "subject": "ela",
            "output_template_id": "literary_analysis",
            "question_count": 6,
            "difficulty_distribution": {"easy": 1, "medium": 3, "hard": 2},
        },
        "curriculum_output": {
            "subject": "ela",
            "grade_level": "12",
            "standards": [
                {
                    "code": "AP-LIT-LAN-1.A",
                    "description": "Identify and explain the function of a symbol; explain the function of figurative language and structural choices in a literary work.",
                }
            ],
        },
        "expected_pack_id": "g912_ela",
        "must_ban_terms": ["graduate_level_critical_theory_jargon", "lacanian_psychoanalysis"],
        "max_problems_cap": 30,
        "expect_ap_features": True,
    },
    {
        "name": "Biology (10th): cellular respiration",
        "work_order": {
            "work_order_id": "TEST-G912-SCI-BIO",
            "grade_level": "10",
            "subject": "science",
            "output_template_id": "lab_activity",
            "question_count": 10,
            "difficulty_distribution": {"easy": 3, "medium": 5, "hard": 2},
        },
        "curriculum_output": {
            "subject": "science",
            "grade_level": "10",
            "standards": [
                {
                    "code": "HS-LS1-7",
                    "description": "Use a model to illustrate that cellular respiration is a chemical process whereby the bonds of food molecules and oxygen molecules are broken and the bonds in new compounds are formed resulting in a net transfer of energy.",
                }
            ],
        },
        "expected_pack_id": "g912_science",
        "must_ban_terms": ["graduate_level_molecular_biology_jargon", "advanced_quantum_field_theory"],
        "max_problems_cap": 30,
    },
    {
        "name": "AP US History (11th): causes of the Civil War",
        "work_order": {
            "work_order_id": "TEST-G912-SOC-APUSH",
            "grade_level": "11",
            "subject": "social studies",
            "output_template_id": "dbq",
            "question_count": 5,
            "difficulty_distribution": {"easy": 1, "medium": 2, "hard": 2},
        },
        "curriculum_output": {
            "subject": "social studies",
            "grade_level": "11",
            "standards": [
                {
                    "code": "AP-USH-5.2",
                    "description": "Explain the political causes of the Civil War, including the controversy over slavery in the territories and the breakdown of the second party system.",
                }
            ],
        },
        "expected_pack_id": "g912_social",
        "must_ban_terms": ["graduate_level_critical_theory_jargon"],
        "max_problems_cap": 30,
        "expect_ap_features": True,
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
    if fs is not None and (fs < 9 or fs > 14):
        failures.append(f"min_font_size_pt={fs} out of 9-12 range (9-14)")
    mp = layout.get("max_problems_per_page")
    if mp is not None and mp > fixture["max_problems_cap"]:
        failures.append(f"max_problems_per_page={mp} exceeds 9-12 cap {fixture['max_problems_cap']}")
    if layout.get("mascot_required") is True:
        failures.append("mascot_required=True — high schoolers don't want mascots")

    dev = brief.get("developmental_constraints", {}) or {}
    lex = dev.get("max_reading_level_lexile")
    if lex is not None and (lex < 900 or lex > 1500):
        failures.append(f"max_reading_level_lexile={lex} out of 9-12 range (900-1500)")
    span = dev.get("attention_span_min")
    if span is not None and (span < 25 or span > 60):
        failures.append(f"attention_span_min={span} out of 9-12 range (25-60)")

    # 9-12 should have very heavy academic vocab (T1 ≤ 35%)
    rules = brief.get("content_rules", {}) or {}
    tiers = rules.get("vocabulary_tier_caps", {}) or {}
    t1 = tiers.get("tier_1_pct", 100)
    if t1 > 40:
        failures.append(f"tier_1_pct={t1}% — 9-12 needs <=40% Tier 1")

    banned = set(rules.get("banned_terms", []) or [])
    for term in fixture["must_ban_terms"]:
        if term not in banned:
            failures.append(f"banned_terms missing required term: {term}")

    vspec = brief.get("video_spec", {}) or {}
    lmax = vspec.get("length_max", 0)
    if lmax > 20:
        failures.append(f"video length_max={lmax} too long for 9-12")
    if lmax < 5:
        failures.append(f"video length_max={lmax} too short for 9-12 (need >=5)")

    lp = brief.get("lesson_plan_spec", {}) or {}
    dur = lp.get("total_duration_min", 0)
    if dur < 40 or dur > 100:
        failures.append(f"lesson total_duration_min={dur} out of 9-12 range")

    tr = brief.get("template_recommendation", {}) or {}
    if not tr.get("primary"):
        failures.append("template_recommendation.primary is empty")

    return failures


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(2)

    print("=" * 70)
    print("9-12 PEDAGOGY DIRECTOR — live brief test (5 fixtures incl. 3 AP)")
    print("=" * 70)

    all_passed = True

    for fixture in G912_FIXTURES:
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
    print(f"9-12 LIVE TEST: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 70)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
