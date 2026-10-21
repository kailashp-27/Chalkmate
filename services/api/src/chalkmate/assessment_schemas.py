from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chalkmate.schemas import Output

Mark = Annotated[Decimal, Field(ge=0, le=10000, decimal_places=2)]


class Criterion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    guidance: str = Field(default="", max_length=2000)
    label: str = Field(min_length=1, max_length=500)
    maximum: Mark


class Question(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    label: str = Field(min_length=1, max_length=30)
    prompt: str = Field(min_length=1, max_length=6000)
    accepted_alternatives: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        default_factory=list, max_length=20
    )
    model_answer: str = Field(default="", max_length=8000)
    maximum: Mark
    criteria: list[Criterion] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def check_total(self):
        if self.maximum <= 0 or sum(c.maximum for c in self.criteria) != self.maximum:
            raise ValueError("Criterion marks must add up to the positive question maximum")
        return self


class RubricInput(BaseModel):
    base_version: int | None = Field(default=None, ge=0)
    reason: str = Field(default="", max_length=2000)
    questions: list[Question] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def check_ids(self):
        ids = [q.id for q in self.questions] + [c.id for q in self.questions for c in q.criteria]
        if len(ids) != len(set(ids)) or sum(q.maximum for q in self.questions) > 10000:
            raise ValueError("Question/criterion IDs must be unique and total marks at most 10000")
        return self


class CriterionOutput(Criterion):
    id: UUID = Field(...)


class QuestionOutput(Question):
    id: UUID = Field(...)
    criteria: list[CriterionOutput]


class RubricOutput(Output):
    reason: str = ""
    id: UUID
    version: int
    questions: list[QuestionOutput]
    maximum: Decimal
    approved_at: datetime | None


class AssessmentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=140)
    instructions: str = Field(default="", max_length=4000)


class AssessmentOutput(Output):
    id: UUID
    classroom_id: UUID
    title: str
    instructions: str
    status: str
    rubric: RubricOutput | None
    draft_rubric: RubricOutput | None = None
    submission_count: int
    released_count: int


class AnswerMap(BaseModel):
    question_id: UUID
    text: str = Field(max_length=20000)
    page_from: int = Field(ge=1, le=30)
    page_to: int = Field(ge=1, le=30)
    readable: bool


class ExtractionInput(BaseModel):
    base_version: int = Field(ge=0)
    pages_complete: Literal[True]
    identity_confirmed: Literal[True]
    answers: list[AnswerMap] = Field(min_length=1, max_length=50)


class PageText(BaseModel):
    page: int
    text: str


class ExtractionOutput(Output):
    id: UUID
    version: int
    source: str
    pages: list[PageText]
    answers: list[AnswerMap]
    reviewed_by: UUID | None


class CriterionMark(BaseModel):
    criterion_id: UUID
    mark: Mark


class CriterionSuggestion(CriterionMark):
    question_id: UUID
    explanation: str = Field(max_length=2000)
    evidence_page: int = Field(ge=1, le=30)
    evidence_quote: str = Field(max_length=2000)


class Suggestion(BaseModel):
    criteria: list[CriterionSuggestion]
    feedback: str = Field(max_length=8000)
    review_reasons: list[str] = Field(default_factory=list, max_length=30)


class DecisionInput(BaseModel):
    question_review_ids: list[UUID] = Field(default_factory=list, max_length=50)
    extraction_id: UUID
    proposal_id: UUID | None = None
    marks: list[CriterionMark] = Field(min_length=1, max_length=1000)
    feedback: str = Field(min_length=1, max_length=8000)
    reason: str = Field(default="", max_length=2000)


class DecisionOutput(Output):
    question_feedback: dict[str, str] = Field(default_factory=dict)
    rubric_id: UUID
    id: UUID
    extraction_id: UUID
    proposal_id: UUID | None
    marks: list[CriterionMark]
    total: Decimal
    maximum: Decimal
    feedback: str
    reason: str
    created_at: datetime


class ProposalOutput(Output):
    calibration_ids: list[UUID]
    rubric_id: UUID
    id: UUID
    extraction_id: UUID
    model: str
    model_digest: str
    prompt_version: str
    output: Suggestion


class JobOutput(Output):
    calibration_ids: list[UUID]
    id: UUID
    kind: str
    model: str
    status: str
    attempts: int
    error: str | None


class QuestionReviewInput(BaseModel):
    extraction_id: UUID
    rubric_id: UUID
    base_review_id: UUID | None = None
    marks: list[CriterionMark] = Field(min_length=1, max_length=20)
    feedback: str = Field(min_length=1, max_length=4000)


class QuestionReviewOutput(Output):
    id: UUID
    extraction_id: UUID
    rubric_id: UUID
    question_id: UUID
    reviewed_by: UUID
    marks: list[CriterionMark]
    feedback: str
    created_at: datetime


class SubmissionOutput(Output):
    rubric: RubricOutput
    released_decision_id: UUID | None = None
    question_reviews: list[QuestionReviewOutput]
    id: UUID
    assessment_id: UUID
    student_id: UUID
    student_name: str
    registration_number: str
    file_id: UUID
    filename: str
    content_type: str
    page_count: int
    status: str
    extraction: ExtractionOutput | None
    proposal: ProposalOutput | None
    decision: DecisionOutput | None
    jobs: list[JobOutput]


class JobInput(BaseModel):
    calibration_ids: list[UUID] = Field(default_factory=list, max_length=10)
    kind: Literal["extract", "grade"]
    model: str | None = Field(default=None, max_length=160)


class SubmissionInput(BaseModel):
    student_id: UUID
    file_id: UUID
    identity_confirmed: Literal[True]


class ReleaseInput(BaseModel):
    decision_id: UUID


class ReleasedResult(BaseModel):
    question_feedback: dict[str, str] = Field(default_factory=dict)
    assessment_title: str
    submission_id: UUID
    total: Decimal
    maximum: Decimal
    feedback: str
    marks: list[CriterionMark]
    questions: list[QuestionOutput]
    released_at: datetime


class ProcessingStatus(BaseModel):
    available: bool
    models: list[str]
    grading_model: str
    vision_model: str
    detail: str


class ActivateInput(BaseModel):
    rubric_id: UUID


class DiffField(BaseModel):
    path: str
    before: str
    after: str


class RubricDiff(BaseModel):
    base_version: int
    candidate: RubricOutput
    changes: list[DiffField]
    affected_submissions: int


class ReevaluationInput(BaseModel):
    rubric_id: UUID
    base_extraction_version: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=2000)


class ReevaluationOutput(Output):
    id: UUID
    from_rubric_id: UUID
    to_rubric_id: UUID
    reason: str
    created_at: datetime


class ReleaseOutput(Output):
    id: UUID
    decision_id: UUID
    created_at: datetime


class ReviewHistory(BaseModel):
    decisions: list[DecisionOutput]
    releases: list[ReleaseOutput]
    reevaluations: list[ReevaluationOutput]
    rubrics: list[RubricOutput]
    extractions: list[ExtractionOutput]
    question_reviews: list[QuestionReviewOutput]


class CalibrationInput(BaseModel):
    extraction_id: UUID
    rubric_id: UUID
    proposal_id: UUID | None = None
    band: Literal["low", "middle", "high"]
    note: str = Field(min_length=3, max_length=2000)
    marks: list[CriterionMark] = Field(min_length=1, max_length=1000)


class CalibrationCriterion(BaseModel):
    criterion_id: UUID
    expected: Decimal
    observed: Decimal | None
    delta: Decimal | None


class CalibrationSnapshot(BaseModel):
    expected_total: Decimal
    observed_total: Decimal | None
    mean_absolute_error: Decimal | None
    criteria: list[CalibrationCriterion]
    model: str | None
    model_digest: str | None
    prompt_version: str | None
    answers: list[AnswerMap]


class CalibrationOutput(Output):
    id: UUID
    submission_id: UUID
    rubric_id: UUID
    extraction_id: UUID
    band: str
    note: str
    snapshot: CalibrationSnapshot
    created_at: datetime


class QueueItem(BaseModel):
    submission_id: UUID
    student_name: str
    registration_number: str
    status: str
    rubric_version: int
    latest_rubric_version: int
    reviewed_questions: int
    question_count: int
    failed_jobs: int
    reasons: list[str]
