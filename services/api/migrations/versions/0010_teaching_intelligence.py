"""Private source-grounded teaching runs, finding reviews and versioned materials."""

from pathlib import Path

from alembic import op

revision = "0010_teaching_intelligence"
down_revision = "0009_scoped_contacts"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration; preserve teaching and approval history")
