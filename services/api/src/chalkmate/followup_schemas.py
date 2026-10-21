from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, model_validator

from chalkmate.schemas import Output

Money = Annotated[Decimal, Field(ge=0, le=10000, decimal_places=2)]


class AssignmentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    base_version: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=160)
    instructions: str = Field(min_length=1, max_length=20000)
    due_at: AwareDatetime | None = None
    reason: str = Field(default="", max_length=2000)


class AssignmentVersionOutput(Output):
    id: UUID
    assignment_id: UUID
    classroom_id: UUID
    version: int
    title: str
    instructions: str
    due_at: datetime | None
    published_at: datetime | None
    reason: str


class AssignmentOutput(BaseModel):
    id: UUID
    classroom_id: UUID
    closed: bool
    version: AssignmentVersionOutput
    draft: AssignmentVersionOutput | None
    audience_count: int
    response_count: int
    own_response_version: int
    can_edit: bool
    is_staff: bool
    can_submit: bool


class PublishAssignment(BaseModel):
    student_ids: list[UUID] | None = Field(default=None, max_length=2000)


class AssignmentState(BaseModel):
    closed: bool


class ResponseOutput(Output):
    id: UUID
    assignment_version_id: UUID
    student_id: UUID
    student_name: str
    version: int
    text: str
    filename: str | None
    content_type: str | None
    late: bool
    created_at: datetime


class ScoreRule(BaseModel):
    assessment_id: UUID
    operator: Literal["lt", "lte", "eq", "gte", "gt"] = "lt"
    threshold: Money
    maximum: Annotated[Decimal, Field(gt=0, le=10000, decimal_places=2)]

    @model_validator(mode="after")
    def valid_threshold(self):
        if self.threshold > self.maximum:
            raise ValueError("Score threshold cannot exceed the stated maximum")
        return self


class ContactInput(BaseModel):
    email: EmailStr | None


class PreviewInput(BaseModel):
    assignment_version_id: UUID
    rule: ScoreRule
    subject: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=12000)
    include_score: bool = False
    skip_submitted: bool = False
    exclude_student_ids: list[UUID] = Field(default_factory=list, max_length=2000)


class RecipientPreview(BaseModel):
    student_id: UUID
    student_name: str
    registration_number: str
    email: str | None
    decision_id: UUID | None
    total: Decimal | None
    maximum: Decimal | None
    eligible: bool
    excluded: bool
    blocked: bool
    reason: str


class PreviewSnapshot(BaseModel):
    assignment_title: str
    assignment_version: int
    rows: list[RecipientPreview]
    eligible_count: int
    selected_count: int
    blocked_count: int


class PreviewOutput(Output):
    id: UUID
    digest: str
    expires_at: datetime
    request: PreviewInput
    snapshot: PreviewSnapshot


class PersonalMessage(BaseModel):
    student_id: UUID
    to: str
    subject: str
    text: str
    assignment_link: str


class ApproveCampaign(BaseModel):
    preview_id: UUID
    digest: str = Field(min_length=64, max_length=64)
    scheduled_at: AwareDatetime | None = None


class CampaignOutput(Output):
    id: UUID
    assignment_version_id: UUID
    scheduled_at: datetime
    provider: str
    canceled: bool
    created_at: datetime
    request: PreviewInput
    counts: dict[str, int]


class DeliveryOutput(Output):
    id: UUID
    student_id: UUID
    student_name: str
    email: str
    status: str
    attempts: int
    provider_id: str | None
    detail: str
    created_at: datetime


class AttemptOutput(Output):
    id: UUID
    outcome: str
    detail: str
    provider_id: str | None
    created_at: datetime


class MailStatus(BaseModel):
    provider: str
    available: bool
    external: bool
    detail: str
    inbox_url: str | None
