"""Private, versioned teaching analysis and teacher-approved practice material."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from chalkmate.assessment_models import Scoped, assessment_scope
from chalkmate.db import Base


def run_scope():
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id", "run_id"],
        [
            "chalkmate.intelligence_runs.workspace_id",
            "chalkmate.intelligence_runs.classroom_id",
            "chalkmate.intelligence_runs.id",
        ],
    )


class IntelligenceRun(Scoped, Base):
    __tablename__ = "intelligence_runs"
    __table_args__ = (
        assessment_scope(),
        ForeignKeyConstraint(
            ["assessment_id", "rubric_id"],
            ["chalkmate.rubrics.assessment_id", "chalkmate.rubrics.id"],
            name="fk_intelligence_runs_assessment_rubric",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "rubric_id"],
            [
                "chalkmate.rubrics.workspace_id",
                "chalkmate.rubrics.classroom_id",
                "chalkmate.rubrics.id",
            ],
        ),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
        CheckConstraint("kind IN ('analysis','material')", name="valid_kind"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','canceled')", name="valid_status"
        ),
    )
    assessment_id: Mapped[UUID]
    rubric_id: Mapped[UUID]
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(160))
    model_digest: Mapped[str] = mapped_column(String(100), default="")
    prompt_version: Mapped[str] = mapped_column(String(50))
    request: Mapped[dict] = mapped_column(JSONB)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    input_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(500))
    result: Mapped[dict | None] = mapped_column(JSONB)
    usage: Mapped[dict] = mapped_column(JSONB, default=dict)


class FindingReview(Scoped, Base):
    __tablename__ = "finding_reviews"
    __table_args__ = (
        run_scope(),
        UniqueConstraint("run_id", "finding_index", "version"),
        CheckConstraint("disposition IN ('accepted','dismissed')", name="valid_disposition"),
    )
    run_id: Mapped[UUID]
    finding_index: Mapped[int]
    version: Mapped[int]
    disposition: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(2000))
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))


class TeachingMaterial(Scoped, Base):
    __tablename__ = "teaching_materials"
    __table_args__ = (
        run_scope(),
        UniqueConstraint("run_id", "version"),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
    )
    run_id: Mapped[UUID]
    version: Mapped[int]
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    content: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(2000))


class MaterialApproval(Scoped, Base):
    __tablename__ = "material_approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "material_id"],
            [
                "chalkmate.teaching_materials.workspace_id",
                "chalkmate.teaching_materials.classroom_id",
                "chalkmate.teaching_materials.id",
            ],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "assignment_version_id"],
            [
                "chalkmate.assignment_versions.workspace_id",
                "chalkmate.assignment_versions.classroom_id",
                "chalkmate.assignment_versions.id",
            ],
        ),
        UniqueConstraint("material_id"),
    )
    material_id: Mapped[UUID]
    assignment_version_id: Mapped[UUID]
    approved_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    reason: Mapped[str] = mapped_column(String(2000))


for model in [IntelligenceRun, FindingReview, TeachingMaterial, MaterialApproval]:
    Index(f"ix_{model.__tablename__}_class", model.classroom_id)
