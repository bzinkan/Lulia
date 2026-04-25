# Alembic migrations

Forward migrations now live here. The legacy `scripts/migrate_*.py` chain is
frozen — don't add new scripts to it.

## Creating a new migration

```bash
docker compose exec api alembic revision -m "add foo to bar"
```

Alembic writes a new file under `alembic/versions/` with timestamp + slug
filename, an empty `upgrade()`, and an empty `downgrade()`. Fill those in
with `op.execute(...)` or SQLAlchemy's `op.add_column` / `op.create_index`
helpers.

## Applying migrations

On boot, `main.py` automatically:

1. Runs the legacy `migrate_*.py` chain (tracked in `schema_migrations`).
2. Stamps the DB at `0000_baseline` if Alembic has never touched it.
3. Runs `alembic upgrade head` to apply any new revisions.

For manual operations:

```bash
docker compose exec api alembic current      # show current revision
docker compose exec api alembic history      # show full chain
docker compose exec api alembic upgrade head # apply pending
docker compose exec api alembic downgrade -1 # revert last revision
```

## Why we have both migrate_*.py and alembic/

Before Wave 2, 14 idempotent `migrate_*.py` scripts had already applied
against every dev + staging DB. Hand-translating them into Alembic
revisions would risk a re-apply bug that no one would catch until prod.
Instead, we:

- Kept the legacy chain idempotent and tracked in `schema_migrations`.
- Added an empty `0000_baseline` revision that represents "whatever state
  the legacy chain leaves us in".
- Stamp new databases with that baseline on first boot.
- Everything authored after April 2026 goes through Alembic.

## When to use `--autogenerate`

Don't. The app uses raw `psycopg2` + `init.sql` rather than a SQLAlchemy
ORM, so there are no Python models for Alembic to diff against. Author
migrations by hand.
