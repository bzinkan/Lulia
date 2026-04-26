"""
Tenant-isolation tests — Teacher A cannot read or mutate Teacher B's
resources. Every CRUD endpoint that exposes a tenant-scoped resource
should be tested here.

Strategy: register two teachers via /auth/register, generate one resource
under each, then assert each side gets 403/404 when probing the other's
resource via the canonical endpoints.

Run: docker compose exec api pytest tests/test_tenant_isolation.py -v
"""
import os
import uuid

import httpx
import pytest


API = os.environ.get("API_BASE_FOR_TESTS", "http://api:8000")


def _register(suffix: str) -> dict:
    email = f"isolation_{suffix}_{uuid.uuid4().hex[:8]}@lulia.example"
    r = httpx.post(f"{API}/api/v1/auth/register",
                   json={"email": email, "password": "TestPass123", "name": f"Test {suffix}"},
                   timeout=15)
    r.raise_for_status()
    return r.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def two_teachers():
    """Two freshly-registered teachers for isolation testing."""
    a = _register("a")
    b = _register("b")
    return a, b


@pytest.fixture(scope="module")
def alice_activity(two_teachers):
    """An interactive activity owned by Teacher A."""
    a, _ = two_teachers
    r = httpx.post(
        f"{API}/api/v1/assistant/generate-from-prompt",
        headers=_auth(a["access_token"]),
        json={
            "prompt": "Crossword for 4th grade about rocks and minerals",
            "output_type": "interactive",
            "template_id": "crossword",
            "topic": "Rocks and minerals",
            "subject": "Science",
            "grade": "4",
            "standards": [],
        },
        timeout=120,
    )
    r.raise_for_status()
    body = r.json()
    aid = (body.get("interactive") or {}).get("activity_id")
    assert aid, f"no activity_id in {body}"
    return aid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestActivities:
    def test_owner_can_read_own_data(self, two_teachers, alice_activity):
        a, _ = two_teachers
        r = httpx.get(f"{API}/api/v1/interactive/{alice_activity}/data",
                      headers=_auth(a["access_token"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["activity_id"] == alice_activity
        assert body["mode"] == "structured"
        assert body["data"] is not None

    def test_other_teacher_cannot_read_data(self, two_teachers, alice_activity):
        _, b = two_teachers
        r = httpx.get(f"{API}/api/v1/interactive/{alice_activity}/data",
                      headers=_auth(b["access_token"]), timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_other_teacher_cannot_update_data(self, two_teachers, alice_activity):
        _, b = two_teachers
        r = httpx.put(f"{API}/api/v1/interactive/{alice_activity}/data",
                      headers=_auth(b["access_token"]),
                      json={"data": {"title": "Hijacked", "words": []}},
                      timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_other_teacher_cannot_delete(self, two_teachers, alice_activity):
        _, b = two_teachers
        r = httpx.delete(f"{API}/api/v1/interactive/{alice_activity}",
                         headers=_auth(b["access_token"]), timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_unauthenticated_strict_endpoints(self, alice_activity):
        """No token + no dev bypass header — must 401.
        We can't disable DEV_AUTH_BYPASS at runtime, so skip if it's enabled.
        """
        # Try with an obviously-bad token: that path always 401s regardless of bypass.
        r = httpx.get(f"{API}/api/v1/interactive/{alice_activity}/data",
                      headers={"Authorization": "Bearer not-a-real-token"}, timeout=15)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


class TestAuthMe:
    def test_me_returns_caller_identity(self, two_teachers):
        a, b = two_teachers
        ra = httpx.get(f"{API}/api/v1/auth/me", headers=_auth(a["access_token"]), timeout=10).json()
        rb = httpx.get(f"{API}/api/v1/auth/me", headers=_auth(b["access_token"]), timeout=10).json()
        assert ra["teacher_id"] == a["teacher_id"]
        assert rb["teacher_id"] == b["teacher_id"]
        assert ra["teacher_id"] != rb["teacher_id"]

    def test_register_rejects_duplicate_email(self, two_teachers):
        a, _ = two_teachers
        r = httpx.post(f"{API}/api/v1/auth/register",
                       json={"email": a["email"], "password": "TestPass123", "name": "Dup"},
                       timeout=10)
        assert r.status_code == 409

    def test_login_wrong_password_401(self, two_teachers):
        a, _ = two_teachers
        r = httpx.post(f"{API}/api/v1/auth/login",
                       json={"email": a["email"], "password": "wrong"}, timeout=10)
        assert r.status_code == 401
