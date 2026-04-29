# Prebuilt Activities Discovery

## Current Interactive Flow

Lulia currently generates interactive activities through the backend interactive tools and routes:

- `src/lms_agents/routers/activities.py`
- `src/lms_agents/tools/interactive_generator.py`
- `src/lms_agents/tools/hotspot_diagram_generator.py`
- `src/lms_agents/tools/visual_renderer.py`
- `src/lms_agents/tools/structured_common.py`

The primary teacher-facing route is `POST /api/v1/interactive/generate`. Assistant-driven generation also routes into the same structured activity deployment helpers when the requested output is interactive.

Generated structured interactives are persisted as two linked records:

- `assignments`: teacher/class-owned assignment metadata, standards, questions, output format, and file paths.
- `interactive_activities`: the live interactive runtime record, including template id, `content_json`, access code, access URL, status, and attempt settings.

Student submissions are stored in:

- `interactive_submissions`

The generated HTML is uploaded to the configured activities object store bucket, usually `lulia-activities` in MinIO/S3, then `interactive_activities.access_url` points to the deployed HTML. Structured templates keep editable data inside `interactive_activities.content_json` under:

```json
{
  "mode": "structured",
  "template": "crossword",
  "data": {}
}
```

The current editable structured templates are registered in `structured_common.get_builder()` and include crossword, word search, flash cards, timeline, number line, and fill-in-the-blank. Artifact-style generated interactives do not yet have the same JSON edit round trip.

## Current Content Shape

There is no canonical prebuilt activity table yet. Existing generated activities use a runtime payload shaped around template output:

- `interactive_template_id`: renderer/template identifier.
- `content_json.mode`: usually `structured` or artifact mode.
- `content_json.template`: structured template id.
- `content_json.data`: template-specific editable data.
- Additional template summary fields, such as title/topic/grade/subject, may be spread into `content_json`.

This makes generated interactives usable, but not ideal as the source of truth for a large curated curriculum library.

## Storage Decision

Prebuilt activities should be stored as static JSON files that seed into a database table.

This gives Lulia both workflows it needs:

- Static JSON in `data/prebuilt_activities/` keeps curriculum records reviewable in Git.
- A database-backed `prebuilt_activities` table makes teacher library browsing, filtering, previewing, and assignment use fast at runtime.

The canonical prebuilt record should remain separate from teacher-owned copies. When a teacher uses an activity, Lulia should create a normal `assignments` row plus an `interactive_activities` row from the prebuilt record, preserving the existing generated activity flow.

## Files And Tables To Update

Phase 1-4 backend files:

- `scripts/init.sql`
- `scripts/migrate_prebuilt_activities.py`
- `src/lms_agents/tools/prebuilt_activity_schema.py`
- `src/lms_agents/tools/prebuilt_activity_renderer.py`
- `src/lms_agents/routers/prebuilt_activities.py`
- `src/lms_agents/main.py`
- `scripts/seed_prebuilt_activities.py`

Phase 1-4 data files:

- `data/prebuilt_activities/**/*.json`

Phase 1-4 frontend files:

- `dashboard/src/app/prebuilt/page.jsx`
- `dashboard/src/components/Sidebar.jsx`

Tables:

- New canonical table: `prebuilt_activities`
- Existing copy/use tables: `assignments`, `interactive_activities`, `interactive_submissions`

Future phases should add admin review endpoints and richer renderer/editor support without replacing the existing generated interactive routes.
