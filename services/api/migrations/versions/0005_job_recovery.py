"""Reconcile exhausted or revoked processing jobs without granting queue-wide API access."""

from alembic import op

revision = "0005_job_recovery"
down_revision = "0004_assessment_workflow"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION chalkmate.pending_jobs() RETURNS SETOF uuid
    LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
      WITH revoked AS (UPDATE chalkmate.processing_jobs j SET status='canceled',
        error='Class access changed; processing was canceled.'
        WHERE status IN ('queued','running') AND NOT chalkmate.job_authorized(j)),
      exhausted AS (UPDATE chalkmate.processing_jobs j SET status='failed',
        error='Worker recovery attempts exhausted. Continue with manual review.'
        WHERE status='running' AND attempts>=3 AND lease_until<now())
      SELECT j.id FROM chalkmate.processing_jobs j WHERE j.attempts<3
        AND (j.status='queued' OR (j.status='running' AND j.lease_until<now()))
        AND chalkmate.job_authorized(j) ORDER BY j.created_at LIMIT 50
    $$;
    """)


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration")
