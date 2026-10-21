"""Pin explicit calibration examples to jobs/proposals and constrain rubric scopes."""

from alembic import op

revision = "0007_calibrated_jobs"
down_revision = "0006_reliable_review"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE chalkmate.processing_jobs ADD COLUMN calibration_ids jsonb NOT NULL DEFAULT '[]';
    ALTER TABLE chalkmate.processing_jobs ALTER COLUMN calibration_ids DROP DEFAULT;
    ALTER TABLE chalkmate.proposals ADD COLUMN calibration_ids jsonb NOT NULL DEFAULT '[]';
    ALTER TABLE chalkmate.proposals ALTER COLUMN calibration_ids DROP DEFAULT;
    ALTER TABLE chalkmate.rubrics
      ADD CONSTRAINT uq_rubrics_workspace_id_classroom_id_id
      UNIQUE(workspace_id,classroom_id,id);
    ALTER TABLE chalkmate.question_reviews
      ADD CONSTRAINT fk_question_reviews_workspace_id_rubrics
      FOREIGN KEY(workspace_id,classroom_id,rubric_id)
      REFERENCES chalkmate.rubrics(workspace_id,classroom_id,id);
    ALTER TABLE chalkmate.calibrations
      ADD CONSTRAINT fk_calibrations_workspace_id_rubrics
      FOREIGN KEY(workspace_id,classroom_id,rubric_id)
      REFERENCES chalkmate.rubrics(workspace_id,classroom_id,id);
    ALTER TABLE chalkmate.reevaluations
      ADD CONSTRAINT fk_reevaluations_workspace_id_rubrics
      FOREIGN KEY(workspace_id,classroom_id,from_rubric_id)
      REFERENCES chalkmate.rubrics(workspace_id,classroom_id,id);
    ALTER TABLE chalkmate.reevaluations
      ADD CONSTRAINT fk_reevaluations_workspace_id_rubrics_target
      FOREIGN KEY(workspace_id,classroom_id,to_rubric_id)
      REFERENCES chalkmate.rubrics(workspace_id,classroom_id,id);
    """)


def downgrade():
    raise RuntimeError("Use a reviewed recovery migration")
