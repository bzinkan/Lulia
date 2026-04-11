"""Full diagnostic of the Curriculum tab — upload, validate, generate, track."""
import json
import os
import sys

sys.path.insert(0, "/app")


def main():
    passed = 0
    failed = 0
    total = 0

    def check(name, fn):
        nonlocal passed, failed, total
        total += 1
        try:
            result = fn()
            print(f"  [OK] {name}: {result}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print("=" * 70)
    print("CURRICULUM TAB — FULL DIAGNOSTIC")
    print("=" * 70)

    # 1. Upload validate router
    print("\n── Upload Validation ──")
    def t1():
        from src.lms_agents.routers.upload_validate import router
        routes = [r.path for r in router.routes]
        return f"routes: {routes}"
    check("upload_validate router", t1)

    # 2. Format checks
    def t2():
        from src.lms_agents.routers.upload_validate import _check_json_standards_structure
        good = json.dumps({"standards": [{"code": "A", "description": "B"}]}).encode()
        bad = json.dumps({"data": [1, 2, 3]}).encode()
        assert _check_json_standards_structure(good) is not None, "good JSON rejected"
        assert _check_json_standards_structure(bad) is None, "bad JSON accepted"
        return "good JSON accepted, bad JSON rejected"
    check("JSON structure check", t2)

    def t3():
        from src.lms_agents.routers.upload_validate import _extract_text_preview
        txt = _extract_text_preview(b"Hello world test document", "test.txt")
        assert len(txt) > 0
        return f"{len(txt)} chars extracted from TXT"
    check("text extraction (TXT)", t3)

    # 3. Upload endpoints
    print("\n── Upload Endpoints ──")
    def t4():
        from src.lms_agents.routers.upload import router
        routes = [r.path for r in router.routes]
        return f"routes: {routes}"
    check("upload router", t4)

    def t5():
        from src.lms_agents.routers.upload import _haiku_extract_standards
        return "function exists"
    check("Haiku standards extraction fn", t5)

    def t6():
        from src.lms_agents.routers.upload import _extract_text_from_file
        txt = _extract_text_from_file(b"Test content for extraction", "test.txt")
        assert len(txt) > 0
        return f"{len(txt)} chars"
    check("text extraction for upload", t6)

    # 4. Database schema
    print("\n── Database Schema ──")
    def t7():
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'standard_activity_log'")
        assert cur.fetchone(), "table missing"
        cur.execute("SELECT COUNT(*) FROM standard_activity_log")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return f"exists, {count} rows"
    check("standard_activity_log table", t7)

    def t8():
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'curriculum_calendar'
            AND column_name IN ('unit_status', 'sort_order', 'generation_source')
        """)
        cols = sorted([r[0] for r in cur.fetchall()])
        cur.close()
        conn.close()
        assert len(cols) == 3, f"only {cols}"
        return f"all 3 present: {cols}"
    check("curriculum_calendar extended cols", t8)

    def t9():
        from src.lms_agents.tools.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'class_intelligence'
            AND column_name IN ('current_calendar_id', 'position_source', 'has_curriculum')
        """)
        cols = sorted([r[0] for r in cur.fetchall()])
        cur.close()
        conn.close()
        assert len(cols) == 3, f"only {cols}"
        return f"all 3 present: {cols}"
    check("class_intelligence extended cols", t9)

    # 5. Position tracking functions
    print("\n── Position Tracking ──")
    def t10():
        from src.lms_agents.tools.class_intelligence import (
            get_current_curriculum_context,
            get_standards_coverage,
            log_standard_activity,
            log_standards_batch,
            auto_advance_position,
            override_position,
        )
        return "all 6 functions importable"
    check("position tracking functions", t10)

    def t11():
        from src.lms_agents.tools.class_intelligence import log_standard_activity, get_standards_coverage
        from src.lms_agents.tools.db import get_connection
        # Log a test standard
        log_standard_activity(
            class_id="00000000-0000-0000-0000-000000000010",
            teacher_id="00000000-0000-0000-0000-000000000001",
            standard_code="DIAG.TEST.1",
            activity_type="diagnostic",
            source_id="diag",
        )
        # Verify it landed
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM standard_activity_log WHERE standard_code = 'DIAG.TEST.1'")
        count = cur.fetchone()[0]
        # Cleanup
        cur.execute("DELETE FROM standard_activity_log WHERE standard_code = 'DIAG.TEST.1'")
        conn.commit()
        cur.close()
        conn.close()
        assert count >= 1, f"expected >=1, got {count}"
        return f"logged and verified ({count} row), cleaned up"
    check("log + verify standard activity", t11)

    def t12():
        from src.lms_agents.tools.class_intelligence import get_standards_coverage
        cov = get_standards_coverage("00000000-0000-0000-0000-000000000010")
        return f"has_curriculum={cov.get('has_curriculum')}, total_covered={cov.get('total_covered')}"
    check("standards coverage view", t12)

    # 6. Curriculum generator
    print("\n── Curriculum Generator ──")
    def t13():
        from src.lms_agents.tools.curriculum_generator import _fetch_state_standards
        stds = _fetch_state_standards("OH", "4", "Math")
        return f"Ohio 4th Math: {len(stds)} standards"
    check("fetch Ohio standards", t13)

    def t14():
        from src.lms_agents.tools.curriculum_generator import _fetch_state_standards
        stds = _fetch_state_standards("TX", "6", "Science")
        return f"Texas 6th Science: {len(stds)} standards"
    check("fetch Texas standards", t14)

    def t15():
        from src.lms_agents.tools.curriculum_generator import generate_curriculum_from_standards
        return "function importable (not calling — would hit Sonnet API)"
    check("generate_curriculum_from_standards", t15)

    # 7. Teacher style analyzer
    print("\n── Teacher Style Analyzer ──")
    def t16():
        from src.lms_agents.tools.teacher_style_analyzer import get_teacher_style_profile
        profile = get_teacher_style_profile("00000000-0000-0000-0000-000000000001")
        if profile and profile.get("has_profile"):
            return (
                f"{profile['sources_analyzed']} sources, "
                f"primary={profile['primary_artifact_type']}, "
                f"avg_q={profile['question_count_avg']}, "
                f"features={profile['preferred_structural_features'][:3]}"
            )
        return "no profile (no analyzed materials)"
    check("teacher style profile", t16)

    # 8. Reference analyzer (auto-classify)
    print("\n── Auto-Classify on Upload ──")
    def t17():
        from src.lms_agents.tools.reference_analyzer import analyze_source, list_unanalyzed_sources
        unanalyzed = list_unanalyzed_sources(lanes=["materials", "curriculum"])
        return f"analyze_source importable, {len(unanalyzed)} unanalyzed materials/curriculum sources"
    check("reference analyzer", t17)

    # 9. Router registration
    print("\n── Router Registration ──")
    def t18():
        with open("src/lms_agents/main.py") as f:
            content = f.read()
        checks = {
            "upload": "upload.router" in content,
            "upload_validate": "upload_validate" in content,
            "class_intelligence": "class_intelligence" in content,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            raise AssertionError(f"missing: {missing}")
        return "upload, upload_validate, class_intelligence all registered"
    check("main.py router registration", t18)

    # 10. Frontend pages
    print("\n── Frontend ──")
    def t19():
        pages = {
            "/library": "dashboard/src/app/library/page.jsx",
            "/curriculum": "dashboard/src/app/curriculum/page.jsx",
        }
        results = []
        for route, path in pages.items():
            exists = os.path.exists(path)
            results.append(f"{route}={'OK' if exists else 'MISSING'}")
            if not exists:
                raise AssertionError(f"{path} missing")
        return ", ".join(results)
    check("frontend pages exist", t19)

    # 11. Pedagogy Director accepts curriculum_context
    def t20():
        import inspect
        from src.lms_agents.tools.pedagogy_director import generate_brief
        sig = inspect.signature(generate_brief)
        assert "curriculum_context" in sig.parameters, "missing curriculum_context param"
        return "generate_brief accepts curriculum_context param"
    check("pedagogy director curriculum_context", t20)

    # 12. Assignment crew wiring
    def t21():
        with open("src/lms_agents/crews/assignment_crew.py") as f:
            content = f.read()
        checks = {
            "log_standards_batch": "log_standards_batch" in content,
            "auto_advance_position": "auto_advance_position" in content,
            "curriculum_context": "curriculum_context" in content,
            "teacher_style": "teacher_style" in content,
            "textbook_grounding": "_fetch_textbook_grounding" in content,
        }
        missing = [k for k, v in checks.items() if not v]
        if missing:
            raise AssertionError(f"missing: {missing}")
        return "all 5 integrations wired"
    check("assignment crew wiring", t21)

    # Summary
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
