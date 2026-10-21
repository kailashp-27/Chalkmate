"""Reliable review snapshots, rubric revisions, and immutable replacement releases."""

from pathlib import Path

from alembic import op

revision = "0006_reliable_review"
down_revision = "0005_job_recovery"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration; review history must be preserved")
