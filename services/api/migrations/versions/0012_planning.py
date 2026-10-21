"""Private immutable planning, explicit approvals and durable bounded generation."""

from pathlib import Path

from alembic import op

revision = "0012_planning"
down_revision = "0011_material_export_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration; preserve planning history")
