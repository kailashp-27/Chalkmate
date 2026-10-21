"""Contracts shared by local model validation, routes, and generated browser types."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from chalkmate.schemas import Output

Text = Annotated[str, Field(min_length=1, max_length=3000)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Citation(Strict):
    source_id: str = Field(min_length=1, max_length=12)
    quote: str = Field(min_length=1, max_length=1000)
    page: int = Field(ge=1, le=30)


class Finding(Strict):
    title: str = Field(min_length=3, max_length=160)
    explanation: Text
    kind: Literal["misconception", "strength", "needs_practice"]
    citations: list[Citation] = Field(min_length=1, max_length=30)
    suggested_action: Text


class AnalysisResult(Strict):
    findings: list[Finding] = Field(max_length=6)
    limitations: str = Field(min_length=3, max_length=2000)


class MaterialItem(Strict):
    question: Text
    hint: str = Field(max_length=1000)
    answer: Text
    rationale: str = Field(min_length=1, max_length=2000)


class MaterialContent(Strict):
    title: str = Field(min_length=3, max_length=160)
    introduction: Text
    objectives: list[Annotated[str, Field(min_length=3, max_length=400)]] = Field(
        min_length=1, max_length=6
    )
    revision_notes: list[Annotated[str, Field(min_length=3, max_length=2000)]] = Field(max_length=8)
    items: list[MaterialItem] = Field(min_length=1, max_length=8)


class AnalysisInput(Strict):
    model: str | None = Field(default=None, min_length=1, max_length=160)
    question_id: UUID
    topic: str = Field(min_length=3, max_length=160)
    student_ids: list[UUID] | None = Field(default=None, max_length=30)
    manual_result: AnalysisResult | None = None


class FindingReviewInput(Strict):
    base_version: int = Field(ge=0)
    disposition: Literal["accepted", "dismissed"]
    reason: str = Field(min_length=3, max_length=2000)


class GenerateInput(Strict):
    model: str | None = Field(default=None, min_length=1, max_length=160)
    source_run_id: UUID
    review_ids: list[UUID] = Field(min_length=1, max_length=6)
    material_type: Literal["remedial", "revision"]
    guidance: str = Field(default="", max_length=1500)
    manual_content: MaterialContent | None = None


class MaterialEdit(Strict):
    base_version: int = Field(ge=1)
    content: MaterialContent
    reason: str = Field(min_length=3, max_length=2000)


class MaterialApprove(Strict):
    base_version: int = Field(ge=1)
    confirmed: Literal[True]
    reason: str = Field(min_length=3, max_length=2000)


class TopicSummary(BaseModel):
    question_id: UUID
    label: str
    prompt: str
    maximum: Decimal
    reviewed: int
    analyzable: int
    unreadable: int
    blank: int
    full_credit: int
    partial_credit: int
    zero_credit: int
    average: Decimal | None


class SummaryOutput(BaseModel):
    assessment_id: UUID
    rubric_id: UUID | None
    rubric_version: int | None
    active_students: int
    missing: int
    unapproved: int
    rubric_mismatch: int
    withdrawn: int
    topics: list[TopicSummary]


class EvidenceSource(BaseModel):
    source_id: str
    student_id: UUID
    student_name: str
    submission_id: UUID
    decision_id: UUID
    extraction_id: UUID
    text: str
    page_from: int
    page_to: int
    mark: Decimal
    maximum: Decimal


class ReviewOutput(Output):
    id: UUID
    finding_index: int
    version: int
    disposition: str
    reason: str
    created_at: datetime


class RunOutput(Output):
    id: UUID
    assessment_id: UUID
    rubric_id: UUID
    kind: str
    model: str
    model_digest: str
    prompt_version: str
    request: dict
    input_digest: str
    status: str
    attempts: int
    error: str | None
    created_at: datetime
    result: dict | None
    usage: dict
    stale: bool
    stale_reason: str
    sources: list[EvidenceSource]
    reviews: list[ReviewOutput]


class MaterialOutput(Output):
    id: UUID
    run_id: UUID
    classroom_id: UUID
    version: int
    content: MaterialContent
    reason: str
    created_at: datetime
    approval_assignment_version_id: UUID | None
    stale: bool
    stale_reason: str


class ApprovalOutput(Output):
    id: UUID
    material_id: UUID
    assignment_version_id: UUID
    created_at: datetime
