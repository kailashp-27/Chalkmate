from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal[
    "syllabus",
    "blueprint",
    "paper",
    "question_bank",
    "meeting",
    "announcement",
    "report_template",
    "report",
    "marks_template",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)


class Reference(Strict):
    source_id: str = Field(min_length=1, max_length=10)
    quote: str = Field(min_length=4, max_length=500)


class Topic(Strict):
    name: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=10, max_length=6000)


class Allocation(Strict):
    topic: str = Field(min_length=1, max_length=100)
    outcome: str = Field(min_length=1, max_length=300)
    question_type: Literal["short", "descriptive", "numerical", "mcq"] = "short"
    difficulty: Literal["foundation", "standard", "stretch"] = "standard"
    count: int = Field(ge=1, le=40)
    marks: Decimal = Field(gt=0, le=100, decimal_places=2)


class PlannedQuestion(Strict):
    topic: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=8, max_length=3000)
    marks: Decimal = Field(gt=0, le=100, decimal_places=2)
    solution: str = Field(min_length=1, max_length=4000)
    rubric: str = Field(min_length=1, max_length=2000)
    references: list[Reference] = Field(default_factory=list, max_length=5)


class MeetingAction(Strict):
    action: str = Field(min_length=1, max_length=500)
    owner: str = Field(default="Unassigned", max_length=100)
    deadline: str = Field(default="Not specified", max_length=100)


class ExportColumn(Strict):
    field: Literal[
        "registration_number",
        "name",
        "enrollment",
        "status",
        "total",
        "maximum",
        "percentage",
        "feedback",
    ]
    heading: str = Field(min_length=1, max_length=80)


class PlanningContent(Strict):
    text: str = Field(default="", max_length=18000)
    original: str = Field(default="", max_length=10000)
    topics: list[Topic] = Field(default_factory=list, max_length=30)
    total_marks: Decimal | None = Field(default=None, gt=0, le=1000, decimal_places=2)
    allocations: list[Allocation] = Field(default_factory=list, max_length=40)
    questions: list[PlannedQuestion] = Field(default_factory=list, max_length=40)
    actions: list[MeetingAction] = Field(default_factory=list, max_length=40)
    language: str = Field(default="English", min_length=1, max_length=80)
    export_columns: list[ExportColumn] = Field(default_factory=list, max_length=8)
    score_basis: Literal["released", "approved"] = "released"
    include_withdrawn: bool = False
    columns: list[
        Literal[
            "classroom",
            "students",
            "assessments",
            "approved_decisions",
            "assignments",
            "activity_events",
        ]
    ] = Field(default_factory=list, max_length=6)


class PlanningInput(Strict):
    kind: Kind
    title: str = Field(min_length=1, max_length=200)
    content: PlanningContent
    source_ids: list[UUID] = Field(default_factory=list, max_length=8)


class VersionInput(PlanningInput):
    base_version: int = Field(ge=1)


class PlanningOutput(Strict):
    id: UUID
    family_id: UUID
    version: int
    kind: Kind
    title: str
    content: PlanningContent
    sources: list[dict]
    created_at: datetime
    approved: bool
    latest: bool
    issues: list[str]


class GenerateInput(Strict):
    kind: Literal["paper", "question_bank", "meeting", "announcement"]
    title: str = Field(min_length=1, max_length=200)
    source_ids: list[UUID] = Field(default_factory=list, max_length=8)
    original: str = Field(default="", max_length=10000)
    guidance: str = Field(default="", max_length=1500)
    language: str = Field(default="English", min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    total_marks: Decimal | None = Field(default=None, gt=0, le=1000)


class MeetingDraft(Strict):
    text: str = Field(min_length=1, max_length=10000)
    actions: list[MeetingAction] = Field(default_factory=list, max_length=15)


class TranslationDraft(Strict):
    text: str = Field(min_length=1, max_length=10000)


class PaperDraft(Strict):
    text: str = Field(default="", max_length=2000)
    total_marks: Decimal | None = Field(default=None, gt=0, le=1000)
    questions: list[PlannedQuestion] = Field(min_length=1, max_length=20)


class JobOutput(Strict):
    id: UUID
    model: str
    model_digest: str
    status: str
    attempts: int
    error: str | None
    result_id: UUID | None
    usage: dict
    created_at: datetime


class CommandInput(Strict):
    text: str = Field(min_length=1, max_length=300)


class CommandOutput(Strict):
    destination: str | None
    label: str
    explanation: str


class ReadinessOutput(Strict):
    queued: int
    failed: int
    expired: int
    attempts_today: int
    daily_limit: int
    generated_tokens: int
    pilot_status: str
    services: list["ServiceCheck"] = Field(default_factory=list)
    recovery: "RecoveryStatus | None" = None


class ServiceCheck(Strict):
    name: str
    state: Literal["ready", "unavailable", "optional"]
    detail: str


class RecoveryStatus(Strict):
    verified: bool
    verified_at: datetime | None


ReadinessOutput.model_rebuild()
