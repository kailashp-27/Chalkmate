from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)


class WorkspaceOutput(Output):
    id: UUID
    name: str
    role: str


class SessionOutput(Output):
    id: UUID
    email: str
    workspaces: list[WorkspaceOutput]


class ClassroomInput(WorkspaceInput):
    subject: str = Field(min_length=1, max_length=120)
    term: str = Field(min_length=1, max_length=80)


class ClassroomUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    subject: str | None = Field(default=None, min_length=1, max_length=120)
    term: str | None = Field(default=None, min_length=1, max_length=80)
    archived: bool | None = None


class ClassroomOutput(Output):
    id: UUID
    workspace_id: UUID
    name: str
    subject: str
    term: str
    archived: bool
    can_edit: bool
    role: str
    student_count: int


class StudentOutput(Output):
    id: UUID
    enrollment_id: UUID
    registration_number: str
    name: str
    email: str | None
    status: str
    linked: bool


class EnrollmentUpdate(BaseModel):
    status: Literal["active", "withdrawn"]


class RosterRow(BaseModel):
    row: int
    registration_number: str
    name: str
    email: str | None


class ImportIssue(BaseModel):
    row: int
    severity: Literal["error", "warning"]
    message: str


class ImportOutput(Output):
    id: UUID
    rows: list[RosterRow]
    issues: list[ImportIssue]
    expires_at: datetime
    confirmed_at: datetime | None


class ImportResult(BaseModel):
    imported: int


class InvitationInput(BaseModel):
    email: EmailStr
    role: Literal["teacher", "reviewer", "student"]
    student_id: UUID | None = None


class InvitationOutput(Output):
    id: UUID
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    revoked: bool


class InvitationCreated(InvitationOutput):
    url: str


class AcceptInvitation(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class AcceptedInvitation(BaseModel):
    workspace_id: UUID
    classroom_id: UUID
    role: str


class FileOutput(Output):
    id: UUID
    filename: str
    content_type: str
    size: int
    checksum: str
    created_at: datetime


class DownloadOutput(BaseModel):
    url: str
    expires_in: int


class AuditOutput(Output):
    id: UUID
    action: str
    details: dict
    created_at: datetime
