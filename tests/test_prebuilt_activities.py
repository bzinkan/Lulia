"""Prebuilt activity library smoke tests."""
import os
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest

from src.lms_agents.tools.prebuilt_activity_schema import iter_seed_rows, load_course_file


API = os.environ.get("API_BASE_FOR_TESTS", "http://api:8000")
ROOT = Path(__file__).resolve().parents[1]


def _register() -> dict:
    email = f"prebuilt_{uuid.uuid4().hex[:8]}@lulia.example"
    res = httpx.post(
        f"{API}/api/v1/auth/register",
        json={"email": email, "password": "TestPass123", "name": "Prebuilt Teacher"},
        timeout=15,
    )
    res.raise_for_status()
    return res.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module", autouse=True)
def migrated_and_seeded():
    subprocess.run(["python", "scripts/migrate_prebuilt_activities.py"], cwd=ROOT, check=True)
    subprocess.run(["python", "scripts/seed_prebuilt_activities.py", "--status", "published"], cwd=ROOT, check=True)


def test_prebuilt_json_files_validate():
    rows = []
    for path in (ROOT / "data" / "prebuilt_activities").rglob("*.json"):
        rows.extend(iter_seed_rows(load_course_file(path), default_status="published"))

    assert len(rows) >= 5
    assert {row["subject"] for row in rows} >= {"Science", "Math", "ELA", "Social Studies"}


def test_prebuilt_api_list_preview_map_and_use():
    teacher = _register()
    headers = _auth(teacher["access_token"])

    list_res = httpx.get(
        f"{API}/api/v1/prebuilt-activities",
        params={"subject": "Science", "status": "published"},
        headers=headers,
        timeout=15,
    )
    list_res.raise_for_status()
    activities = list_res.json()["activities"]
    assert any(item["activity_id"] == "ms_grade7_science_u1_l1_cell_organelles" for item in activities)

    activity_id = "ms_grade7_science_u1_l1_cell_organelles"
    get_res = httpx.get(f"{API}/api/v1/prebuilt-activities/{activity_id}", headers=headers, timeout=15)
    get_res.raise_for_status()
    assert get_res.json()["activity_type"] == "visual_study"

    preview_res = httpx.post(f"{API}/api/v1/prebuilt-activities/{activity_id}/preview", headers=headers, timeout=15)
    preview_res.raise_for_status()
    preview_html = preview_res.json()["html"]
    assert "Animal Cell Organelles Visual Study" in preview_html
    assert "Labels on" in preview_html

    map_res = httpx.get(
        f"{API}/api/v1/prebuilt-activities/courses/Grade%207%20Science/map",
        headers=headers,
        timeout=15,
    )
    map_res.raise_for_status()
    assert map_res.json()["units"][0]["lessons"][0]["activity_id"] == activity_id

    use_res = httpx.post(
        f"{API}/api/v1/prebuilt-activities/{activity_id}/use",
        json={"customizations": {}},
        headers=headers,
        timeout=30,
    )
    use_res.raise_for_status()
    body = use_res.json()
    assert body["source_prebuilt_activity_id"] == activity_id
    assert body["activity_id"]
    assert body["access_url"]
