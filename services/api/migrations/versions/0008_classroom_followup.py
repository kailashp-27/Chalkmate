"""Versioned assignments, private student responses, and approved recipient outbox."""

from pathlib import Path

from alembic import op

revision = "0008_classroom_followup"
down_revision = "0007_calibrated_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError(
        "Use a reviewed recovery migration; publications and delivery history must be retained"
    )
