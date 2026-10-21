"""Immutable classroom planning versions and bounded local generation jobs."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from chalkmate.assessment_models import Scoped, class_scope
from chalkmate.db import Base


class PlanningDocument(Scoped, Base):
    __tablename__ = "planning_documents"
    __table_args__ = (
        class_scope(),
        UniqueConstraint("classroom_id", "family_id", "version"),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
        CheckConstraint("version > 0", name="valid_version"),
    )
    family_id: Mapped[UUID]
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSONB)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))


class PlanningApproval(Scoped, Base):
    __tablename__ = "planning_approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "document_id"],
            [
                "chalkmate.planning_documents.workspace_id",
                "chalkmate.planning_documents.classroom_id",
                "chalkmate.planning_documents.id",
            ],
        ),
        UniqueConstraint("document_id"),
    )
    document_id: Mapped[UUID]
    approved_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))


class PlanningJob(Scoped, Base):
    __tablename__ = "planning_jobs"
    __table_args__ = (
        class_scope(),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "result_id"],
            [
                "chalkmate.planning_documents.workspace_id",
                "chalkmate.planning_documents.classroom_id",
                "chalkmate.planning_documents.id",
            ],
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','canceled')", name="valid_status"
        ),
        CheckConstraint(
            "attempts BETWEEN 0 AND 3 AND budget_attempts BETWEEN 1 AND 20", name="valid_attempts"
        ),
    )
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    model: Mapped[str] = mapped_column(String(160))
    model_digest: Mapped[str] = mapped_column(String(100), default="")
    request: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    budget_day: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    budget_attempts: Mapped[int] = mapped_column(Integer, default=1)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(500))
    result_id: Mapped[UUID | None]
    usage: Mapped[dict] = mapped_column(JSONB, default=dict)
