from datetime import datetime
from uuid import UUID, uuid4

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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from chalkmate.db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role IN ('owner','teacher','reviewer','student')", name="valid_role"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    role: Mapped[str] = mapped_column(String(20))


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("workspace_id", "id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.workspaces.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(120))
    term: Mapped[str] = mapped_column(String(80))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClassroomTeacher(Base):
    __tablename__ = "classroom_teachers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id"],
            ["chalkmate.classrooms.workspace_id", "chalkmate.classrooms.id"],
        ),
        UniqueConstraint("classroom_id", "user_id"),
        CheckConstraint("role IN ('teacher','reviewer')", name="valid_role"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID]
    classroom_id: Mapped[UUID]
    user_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    role: Mapped[str] = mapped_column(String(20))


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "registration_number"),
        UniqueConstraint("workspace_id", "user_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.workspaces.id"))
    registration_number: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(320))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("chalkmate.users.id"))


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "classroom_id", "student_id"),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id"],
            ["chalkmate.classrooms.workspace_id", "chalkmate.classrooms.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "student_id"],
            ["chalkmate.students.workspace_id", "chalkmate.students.id"],
        ),
        UniqueConstraint("classroom_id", "student_id"),
        CheckConstraint("status IN ('active','withdrawn')", name="valid_status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID]
    classroom_id: Mapped[UUID]
    student_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id"],
            ["chalkmate.classrooms.workspace_id", "chalkmate.classrooms.id"],
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID]
    classroom_id: Mapped[UUID]
    created_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    rows: Mapped[list] = mapped_column(JSONB)
    issues: Mapped[list] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id"],
            ["chalkmate.classrooms.workspace_id", "chalkmate.classrooms.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "student_id"],
            ["chalkmate.students.workspace_id", "chalkmate.students.id"],
        ),
        CheckConstraint("role IN ('teacher','reviewer','student')", name="valid_role"),
        CheckConstraint("(role = 'student') = (student_id IS NOT NULL)", name="student_target"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID]
    classroom_id: Mapped[UUID]
    student_id: Mapped[UUID | None]
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class StoredFile(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("workspace_id", "classroom_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id"],
            ["chalkmate.classrooms.workspace_id", "chalkmate.classrooms.id"],
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID]
    classroom_id: Mapped[UUID]
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    filename: Mapped[str] = mapped_column(String(180))
    object_path: Mapped[str] = mapped_column(String(250), unique=True)
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __mapper_args__ = {"eager_defaults": False}
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "classroom_id"],
            ["chalkmate.classrooms.workspace_id", "chalkmate.classrooms.id"],
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.workspaces.id"))
    classroom_id: Mapped[UUID | None]
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("chalkmate.users.id"))
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("ix_classrooms_scope", Classroom.workspace_id)
Index("ix_classroom_teachers_scope", ClassroomTeacher.user_id, ClassroomTeacher.classroom_id)
Index("ix_enrollments_scope", Enrollment.student_id, Enrollment.classroom_id)
Index("ix_import_batches_scope", ImportBatch.classroom_id)
Index("ix_invitations_scope", Invitation.email, Invitation.workspace_id)
Index("ix_files_scope", StoredFile.classroom_id)
Index("ix_audit_events_scope", AuditEvent.classroom_id, AuditEvent.created_at)
