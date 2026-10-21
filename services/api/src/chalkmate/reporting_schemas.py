from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from chalkmate.planning_schemas import ExportColumn, Strict


class ExportRequest(Strict):
    template_id: UUID


class ExportRow(Strict):
    registration_number: str
    name: str
    enrollment: str
    status: str
    total: Decimal | None
    maximum: Decimal | None
    percentage: Decimal | None
    feedback: str
    decision_id: UUID | None
    rubric_id: UUID | None


class ExportSnapshot(Strict):
    assessment_title: str
    template_title: str
    template_version: int
    score_basis: str
    include_withdrawn: bool
    columns: list[ExportColumn]
    rows: list[ExportRow]


class ExportOutput(Strict):
    id: UUID
    assessment_id: UUID
    template_id: UUID
    created_at: datetime
    digest: str
    snapshot: ExportSnapshot


class LinkInput(Strict):
    question_index: int = Field(ge=0, le=39)
    assessment_id: UUID
    rubric_id: UUID
    question_id: UUID
    base_link_id: UUID | None = None
    disposition: Literal["linked", "revoked"] = "linked"
    reason: str = Field(min_length=3, max_length=1000)


class LinkOutput(Strict):
    id: UUID
    question_index: int
    assessment_id: UUID
    assessment_title: str
    rubric_id: UUID
    question_id: UUID
    disposition: str
    reason: str
    created_at: datetime
    stale: bool
    reviewed: int
    maximum: Decimal | None
    average: Decimal | None
    full_credit: int
    partial_credit: int
    zero_credit: int


class ReuseOutput(Strict):
    id: UUID
    title: str
    kind: str
    version: int
    approved: bool


class PerformanceOutput(Strict):
    links: list[LinkOutput]
    history: list[LinkOutput]
    reused_by: list[ReuseOutput]
