from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from chalkmate.db import Base


class Scoped:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID]
    classroom_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def class_scope():
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id"],
        ["chalkmate.classrooms.workspace_id", "chalkmate.classrooms.id"],
    )


def assessment_scope():
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id", "assessment_id"],
        [
            "chalkmate.assessments.workspace_id",
            "chalkmate.assessments.classroom_id",
            "chalkmate.assessments.id",
        ],
    )


def submission_scope():
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id", "submission_id"],
        [
            "chalkmate.submissions.workspace_id",
            "chalkmate.submissions.classroom_id",
            "chalkmate.submissions.id",
        ],
    )


class Assessment(Scoped, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        class_scope(),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
        CheckConstraint("status IN ('draft','active')", name="valid_status"),
    )
    title: Mapped[str] = mapped_column(String(140))
    instructions: Mapped[str] = mapped_column(String(4000), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")


class Rubric(Scoped, Base):
    __tablename__ = "rubrics"
    __table_args__ = (
        assessment_scope(),
        UniqueConstraint("assessment_id", "version"),
        UniqueConstraint("assessment_id", "id"),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
    )
    assessment_id: Mapped[UUID]
    reason: Mapped[str] = mapped_column(String(2000), default="")
    version: Mapped[int]
    questions: Mapped[list] = mapped_column(JSONB)
    maximum: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Submission(Scoped, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        assessment_scope(),
        ForeignKeyConstraint(
            ["assessment_id", "rubric_id"],
            ["chalkmate.rubrics.assessment_id", "chalkmate.rubrics.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "file_id"],
            ["chalkmate.files.workspace_id", "chalkmate.files.classroom_id", "chalkmate.files.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "student_id"],
            [
                "chalkmate.enrollments.workspace_id",
                "chalkmate.enrollments.classroom_id",
                "chalkmate.enrollments.student_id",
            ],
        ),
        UniqueConstraint("assessment_id", "student_id"),
        UniqueConstraint("assessment_id", "file_id"),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
        CheckConstraint(
            "status IN ('uploaded','extraction_review','teacher_review','approved','released')",
            name="valid_status",
        ),
        CheckConstraint("page_count BETWEEN 1 AND 30", name="page_limit"),
    )
    assessment_id: Mapped[UUID]
    student_id: Mapped[UUID]
    file_id: Mapped[UUID]
    rubric_id: Mapped[UUID]
    page_count: Mapped[int]
    status: Mapped[str] = mapped_column(String(30), default="uploaded")


class Extraction(Scoped, Base):
    __tablename__ = "extractions"
    __table_args__ = (
        submission_scope(),
        UniqueConstraint("submission_id", "version"),
        UniqueConstraint("submission_id", "id"),
    )
    submission_id: Mapped[UUID]
    version: Mapped[int]
    source: Mapped[str] = mapped_column(String(100))
    pages: Mapped[list] = mapped_column(JSONB)
    answers: Mapped[list] = mapped_column(JSONB, default=list)
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("chalkmate.users.id"))


class Proposal(Scoped, Base):
    __tablename__ = "proposals"
    __table_args__ = (
        submission_scope(),
        ForeignKeyConstraint(
            ["submission_id", "extraction_id"],
            ["chalkmate.extractions.submission_id", "chalkmate.extractions.id"],
        ),
        UniqueConstraint("submission_id", "id"),
    )
    submission_id: Mapped[UUID]
    extraction_id: Mapped[UUID]
    rubric_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.rubrics.id"))
    calibration_ids: Mapped[list] = mapped_column(JSONB, default=list)
    model: Mapped[str] = mapped_column(String(160))
    model_digest: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    output: Mapped[dict] = mapped_column(JSONB)
    usage: Mapped[dict] = mapped_column(JSONB, default=dict)


class Decision(Scoped, Base):
    __tablename__ = "decisions"
    __table_args__ = (
        submission_scope(),
        ForeignKeyConstraint(
            ["submission_id", "extraction_id"],
            ["chalkmate.extractions.submission_id", "chalkmate.extractions.id"],
        ),
        ForeignKeyConstraint(
            ["submission_id", "proposal_id"],
            ["chalkmate.proposals.submission_id", "chalkmate.proposals.id"],
        ),
        UniqueConstraint("submission_id", "id"),
        CheckConstraint("total >= 0 AND total <= maximum", name="score_bounds"),
    )
    submission_id: Mapped[UUID]
    extraction_id: Mapped[UUID]
    rubric_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.rubrics.id"))
    proposal_id: Mapped[UUID | None]
    approved_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    marks: Mapped[list] = mapped_column(JSONB)
    total: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    maximum: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    question_feedback: Mapped[dict] = mapped_column(JSONB, default=dict)
    feedback: Mapped[str] = mapped_column(String(8000))
    reason: Mapped[str] = mapped_column(String(2000))


class Release(Scoped, Base):
    __tablename__ = "releases"
    __table_args__ = (
        submission_scope(),
        ForeignKeyConstraint(
            ["submission_id", "decision_id"],
            ["chalkmate.decisions.submission_id", "chalkmate.decisions.id"],
        ),
        UniqueConstraint("submission_id", "decision_id"),
    )
    submission_id: Mapped[UUID]
    decision_id: Mapped[UUID]
    released_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))


class ProcessingJob(Scoped, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        submission_scope(),
        UniqueConstraint("submission_id", "kind", "input_version"),
        CheckConstraint("kind IN ('extract','grade')", name="valid_kind"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','canceled')", name="valid_status"
        ),
    )
    submission_id: Mapped[UUID]
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    input_version: Mapped[str] = mapped_column(String(80))
    calibration_ids: Mapped[list] = mapped_column(JSONB, default=list)
    model: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(500))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


for table in [
    Assessment,
    Rubric,
    Submission,
    Extraction,
    Proposal,
    Decision,
    Release,
    ProcessingJob,
]:
    Index(f"ix_{table.__tablename__}_class", table.classroom_id)


class QuestionReview(Scoped, Base):
    __tablename__ = "question_reviews"
    __table_args__ = (
        submission_scope(),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "rubric_id"],
            [
                "chalkmate.rubrics.workspace_id",
                "chalkmate.rubrics.classroom_id",
                "chalkmate.rubrics.id",
            ],
        ),
        ForeignKeyConstraint(
            ["submission_id", "extraction_id"],
            ["chalkmate.extractions.submission_id", "chalkmate.extractions.id"],
        ),
    )
    submission_id: Mapped[UUID]
    extraction_id: Mapped[UUID]
    rubric_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.rubrics.id"))
    question_id: Mapped[UUID]
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    marks: Mapped[list] = mapped_column(JSONB)
    feedback: Mapped[str] = mapped_column(String(4000))


class Calibration(Scoped, Base):
    __tablename__ = "calibrations"
    __table_args__ = (
        submission_scope(),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "rubric_id"],
            [
                "chalkmate.rubrics.workspace_id",
                "chalkmate.rubrics.classroom_id",
                "chalkmate.rubrics.id",
            ],
        ),
        ForeignKeyConstraint(
            ["submission_id", "extraction_id"],
            ["chalkmate.extractions.submission_id", "chalkmate.extractions.id"],
        ),
    )
    submission_id: Mapped[UUID]
    extraction_id: Mapped[UUID]
    rubric_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.rubrics.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    band: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(String(2000))
    snapshot: Mapped[dict] = mapped_column(JSONB)


class Reevaluation(Scoped, Base):
    __tablename__ = "reevaluations"
    __table_args__ = (
        submission_scope(),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "from_rubric_id"],
            [
                "chalkmate.rubrics.workspace_id",
                "chalkmate.rubrics.classroom_id",
                "chalkmate.rubrics.id",
            ],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "to_rubric_id"],
            [
                "chalkmate.rubrics.workspace_id",
                "chalkmate.rubrics.classroom_id",
                "chalkmate.rubrics.id",
            ],
            name="fk_reevaluations_workspace_id_rubrics_target",
        ),
    )
    submission_id: Mapped[UUID]
    from_rubric_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.rubrics.id"))
    to_rubric_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.rubrics.id"))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    reason: Mapped[str] = mapped_column(String(2000))


for table in [QuestionReview, Calibration, Reevaluation]:
    Index(f"ix_{table.__tablename__}_class", table.classroom_id)
