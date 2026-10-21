"""Versioned assessment, review, release, and durable processing records."""

from pathlib import Path

from alembic import op

revision = "0004_assessment_workflow"
down_revision = "0003_scope_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Assessment history is immutable; use a reviewed recovery migration.")
