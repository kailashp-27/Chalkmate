"""Enforce planning attempt bounds and result classroom scope in PostgreSQL."""

from alembic import op

revision = "0013_planning_integrity"
down_revision = "0012_planning"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE chalkmate.planning_documents ADD CONSTRAINT ck_planning_documents_valid_version
      CHECK(version>0);
    ALTER TABLE chalkmate.planning_jobs ADD CONSTRAINT ck_planning_jobs_valid_status
      CHECK(status IN ('queued','running','succeeded','failed','canceled'));
    ALTER TABLE chalkmate.planning_jobs ADD CONSTRAINT ck_planning_jobs_valid_attempts
      CHECK(attempts BETWEEN 0 AND 3 AND budget_attempts BETWEEN 1 AND 20);
    ALTER TABLE chalkmate.planning_jobs
      ADD CONSTRAINT fk_planning_jobs_workspace_id_planning_documents
      FOREIGN KEY(workspace_id,classroom_id,result_id)
      REFERENCES chalkmate.planning_documents(workspace_id,classroom_id,id);
    """)


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration")
