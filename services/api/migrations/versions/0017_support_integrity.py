"""Complete support metadata on development checkouts upgraded during implementation."""

from pathlib import Path

from alembic import op

revision = "0017_support_integrity"
down_revision = "0016_student_support"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE chalkmate.review_requests ADD COLUMN IF NOT EXISTS student_label varchar(400);
      ALTER TABLE chalkmate.review_requests ADD COLUMN IF NOT EXISTS assessment_title varchar(140);
      UPDATE chalkmate.review_requests r
      SET student_label=st.name || ' · ' || st.registration_number, assessment_title=a.title
      FROM chalkmate.submissions s, chalkmate.students st, chalkmate.assessments a
      WHERE r.submission_id=s.id AND st.id=s.student_id AND a.id=s.assessment_id
      AND (r.student_label IS NULL OR r.assessment_title IS NULL);
      ALTER TABLE chalkmate.review_requests ALTER COLUMN student_label SET NOT NULL;
      ALTER TABLE chalkmate.review_requests ALTER COLUMN assessment_title SET NOT NULL;
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='chalkmate.review_requests'::regclass
        AND conname='uq_review_requests_submission_id_decision_id_question_id_requeste') THEN
          ALTER TABLE chalkmate.review_requests RENAME CONSTRAINT
          uq_review_requests_submission_id_decision_id_question_id_requeste
          TO uq_review_request_release_question_actor;
        END IF;
      END $$;
    """)
    source = Path(__file__).with_name("0016_student_support.sql").read_text(encoding="utf-8")
    functions = source[source.index("CREATE FUNCTION chalkmate.request_review") :]
    op.execute(functions.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION"))


def downgrade():
    raise RuntimeError("Preserve student request history with a reviewed recovery migration")
