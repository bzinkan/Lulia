"""
Alembic environment.

Design notes:
    We don't have a SQLAlchemy ORM to point at (the app is raw psycopg2
    against a schema defined in scripts/init.sql plus a chain of idempotent
    migrate_*.py scripts). That means `target_metadata` is None, and we
    write migrations by hand rather than autogenerating them from models.
    This is the right shape for Lulia: the source of truth is the DB, not
    a Python class tree.

Two modes:
    - Offline: `alembic upgrade head --sql` emits SQL without connecting.
      Useful for review in a PR or for shipping migration SQL to an RDS
      admin who runs it separately.
    - Online: default. Opens a connection using the same DB_* env vars the
      rest of the app uses (so local dev + prod work with no extra config).

The `alembic_version` table lives next to `schema_migrations` (the legacy
tracker for migrate_*.py scripts). Both can coexist — the legacy tracker
keeps skipping already-applied scripts; Alembic manages everything new.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic's ConfigParser-based config. fileConfig loads the logging
# section; the rest is queried via config.get_main_option(...).
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# We're not using a SQLAlchemy ORM. `target_metadata = None` tells
# `--autogenerate` to do nothing useful; that's intentional. Migrations are
# authored by hand.
target_metadata = None


def _db_url_from_env() -> str:
    """Build a PostgreSQL SQLAlchemy URL from the standard Lulia env vars.

    Why here and not in alembic.ini: secrets don't belong in repo files. By
    assembling the URL at runtime we reuse the same env-driven config the
    rest of the app uses (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD).
    """
    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "lulia")
    user = os.environ.get("DB_USER", "lulia")
    pwd = os.environ.get("DB_PASSWORD", "devpassword")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"


def run_migrations_offline() -> None:
    """Emit SQL without connecting to a DB."""
    context.configure(
        url=_db_url_from_env(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Open a connection and apply migrations inside a transaction."""
    section = config.get_section(config.config_ini_section) or {}
    # Fill in the URL at runtime. alembic.ini has an empty sqlalchemy.url
    # on purpose — this is where the real value gets injected.
    section["sqlalchemy.url"] = _db_url_from_env()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
