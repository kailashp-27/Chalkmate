"""Private immutable export snapshots and explicit, append-only question links."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from chalkmate.assessment_models import Scoped, assessment_scope
from chalkmate.db import Base


def document_scope(column):
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id", column],
        [
            "chalkmate.planning_documents.workspace_id",
            "chalkmate.planning_documents.classroom_id",
            "chalkmate.planning_documents.id",
        ],
    )


class MarksExport(Scoped, Base):
    __tablename__ = "marks_exports"
    __table_args__ = (assessment_scope(), document_scope("template_id"))
    assessment_id: Mapped[UUID]
    template_id: Mapped[UUID]
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))


class QuestionLink(Scoped, Base):
    __tablename__ = "question_links"
    __table_args__ = (
        assessment_scope(),
        document_scope("document_id"),
        UniqueConstraint("document_id", "version"),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "rubric_id"],
            [
                "chalkmate.rubrics.workspace_id",
                "chalkmate.rubrics.classroom_id",
                "chalkmate.rubrics.id",
            ],
        ),
        ForeignKeyConstraint(
            ["assessment_id", "rubric_id"],
            ["chalkmate.rubrics.assessment_id", "chalkmate.rubrics.id"],
        ),
        CheckConstraint("disposition IN ('linked','revoked')", name="valid_disposition"),
        CheckConstraint("question_index BETWEEN 0 AND 39", name="valid_index"),
    )
    document_id: Mapped[UUID]
    version: Mapped[int] = mapped_column(Integer)
    question_index: Mapped[int] = mapped_column(Integer)
    assessment_id: Mapped[UUID]
    rubric_id: Mapped[UUID]
    question_id: Mapped[UUID]
    disposition: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
