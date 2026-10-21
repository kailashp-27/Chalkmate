"""Allow the owner to see the workspace while its membership is being created."""

from alembic import op

revision = "0002_workspace_visibility"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP POLICY workspace_read ON chalkmate.workspaces")
    op.execute(
        "CREATE POLICY workspace_read ON chalkmate.workspaces FOR SELECT "
        "USING(owner_id=chalkmate.actor() OR chalkmate.member(id))"
    )


def downgrade():
    op.execute("DROP POLICY workspace_read ON chalkmate.workspaces")
    op.execute(
        "CREATE POLICY workspace_read ON chalkmate.workspaces FOR SELECT "
        "USING(chalkmate.member(id))"
    )
