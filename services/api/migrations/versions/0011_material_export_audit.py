"""Audit read-only material exports without granting reviewers general audit writes."""

from alembic import op

revision = "0011_material_export_audit"
down_revision = "0010_teaching_intelligence"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION chalkmate.record_material_export(mid uuid,with_key boolean) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
    DECLARE material chalkmate.teaching_materials;
    BEGIN
      SELECT * INTO material FROM chalkmate.teaching_materials WHERE id=mid;
      IF NOT FOUND OR NOT chalkmate.staff(material.classroom_id) THEN RETURN false; END IF;
      INSERT INTO chalkmate.audit_events(id,workspace_id,classroom_id,actor_id,action,details)
      VALUES(gen_random_uuid(),material.workspace_id,material.classroom_id,chalkmate.actor(),
        'material.exported',jsonb_build_object('material_id',mid,'answer_key',with_key));
      RETURN true;
    END $$;
    REVOKE ALL ON FUNCTION chalkmate.record_material_export(uuid,boolean) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION chalkmate.record_material_export(uuid,boolean) TO chalkmate_app;
    """)


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration")
