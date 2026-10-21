"""Private student review requests and teacher responses."""

from pathlib import Path

from alembic import op

revision = "0016_student_support"
down_revision = "0015_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Preserve student request history with a reviewed recovery migration")
