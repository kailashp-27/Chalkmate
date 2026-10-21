"""Narrow worker heartbeat functions, with classroom-scoped staff reads."""

from alembic import op

revision = "0015_operations"
down_revision = "0014_reporting"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE chalkmate.worker_heartbeats (
      name varchar(40) PRIMARY KEY, seen_at timestamptz NOT NULL
    );
    ALTER TABLE chalkmate.worker_heartbeats ENABLE ROW LEVEL SECURITY;
    CREATE FUNCTION chalkmate.record_worker_heartbeat() RETURNS void
    LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
      INSERT INTO chalkmate.worker_heartbeats(name,seen_at) VALUES('celery',clock_timestamp())
      ON CONFLICT(name) DO UPDATE SET seen_at=excluded.seen_at
    $$;
    CREATE FUNCTION chalkmate.worker_seen(cid uuid) RETURNS timestamptz
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
      SELECT seen_at FROM chalkmate.worker_heartbeats
      WHERE name='celery' AND chalkmate.staff(cid)
    $$;
    REVOKE ALL ON FUNCTION chalkmate.record_worker_heartbeat(),chalkmate.worker_seen(uuid)
      FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION chalkmate.record_worker_heartbeat() TO chalkmate_worker;
    GRANT EXECUTE ON FUNCTION chalkmate.worker_seen(uuid) TO chalkmate_app;
    """)


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration")
