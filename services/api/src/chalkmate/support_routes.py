"""Scoped review requests and a read-only classroom task overview."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from chalkmate.auth import CurrentUser, Database
from chalkmate.routes import classroom
from chalkmate.support_models import ReviewRequest

router = APIRouter(prefix="/v1", tags=["classroom support"])


class ReviewRequestInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    submission_id: UUID
    question_id: UUID
    released_at: AwareDatetime
    reason: str = Field(min_length=10, max_length=2000)


class ReviewResponseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    response: str = Field(min_length=10, max_length=2000)


class ReviewRequestOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    submission_id: UUID
    question_id: UUID
    question_label: str
    student_label: str
    assessment_title: str
    reason: str
    response: str | None
    created_at: datetime
    resolved_at: datetime | None


class OverviewTask(BaseModel):
    label: str
    count: int
    destination: Literal["Assessments", "Assignments", "Follow-up", "Overview"]
    detail: str


class OverviewOutput(BaseModel):
    tasks: list[OverviewTask]


@router.get("/classrooms/{classroom_id}/review-requests", response_model=list[ReviewRequestOutput])
def requests(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id, staff=False)
    return list(
        db.scalars(
            select(ReviewRequest)
            .where(ReviewRequest.classroom_id == classroom_id)
            .order_by(ReviewRequest.created_at.desc(), ReviewRequest.id.desc())
        )
    )


@router.post(
    "/classrooms/{classroom_id}/review-requests",
    response_model=ReviewRequestOutput,
    status_code=201,
)
def request_review(classroom_id: UUID, body: ReviewRequestInput, db: Database, user: CurrentUser):
    classroom(db, classroom_id, staff=False, active=True)
    result = db.scalar(
        text("SELECT chalkmate.request_review(:cid,:sid,:qid,:released,:reason)"),
        {
            "cid": classroom_id,
            "sid": body.submission_id,
            "qid": body.question_id,
            "released": body.released_at,
            "reason": body.reason,
        },
    )
    if result is None:
        raise HTTPException(404, "Released question not found")
    if result == "stale":
        raise HTTPException(409, "A newer result was released. Refresh your feedback first.")
    if result == "duplicate":
        raise HTTPException(409, "You already requested review of this released question")
    return db.get(ReviewRequest, UUID(result))


@router.post("/review-requests/{request_id}/resolve", response_model=ReviewRequestOutput)
def resolve_request(request_id: UUID, body: ReviewResponseInput, db: Database, user: CurrentUser):
    item = db.get(ReviewRequest, request_id)
    if item is None:
        raise HTTPException(404, "Review request not found")
    classroom(db, item.classroom_id, edit=True, active=True)
    if not db.scalar(
        text("SELECT chalkmate.respond_review(:id,:reply)"),
        {"id": request_id, "reply": body.response},
    ):
        raise HTTPException(409, "This request already has a response. Refresh to read it.")
    db.refresh(item)
    return item


@router.get("/classrooms/{classroom_id}/overview", response_model=OverviewOutput)
def overview(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id)
    # Aggregate in the database under the caller's RLS identity. No answer/contact data.
    counts = (
        db.execute(
            text(
                """
        WITH active_papers AS (
          SELECT s.* FROM chalkmate.submissions s JOIN chalkmate.enrollments e
          ON e.classroom_id=s.classroom_id AND e.student_id=s.student_id
          WHERE s.classroom_id=:cid AND e.status='active'
        ), publications AS (
          SELECT DISTINCT ON (v.assignment_id) v.* FROM chalkmate.assignment_versions v
          JOIN chalkmate.assignments a ON a.id=v.assignment_id
          WHERE v.classroom_id=:cid AND v.published_at IS NOT NULL AND NOT a.closed
          ORDER BY v.assignment_id,v.version DESC
        )
        SELECT
        (SELECT count(*) FROM active_papers WHERE status IN
          ('uploaded','extraction_review','teacher_review')) AS grading,
        (SELECT count(*) FROM active_papers WHERE status='approved') AS release,
        (SELECT count(*) FROM chalkmate.processing_jobs j JOIN active_papers s
          ON s.id=j.submission_id WHERE j.status='failed') AS failed,
        (SELECT count(*) FROM chalkmate.review_requests
          WHERE classroom_id=:cid AND resolved_at IS NULL) AS requests,
        (SELECT count(*) FROM publications v JOIN chalkmate.assignment_audiences a
          ON a.assignment_version_id=v.id JOIN chalkmate.enrollments e
          ON e.classroom_id=v.classroom_id AND e.student_id=a.student_id
          WHERE e.status='active' AND v.due_at < now() AND NOT EXISTS (
            SELECT 1 FROM chalkmate.assignment_responses r
            WHERE r.assignment_version_id=v.id AND r.student_id=a.student_id)) AS missing,
        (SELECT count(*) FROM chalkmate.deliveries d JOIN chalkmate.campaigns c
          ON c.id=d.campaign_id WHERE d.classroom_id=:cid AND d.status='queued'
          AND NOT c.canceled AND c.scheduled_at > now()) AS scheduled,
        (SELECT count(*) FROM chalkmate.deliveries WHERE classroom_id=:cid
          AND status IN ('failed','held','uncertain')) AS delivery_attention
        """
            ),
            {"cid": classroom_id},
        )
        .mappings()
        .one()
    )
    items = [
        (
            "grading",
            "Papers to review",
            "Assessments",
            "Uploaded or awaiting extraction/mark review.",
        ),
        (
            "release",
            "Approved, unreleased",
            "Assessments",
            "Ready for your separate release action.",
        ),
        ("failed", "Processing failures", "Assessments", "Inspect errors before retrying a job."),
        ("requests", "Student review requests", "Overview", "Read the question and respond below."),
        (
            "missing",
            "Overdue responses",
            "Assignments",
            "Active audience, latest open publication; no response. Missing is not zero.",
        ),
        (
            "scheduled",
            "Scheduled messages",
            "Follow-up",
            "Previously approved messages queued for a future time.",
        ),
        (
            "delivery_attention",
            "Messages to check",
            "Follow-up",
            "Failed, held or uncertain delivery. Inspect before retrying.",
        ),
    ]
    return {
        "tasks": [
            {"label": label, "count": counts[key], "destination": destination, "detail": detail}
            for key, label, destination, detail in items
        ]
    }
