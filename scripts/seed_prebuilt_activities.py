"""Seed Git-backed prebuilt activity JSON into Postgres.

Examples:
  python scripts/seed_prebuilt_activities.py --dry-run
  python scripts/seed_prebuilt_activities.py --course Biology --status published
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if Path("/app").exists():
    sys.path.insert(0, "/app")

from psycopg2.extras import Json

from src.lms_agents.tools.db import get_connection
from src.lms_agents.tools.prebuilt_activity_schema import STATUS_VALUES, iter_seed_rows, load_course_file


DATA_ROOT = ROOT / "data" / "prebuilt_activities"


UPSERT_SQL = """
INSERT INTO prebuilt_activities (
    activity_id, grade_level, grade_band, subject, course,
    unit_number, unit_title, lesson_number, lesson_title,
    activity_type, standards, visual_surface, content, checks,
    reflection_prompt, tags, difficulty, estimated_minutes,
    status, source, version
) VALUES (
    %(activity_id)s, %(grade_level)s, %(grade_band)s, %(subject)s, %(course)s,
    %(unit_number)s, %(unit_title)s, %(lesson_number)s, %(lesson_title)s,
    %(activity_type)s, %(standards)s, %(visual_surface)s, %(content)s, %(checks)s,
    %(reflection_prompt)s, %(tags)s, %(difficulty)s, %(estimated_minutes)s,
    %(status)s, %(source)s, %(version)s
)
ON CONFLICT (activity_id) DO UPDATE SET
    grade_level = EXCLUDED.grade_level,
    grade_band = EXCLUDED.grade_band,
    subject = EXCLUDED.subject,
    course = EXCLUDED.course,
    unit_number = EXCLUDED.unit_number,
    unit_title = EXCLUDED.unit_title,
    lesson_number = EXCLUDED.lesson_number,
    lesson_title = EXCLUDED.lesson_title,
    activity_type = EXCLUDED.activity_type,
    standards = EXCLUDED.standards,
    visual_surface = EXCLUDED.visual_surface,
    content = EXCLUDED.content,
    checks = EXCLUDED.checks,
    reflection_prompt = EXCLUDED.reflection_prompt,
    tags = EXCLUDED.tags,
    difficulty = EXCLUDED.difficulty,
    estimated_minutes = EXCLUDED.estimated_minutes,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    version = EXCLUDED.version,
    updated_at = NOW()
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed prebuilt activities from JSON files.")
    parser.add_argument("--dry-run", action="store_true", help="Validate files without writing to the DB.")
    parser.add_argument("--course", help="Only seed one course name, case-insensitive.")
    parser.add_argument(
        "--status",
        default="published",
        choices=sorted(STATUS_VALUES),
        help="Default status for records that do not declare one.",
    )
    return parser.parse_args()


def discover_files() -> list[Path]:
    if not DATA_ROOT.exists():
        return []
    return sorted(DATA_ROOT.rglob("*.json"))


def json_params(row: dict) -> dict:
    out = dict(row)
    for key in ("standards", "visual_surface", "content", "checks", "reflection_prompt"):
        out[key] = Json(out.get(key) or ([] if key in {"standards", "checks"} else {}))
    out["tags"] = out.get("tags") or []
    return out


def main() -> None:
    args = parse_args()
    files = discover_files()
    if not files:
        raise SystemExit(f"No JSON files found under {DATA_ROOT}")

    rows: list[dict] = []
    errors: list[str] = []
    course_filter = args.course.strip().lower() if args.course else None

    for path in files:
        try:
            course_doc = load_course_file(path)
            if course_filter and course_doc.course.strip().lower() != course_filter:
                continue
            rows.extend(iter_seed_rows(course_doc, default_status=args.status))
        except Exception as exc:
            errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        raise SystemExit(1)

    if args.dry_run:
        print(f"[OK] Validated {len(files)} files; {len(rows)} activities ready")
        for row in rows:
            print(f" - {row['activity_id']} ({row['course']} / unit {row['unit_number']}, lesson {row['lesson_number']})")
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        for row in rows:
            cur.execute(UPSERT_SQL, json_params(row))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    print(f"[OK] Upserted {len(rows)} prebuilt activities")


if __name__ == "__main__":
    main()
