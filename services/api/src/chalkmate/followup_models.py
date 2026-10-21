"""Class-scoped assignments, immutable communication approvals, and durable delivery."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
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

from chalkmate.assessment_models import Scoped, class_scope
from chalkmate.db import Base


def assignment_scope():
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id", "assignment_id"],
        [
            "chalkmate.assignments.workspace_id",
            "chalkmate.assignments.classroom_id",
            "chalkmate.assignments.id",
        ],
    )


def version_scope():
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id", "assignment_version_id"],
        [
            "chalkmate.assignment_versions.workspace_id",
            "chalkmate.assignment_versions.classroom_id",
            "chalkmate.assignment_versions.id",
        ],
    )


def enrollment_scope():
    return ForeignKeyConstraint(
        ["workspace_id", "classroom_id", "student_id"],
        [
            "chalkmate.enrollments.workspace_id",
            "chalkmate.enrollments.classroom_id",
            "chalkmate.enrollments.student_id",
        ],
    )


class Assignment(Scoped, Base):
    __tablename__ = "assignments"
    __table_args__ = (class_scope(), UniqueConstraint("workspace_id", "classroom_id", "id"))
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))


class AssignmentVersion(Scoped, Base):
    __tablename__ = "assignment_versions"
    __table_args__ = (
        assignment_scope(),
        UniqueConstraint("assignment_id", "version"),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
    )
    assignment_id: Mapped[UUID]
    version: Mapped[int]
    title: Mapped[str] = mapped_column(String(160))
    instructions: Mapped[str] = mapped_column(String(20000))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(2000), default="")


class AssignmentAudience(Scoped, Base):
    __tablename__ = "assignment_audiences"
    __table_args__ = (
        version_scope(),
        enrollment_scope(),
        UniqueConstraint("assignment_version_id", "student_id"),
    )
    assignment_version_id: Mapped[UUID]
    student_id: Mapped[UUID]


class AssignmentResponse(Scoped, Base):
    __tablename__ = "assignment_responses"
    __table_args__ = (
        version_scope(),
        enrollment_scope(),
        UniqueConstraint("assignment_version_id", "student_id", "version"),
    )
    assignment_version_id: Mapped[UUID]
    student_id: Mapped[UUID]
    version: Mapped[int]
    text: Mapped[str] = mapped_column(String(20000))
    file_path: Mapped[str | None] = mapped_column(String(350))
    filename: Mapped[str | None] = mapped_column(String(180))
    content_type: Mapped[str | None] = mapped_column(String(80))
    late: Mapped[bool] = mapped_column(Boolean)


class CampaignPreview(Scoped, Base):
    __tablename__ = "campaign_previews"
    __table_args__ = (version_scope(), UniqueConstraint("workspace_id", "classroom_id", "id"))
    assignment_version_id: Mapped[UUID]
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    request: Mapped[dict] = mapped_column(JSONB)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Campaign(Scoped, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        version_scope(),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "preview_id"],
            [
                "chalkmate.campaign_previews.workspace_id",
                "chalkmate.campaign_previews.classroom_id",
                "chalkmate.campaign_previews.id",
            ],
        ),
        UniqueConstraint("preview_id"),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
    )
    assignment_version_id: Mapped[UUID]
    preview_id: Mapped[UUID]
    approved_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    request: Mapped[dict] = mapped_column(JSONB)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(20))
    canceled: Mapped[bool] = mapped_column(Boolean, default=False)


class Delivery(Scoped, Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "campaign_id"],
            [
                "chalkmate.campaigns.workspace_id",
                "chalkmate.campaigns.classroom_id",
                "chalkmate.campaigns.id",
            ],
        ),
        enrollment_scope(),
        UniqueConstraint("campaign_id", "student_id"),
        UniqueConstraint("provider_id"),
        UniqueConstraint("workspace_id", "classroom_id", "id"),
        CheckConstraint(
            "status IN ('queued','sending','captured','accepted','delivered','bounced',"
            "'failed','held','skipped','uncertain','canceled')",
            name="valid_status",
        ),
    )
    campaign_id: Mapped[UUID]
    student_id: Mapped[UUID]
    snapshot: Mapped[dict] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    first_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_id: Mapped[str | None] = mapped_column(String(180))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[str] = mapped_column(String(500), default="")


class DeliveryAttempt(Scoped, Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id", "delivery_id"],
            [
                "chalkmate.deliveries.workspace_id",
                "chalkmate.deliveries.classroom_id",
                "chalkmate.deliveries.id",
            ],
        ),
    )
    delivery_id: Mapped[UUID]
    outcome: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(String(500))
    provider_id: Mapped[str | None] = mapped_column(String(180))


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"
    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


for model in [
    Assignment,
    AssignmentVersion,
    AssignmentAudience,
    AssignmentResponse,
    CampaignPreview,
    Campaign,
    Delivery,
    DeliveryAttempt,
]:
    Index(f"ix_{model.__tablename__}_class", model.classroom_id)
