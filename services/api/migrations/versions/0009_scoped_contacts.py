"""Restrict teacher contact changes to a scoped operation, without widening account-link grants."""

from alembic import op

revision = "0009_scoped_contacts"
down_revision = "0008_classroom_followup"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    REVOKE UPDATE(email) ON chalkmate.students FROM chalkmate_app;
    CREATE FUNCTION chalkmate.set_student_contact(cid uuid,sid uuid,address text) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
    BEGIN
      IF NOT chalkmate.staff(cid,true) OR NOT EXISTS(
        SELECT 1 FROM chalkmate.enrollments e JOIN chalkmate.classrooms c ON c.id=e.classroom_id
        WHERE e.classroom_id=cid AND e.student_id=sid AND NOT c.archived)
      THEN RETURN false; END IF;
      UPDATE chalkmate.students SET email=address WHERE id=sid;
      RETURN FOUND;
    END $$;
    REVOKE ALL ON FUNCTION chalkmate.set_student_contact(uuid,uuid,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION chalkmate.set_student_contact(uuid,uuid,text) TO chalkmate_app;
    """)


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration")
