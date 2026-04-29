"""
Auto-migration runner — applies any un-applied migrate_*.py scripts in order.

Tracks applied migrations in a `schema_migrations` table (created if missing).
Each migration is run as a subprocess so scripts with different entry-point
styles (`def migrate()` vs top-level code vs `if __name__ == "__main__"`) all
work without changes.

Migrations are expected to be idempotent — the tracker is a convenience to
skip already-applied ones and surface new failures clearly on boot.

Usage:
    docker compose exec api python scripts/run_migrations.py     # manual
    (also wired into FastAPI startup — see src/lms_agents/main.py)

Env vars:
    AUTO_MIGRATE=true           — default, runs on boot
    FAIL_ON_MIGRATION_ERROR=false — default, logs errors but keeps booting
"""
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_migrations_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   VARCHAR PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status     VARCHAR NOT NULL DEFAULT 'success',
            output     TEXT
        )
    """)
    conn.commit()
    cur.close()


def _applied_filenames(conn) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT filename FROM schema_migrations WHERE status = 'success'")
    rows = {r[0] for r in cur.fetchall()}
    cur.close()
    return rows


def _mark(conn, filename: str, status: str, output: str = "") -> None:
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO schema_migrations (filename, status, output)
           VALUES (%s, %s, %s)
           ON CONFLICT (filename) DO UPDATE SET
             status = EXCLUDED.status,
             output = EXCLUDED.output,
             applied_at = NOW()""",
        (filename, status, output[:4000] if output else None),
    )
    conn.commit()
    cur.close()


def run_pending() -> dict:
    """Run all un-applied migrate_*.py scripts. Returns dict with ran/skipped/failed lists."""
    try:
        from src.lms_agents.tools.db import get_connection
    except ImportError:
        log.error("[migrations] Cannot import db module — skipping migration run")
        return {"ran": [], "skipped": [], "failed": []}

    try:
        conn = get_connection()
    except Exception as e:
        log.error(f"[migrations] Cannot connect to DB: {e}")
        return {"ran": [], "skipped": [], "failed": [("<db-connect>", str(e))]}

    _ensure_migrations_table(conn)
    applied = _applied_filenames(conn)

    scripts_dir = Path(__file__).parent
    migrations = sorted(scripts_dir.glob("migrate_*.py"))

    ran: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    for script in migrations:
        name = script.name
        if name in applied:
            skipped.append(name)
            continue

        log.info(f"[migrations] running {name}")
        try:
            # Ensure child process can import the `src` package.
            # Migration scripts assume they run from /app with PYTHONPATH including project root.
            env = os.environ.copy()
            project_root = str(scripts_dir.parent)
            env["PYTHONPATH"] = project_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=300,
                cwd=project_root, env=env,
            )
            if result.returncode == 0:
                _mark(conn, name, "success", result.stdout)
                ran.append(name)
                log.info(f"[migrations] ✓ {name}")
            else:
                _mark(conn, name, "failed", (result.stderr or result.stdout))
                failed.append((name, result.stderr or result.stdout))
                log.error(f"[migrations] ✗ {name}: {result.stderr[:200] if result.stderr else result.stdout[:200]}")
        except subprocess.TimeoutExpired:
            _mark(conn, name, "timeout", "Exceeded 5-minute timeout")
            failed.append((name, "timeout"))
            log.error(f"[migrations] ✗ {name}: timeout")
        except Exception as e:
            _mark(conn, name, "error", str(e))
            failed.append((name, str(e)))
            log.error(f"[migrations] ✗ {name}: {e}")

    conn.close()
    return {"ran": ran, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run_pending()
    print(f"\nSummary: {len(result['ran'])} applied, {len(result['skipped'])} skipped, {len(result['failed'])} failed")
    if result["ran"]:
        print("Applied:")
        for n in result["ran"]:
            print(f"  ✓ {n}")
    if result["failed"]:
        print("Failed:")
        for n, err in result["failed"]:
            print(f"  ✗ {n}: {err[:200]}")
        sys.exit(1)
