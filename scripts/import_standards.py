"""
Lulia — Standards Importer
Downloads standards from the Common Standards Project API and loads them
into the three-tier standards_frameworks + standards tables.

Usage:
    # Inside the api container:
    python scripts/import_standards.py --national          # Tier 3: Common Core, NGSS, C3
    python scripts/import_standards.py --state OH          # Tier 2: single state
    python scripts/import_standards.py --all-states        # Tier 2: all 50 states + DC
    python scripts/import_standards.py --national --all-states  # Everything

Idempotent: safe to run multiple times. Uses ON CONFLICT DO NOTHING.
"""

import argparse
import logging
import os
import sys
import time
from uuid import uuid4

import httpx
import psycopg2
from psycopg2.extras import Json, execute_values

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [import] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

API_BASE = "http://api.commonstandardsproject.com/api/v1"
REQUEST_DELAY = 0.5  # seconds between API calls to be polite

# US states + DC — used to filter the jurisdictions list
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

# Reverse lookup: title -> state code
STATE_BY_TITLE = {v: k for k, v in US_STATES.items()}

# Known national framework jurisdiction IDs
NATIONAL_JURISDICTIONS = {
    "Common Core State Standards": {
        "jurisdiction_id": "67810E9EF6944F9383DCC602A3484C23",
        "authority": "CCSSO / NGA",
        "tier": "national",
        "priority": 3,
    },
}

# Subject normalization map
SUBJECT_MAP = {
    "Math": "Math",
    "Mathematics": "Math",
    "Common Core Mathematics": "Math",
    "ELA": "ELA",
    "English Language Arts": "ELA",
    "Common Core English/Language Arts": "ELA",
    "English Language Arts & Literacy": "ELA",
    "ELA & Literacy": "ELA",
    "Science": "Science",
    "Social Studies": "Social Studies",
    "History": "Social Studies",
}


def normalize_subject(raw: str) -> str:
    """Normalize subject names to our canonical set."""
    for pattern, canonical in SUBJECT_MAP.items():
        if pattern.lower() in raw.lower():
            return canonical
    return raw


def normalize_grade(education_levels: list[str]) -> str | None:
    """Convert educationLevels like ['08'] or ['09','10','11','12'] to grade string."""
    if not education_levels:
        return None
    levels = sorted(education_levels)
    if len(levels) == 1:
        grade = levels[0].lstrip("0") or "K"
        if grade == "13":
            return "K"
        return grade
    low = levels[0].lstrip("0") or "K"
    high = levels[-1].lstrip("0") or "K"
    return f"{low}-{high}"


def get_db_connection():
    """Connect to PostgreSQL using env vars."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )


def api_get(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    """Make a GET request to the Common Standards Project API."""
    url = f"{API_BASE}{path}"
    headers = {}
    api_key = os.environ.get("COMMON_STANDARDS_API_KEY")
    if api_key:
        headers["Api-Key"] = api_key
    resp = client.get(url, params=params or {}, headers=headers, timeout=30)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return resp.json()


def fetch_jurisdictions(client: httpx.Client) -> list[dict]:
    """Fetch all jurisdictions from the API."""
    log.info("Fetching jurisdictions list...")
    data = api_get(client, "/jurisdictions")
    return data.get("data", [])


def fetch_jurisdiction_detail(client: httpx.Client, jur_id: str) -> dict:
    """Fetch a jurisdiction with its standard sets."""
    data = api_get(client, f"/jurisdictions/{jur_id}")
    return data.get("data", {})


def fetch_standard_set(client: httpx.Client, set_id: str) -> dict:
    """Fetch a full standard set with all individual standards."""
    data = api_get(client, f"/standard_sets/{set_id}")
    return data.get("data", {})


def upsert_framework(
    cur, name: str, tier: str, state_code: str | None,
    authority: str | None, subjects: list[str],
    grade_range: str | None, priority: int,
    uploaded_by=None,
) -> str:
    """Insert a framework if it doesn't exist, return its ID."""
    # Check if it already exists by name + tier + state_code
    cur.execute(
        """SELECT framework_id FROM standards_frameworks
           WHERE name = %s AND tier = %s AND COALESCE(state_code, '') = COALESCE(%s, '')""",
        (name, tier, state_code),
    )
    row = cur.fetchone()
    if row:
        log.info(f"  Framework already exists: {name} ({tier})")
        return str(row[0])

    framework_id = str(uuid4())
    cur.execute(
        """INSERT INTO standards_frameworks
           (framework_id, name, tier, state_code, authority, subjects_covered,
            grade_range, is_active, priority, uploaded_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, true, %s, %s)
           ON CONFLICT DO NOTHING
           RETURNING framework_id""",
        (framework_id, name, tier, state_code, authority, Json(subjects),
         grade_range, priority, uploaded_by),
    )
    result = cur.fetchone()
    if result:
        log.info(f"  Created framework: {name} ({tier}, priority={priority})")
        return str(result[0])
    return framework_id


def load_standard_set(
    cur, client: httpx.Client, set_meta: dict,
    framework_id: str, subject: str, grade: str | None,
) -> int:
    """Fetch and load a single standard set into the standards table. Returns count loaded."""
    set_id = set_meta["id"]
    log.info(f"    Fetching standard set: {set_meta.get('title', set_id)} ({subject})")

    try:
        set_data = fetch_standard_set(client, set_id)
    except httpx.HTTPStatusError as e:
        log.warning(f"    Failed to fetch {set_id}: {e}")
        return 0

    standards_dict = set_data.get("standards", {})
    if not standards_dict:
        return 0

    # Build the CSP ID -> our UUID mapping for parent references
    id_map: dict[str, str] = {}
    standards_list = []

    for csp_id, std in standards_dict.items():
        our_id = str(uuid4())
        id_map[csp_id] = our_id
        standards_list.append((csp_id, our_id, std))

    # Sort by position for consistent ordering
    standards_list.sort(key=lambda x: x[2].get("position", 0))

    rows = []
    for csp_id, our_id, std in standards_list:
        code = (
            std.get("statementNotation")
            or std.get("altStatementNotation")
            or std.get("listId")
            or f"[{std.get('depth', 0)}]"
        )
        description = std.get("description", "").strip()
        if not description:
            continue

        parent_csp_id = std.get("parentId")
        parent_id = id_map.get(parent_csp_id) if parent_csp_id else None

        domain = None
        cluster = None
        depth = std.get("depth", 0)
        label = (std.get("statementLabel") or "").lower()

        if depth == 0 or "domain" in label:
            domain = description[:255]
        elif depth == 1 or "cluster" in label:
            cluster = description[:255]

        # Determine cognitive level from label
        cognitive_level = None
        if "standard" in label:
            cognitive_level = "Apply"

        std_grade = normalize_grade(
            set_data.get("educationLevels", [])
        ) or grade

        rows.append((
            our_id, framework_id, parent_id, code, description,
            std_grade, subject, domain, cluster, cognitive_level,
        ))

    if not rows:
        return 0

    # Batch insert with ON CONFLICT on standard_id (UUID, effectively no conflict)
    execute_values(
        cur,
        """INSERT INTO standards
           (standard_id, framework_id, parent_id, code, description,
            grade_level, subject, domain, cluster, cognitive_level)
           VALUES %s
           ON CONFLICT (standard_id) DO NOTHING""",
        rows,
    )
    return len(rows)


def import_jurisdiction(
    cur, client: httpx.Client, jur_id: str, jur_title: str,
    tier: str, state_code: str | None, authority: str | None, priority: int,
):
    """Import all standard sets from a jurisdiction."""
    log.info(f"Importing jurisdiction: {jur_title} (tier={tier})")

    detail = fetch_jurisdiction_detail(client, jur_id)
    standard_sets = detail.get("standardSets", [])

    if not standard_sets:
        log.warning(f"  No standard sets found for {jur_title}")
        return

    # Group sets by subject to build the framework
    subject_sets: dict[str, list] = {}
    for ss in standard_sets:
        raw_subject = ss.get("subject", "Unknown")
        subject = normalize_subject(raw_subject)
        subject_sets.setdefault(subject, []).append(ss)

    all_subjects = list(subject_sets.keys())

    # Compute grade range from all sets
    all_grades = set()
    for ss in standard_sets:
        for lvl in ss.get("educationLevels", []):
            all_grades.add(lvl)
    grade_range = None
    if all_grades:
        sorted_grades = sorted(all_grades)
        low = sorted_grades[0].lstrip("0") or "K"
        high = sorted_grades[-1].lstrip("0") or "K"
        grade_range = f"{low}-{high}" if low != high else low

    framework_id = upsert_framework(
        cur, jur_title, tier, state_code, authority,
        all_subjects, grade_range, priority,
    )

    # Check if this framework already has standards loaded
    cur.execute(
        "SELECT COUNT(*) FROM standards WHERE framework_id = %s",
        (framework_id,),
    )
    existing_count = cur.fetchone()[0]
    if existing_count > 0:
        log.info(f"  Framework already has {existing_count} standards, skipping")
        return

    total = 0
    for subject, sets in subject_sets.items():
        for ss in sets:
            grade = normalize_grade(ss.get("educationLevels", []))
            count = load_standard_set(cur, client, ss, framework_id, subject, grade)
            total += count

    log.info(f"  Loaded {total} standards for {jur_title}")


def import_national(cur, client: httpx.Client):
    """Import Tier 3 national standards (Common Core Math + ELA, NGSS, C3)."""
    log.info("=== Importing National Standards (Tier 3) ===")

    for name, info in NATIONAL_JURISDICTIONS.items():
        import_jurisdiction(
            cur, client,
            jur_id=info["jurisdiction_id"],
            jur_title=name,
            tier="national",
            state_code=None,
            authority=info["authority"],
            priority=3,
        )


def import_state(cur, client: httpx.Client, state_code: str):
    """Import a single state's standards as Tier 2."""
    state_name = US_STATES.get(state_code.upper())
    if not state_name:
        log.error(f"Unknown state code: {state_code}")
        return

    log.info(f"=== Importing State Standards: {state_name} ({state_code}) (Tier 2) ===")

    # Find the jurisdiction ID for this state
    jurisdictions = fetch_jurisdictions(client)
    jur = None
    for j in jurisdictions:
        if j.get("title") == state_name and j.get("type") == "state":
            jur = j
            break

    if not jur:
        # Try partial match
        for j in jurisdictions:
            if state_name.lower() in j.get("title", "").lower() and j.get("type") == "state":
                jur = j
                break

    if not jur:
        log.warning(f"  Could not find jurisdiction for {state_name}")
        return

    import_jurisdiction(
        cur, client,
        jur_id=jur["id"],
        jur_title=f"{state_name} Learning Standards",
        tier="state",
        state_code=state_code.upper(),
        authority=f"{state_name} Department of Education",
        priority=2,
    )


def import_all_states(cur, client: httpx.Client):
    """Import all 50 states + DC as Tier 2."""
    log.info("=== Importing All State Standards (Tier 2) ===")

    jurisdictions = fetch_jurisdictions(client)
    state_jurisdictions = {}
    for j in jurisdictions:
        title = j.get("title", "")
        if j.get("type") == "state" and title in STATE_BY_TITLE:
            state_jurisdictions[STATE_BY_TITLE[title]] = j

    log.info(f"Found {len(state_jurisdictions)} US state jurisdictions")

    for state_code in sorted(US_STATES.keys()):
        jur = state_jurisdictions.get(state_code)
        if not jur:
            log.warning(f"  Skipping {state_code} ({US_STATES[state_code]}) — not found in API")
            continue

        import_jurisdiction(
            cur, client,
            jur_id=jur["id"],
            jur_title=f"{US_STATES[state_code]} Learning Standards",
            tier="state",
            state_code=state_code,
            authority=f"{US_STATES[state_code]} Department of Education",
            priority=2,
        )


def main():
    parser = argparse.ArgumentParser(description="Import standards from Common Standards Project")
    parser.add_argument("--national", action="store_true", help="Import national standards (Tier 3)")
    parser.add_argument("--state", type=str, help="Import a single state (e.g. OH)")
    parser.add_argument("--all-states", action="store_true", help="Import all 50 states + DC")
    args = parser.parse_args()

    if not args.national and not args.state and not args.all_states:
        parser.print_help()
        sys.exit(1)

    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()

    client = httpx.Client()

    try:
        if args.national:
            import_national(cur, client)
            conn.commit()

        if args.state:
            import_state(cur, client, args.state)
            conn.commit()

        if args.all_states:
            import_all_states(cur, client)
            conn.commit()

        # Print summary
        cur.execute(
            """SELECT tier, COUNT(DISTINCT f.framework_id), COUNT(s.standard_id)
               FROM standards_frameworks f
               LEFT JOIN standards s ON f.framework_id = s.framework_id
               GROUP BY tier ORDER BY MIN(f.priority)"""
        )
        log.info("=== Import Summary ===")
        for tier, fw_count, std_count in cur.fetchall():
            log.info(f"  {tier}: {fw_count} frameworks, {std_count} standards")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
        client.close()


if __name__ == "__main__":
    main()
