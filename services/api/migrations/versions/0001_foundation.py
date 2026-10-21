"""Phase 1 schema, least-privilege role, and access policies."""

from pathlib import Path

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_name("0001_foundation.sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Foundation contains user data; restore a backup rather than dropping it.")
