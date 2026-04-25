"""Baseline — represents the schema as of Phase 28 (Wave 2).

Revision ID: 0000_baseline
Revises:
Create Date: 2026-04-22 00:00:00

This is a no-op migration on purpose. Every Lulia database in existence
(Brian's dev DB, any staging instance) has already been brought up to this
schema state via:
    - scripts/init.sql (creates every base table)
    - 14 idempotent scripts/migrate_*.py (ALTER TABLEs for phases 17-28)

All of those are tracked in the legacy `schema_migrations` table that
scripts/run_migrations.py manages. This baseline tells Alembic "treat the
DB as already being at this revision" so future migrations stack on top
cleanly.

For a FRESH database (first deploy after this lands), the sequence is:
    1. init.sql runs at container startup
    2. run_migrations.py applies the migrate_*.py chain
    3. `alembic stamp 0000_baseline` (run once by the entrypoint script)
       so the alembic_version table knows we're at baseline.
    4. Any NEW migration authored after today goes as a new alembic
       revision and will be picked up by `alembic upgrade head`.

This layered approach lets us move to Alembic without hand-translating the
14 existing scripts (which work fine and are proven on every dev laptop).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0000_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentional no-op. The baseline represents "whatever state the legacy
    # migrate_*.py chain leaves us in". If you ever need to apply this
    # against a truly empty database, run `scripts/init.sql` + the
    # `migrate_*.py` chain first.
    pass


def downgrade() -> None:
    # We don't support downgrading past the baseline. Anything below this
    # would require tearing the schema down to empty, which isn't a
    # workflow we'll use in practice.
    raise NotImplementedError("Cannot downgrade past baseline revision")
