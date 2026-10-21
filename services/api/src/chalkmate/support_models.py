"""Student review requests pin the released decision; replies never change marks."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from chalkmate.assessment_models import Scoped, submission_scope
from chalkmate.db import Base


class ReviewRequest(Scoped, Base):
    __tablename__ = "review_requests"
    __table_args__ = (
        submission_scope(),
        ForeignKeyConstraint(
            ["submission_id", "decision_id"],
            ["chalkmate.decisions.submission_id", "chalkmate.decisions.id"],
        ),
        UniqueConstraint(
            "submission_id",
            "decision_id",
            "question_id",
            "requested_by",
            name="uq_review_request_release_question_actor",
        ),
        Index("ix_review_requests_class", "classroom_id"),
    )
    submission_id: Mapped[UUID]
    decision_id: Mapped[UUID]
    question_id: Mapped[UUID]
    question_label: Mapped[str] = mapped_column(String(100))
    student_label: Mapped[str] = mapped_column(String(400))
    assessment_title: Mapped[str] = mapped_column(String(140))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    reason: Mapped[str] = mapped_column(String(2000))
    response: Mapped[str | None] = mapped_column(String(2000))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("chalkmate.users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
