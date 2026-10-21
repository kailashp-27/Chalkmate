"""Immutable marks snapshots and append-only bank/question links."""

from pathlib import Path

from alembic import op

revision = "0014_reporting"
down_revision = "0013_planning_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration; preserve export and link history")
