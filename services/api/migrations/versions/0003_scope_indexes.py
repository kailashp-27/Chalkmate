"""Index the class-scope lookups used by application authorization and RLS."""

from alembic import op

revision = "0003_scope_indexes"
down_revision = "0002_workspace_visibility"
branch_labels = None
depends_on = None

INDEXES = {
    "classrooms": ["workspace_id"],
    "classroom_teachers": ["user_id", "classroom_id"],
    "enrollments": ["student_id", "classroom_id"],
    "import_batches": ["classroom_id"],
    "invitations": ["email", "workspace_id"],
    "files": ["classroom_id"],
    "audit_events": ["classroom_id", "created_at"],
}


def upgrade():
    for table, columns in INDEXES.items():
        op.create_index(f"ix_{table}_scope", table, columns, schema="chalkmate")


def downgrade():
    for table in reversed(INDEXES):
        op.drop_index(f"ix_{table}_scope", table, schema="chalkmate")
