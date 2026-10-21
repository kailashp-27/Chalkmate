"""Versioned teacher review, calibration snapshots, and safe re-evaluation."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from chalkmate import assessment_models as m
from chalkmate import assessment_schemas as s
from chalkmate.assessment_routes import assessment, rubric_for, submission, submission_output
from chalkmate.assessment_rules import latest, validate_marks
from chalkmate.auth import CurrentUser, Database
from chalkmate.routes import audit

router = APIRouter(prefix="/v1")


def changes(before, after, path=""):
    """Stable field-level diff. IDs keep reordered questions/criteria aligned."""
    result = []
    if (
        (isinstance(before, dict) or before is None)
        and (isinstance(after, dict) or after is None)
        and (before is not None or after is not None)
    ):
        before, after = before or {}, after or {}
        for key in sorted((before.keys() | after.keys()) - {"id"}):
            result.extend(changes(before.get(key), after.get(key), f"{path}.{key}".strip(".")))
    elif (
        isinstance(before, list)
        and isinstance(after, list)
        and all(isinstance(item, dict) and "id" in item for item in before + after)
    ):
        old, new = {x["id"]: x for x in before}, {x["id"]: x for x in after}
        for key in dict.fromkeys([*old, *new]):
            label = (new.get(key) or old[key]).get("label", key)
            result.extend(changes(old.get(key), new.get(key), f"{path}.{label}"))
        if list(old) != list(new) and old.keys() == new.keys():
            result.append(
                {"path": f"{path}.order", "before": str(list(old)), "after": str(list(new))}
            )
    elif before != after:
        result.append(
            {
                "path": path,
                "before": str(before) if before is not None else "—",
                "after": str(after) if after is not None else "—",
            }
        )
    return result


@router.get("/assessments/{assessment_id}/rubrics", response_model=list[s.RubricOutput])
def rubric_versions(assessment_id: UUID, db: Database, user: CurrentUser):
    assessment(db, assessment_id)
    return list(
        db.scalars(
            select(m.Rubric)
            .where(m.Rubric.assessment_id == assessment_id)
            .order_by(m.Rubric.version.desc())
        )
    )


@router.get("/assessments/{assessment_id}/rubrics/{rubric_id}/diff", response_model=s.RubricDiff)
def rubric_diff(assessment_id: UUID, rubric_id: UUID, db: Database, user: CurrentUser):
    record = assessment(db, assessment_id)
    candidate = db.get(m.Rubric, rubric_id)
    if not candidate or candidate.assessment_id != record.id:
        raise HTTPException(404, "Rubric not found")
    base = db.scalar(
        select(m.Rubric)
        .where(
            m.Rubric.assessment_id == record.id,
            m.Rubric.version < candidate.version,
            m.Rubric.approved_at.is_not(None),
        )
        .order_by(m.Rubric.version.desc())
        .limit(1)
    )
    papers = list(
        db.scalars(
            select(m.Submission).where(
                m.Submission.assessment_id == record.id, m.Submission.rubric_id != candidate.id
            )
        )
    )
    return {
        "base_version": base.version if base else 0,
        "candidate": candidate,
        "changes": changes(base.questions if base else [], candidate.questions, "questions"),
        "affected_submissions": len(papers),
    }


@router.post("/submissions/{submission_id}/reevaluate", response_model=s.SubmissionOutput)
def reevaluate(submission_id: UUID, body: s.ReevaluationInput, db: Database, user: CurrentUser):
    original = submission(db, submission_id)
    parent = assessment(db, original.assessment_id, edit=True)
    record = db.scalar(
        select(m.Submission).where(m.Submission.id == submission_id).with_for_update()
    )
    db.refresh(record)
    target = rubric_for(db, parent)
    previous = latest(db, m.Extraction, record.id)
    if not body.reason.strip() or len(body.reason.strip()) < 3:
        raise HTTPException(422, "Explain why this paper needs re-evaluation")
    if not target or target.id != body.rubric_id or not target.approved_at:
        raise HTTPException(409, "Choose the current approved rubric for re-evaluation")
    if body.base_extraction_version != (previous.version if previous else 0):
        raise HTTPException(409, "The paper changed. Refresh before re-evaluating.")
    if record.status not in ("approved", "released") and record.rubric_id == target.id:
        raise HTTPException(409, "This paper is already awaiting review with this rubric")
    if previous:
        known = {q["id"] for q in target.questions}
        db.add(
            m.Extraction(
                workspace_id=record.workspace_id,
                classroom_id=record.classroom_id,
                submission_id=record.id,
                version=previous.version + 1,
                source="re-evaluation",
                pages=previous.pages,
                answers=[a for a in previous.answers if a["question_id"] in known],
                reviewed_by=None,
            )
        )
    db.add(
        m.Reevaluation(
            workspace_id=record.workspace_id,
            classroom_id=record.classroom_id,
            submission_id=record.id,
            from_rubric_id=record.rubric_id,
            to_rubric_id=target.id,
            requested_by=user.id,
            reason=body.reason.strip(),
        )
    )
    record.rubric_id, record.status = target.id, "extraction_review" if previous else "uploaded"
    for job in db.scalars(
        select(m.ProcessingJob).where(
            m.ProcessingJob.submission_id == record.id,
            m.ProcessingJob.status.in_(["queued", "running"]),
        )
    ):
        job.status = "canceled"
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "review.reopened",
        record.classroom_id,
        submission_id=str(record.id),
        rubric_id=str(target.id),
        reason=body.reason.strip(),
    )
    return submission_output(db, record)


@router.post(
    "/submissions/{submission_id}/questions/{question_id}/reviews",
    response_model=s.QuestionReviewOutput,
    status_code=201,
)
def save_question_review(
    submission_id: UUID,
    question_id: UUID,
    body: s.QuestionReviewInput,
    db: Database,
    user: CurrentUser,
):
    record = submission(db, submission_id, edit=True)
    extraction = latest(db, m.Extraction, record.id)
    if (
        not extraction
        or not extraction.reviewed_by
        or extraction.id != body.extraction_id
        or body.rubric_id != record.rubric_id
    ):
        raise HTTPException(
            409, "Review the current extraction and rubric before saving question marks"
        )
    rubric = db.get(m.Rubric, record.rubric_id)
    question = next((q for q in rubric.questions if q["id"] == str(question_id)), None)
    if not question:
        raise HTTPException(404, "Question not found")
    previous = db.scalar(
        select(m.QuestionReview)
        .where(
            m.QuestionReview.submission_id == record.id,
            m.QuestionReview.question_id == question_id,
            m.QuestionReview.extraction_id == extraction.id,
            m.QuestionReview.rubric_id == rubric.id,
        )
        .order_by(m.QuestionReview.created_at.desc(), m.QuestionReview.id.desc())
        .limit(1)
    )
    if body.base_review_id != (previous.id if previous else None):
        raise HTTPException(409, "This question review changed. Refresh before saving.")
    marks = body.model_dump(mode="json")["marks"]
    validate_marks([question], marks)
    if not body.feedback.strip():
        raise HTTPException(422, "Add feedback for this question")
    item = m.QuestionReview(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        submission_id=record.id,
        extraction_id=extraction.id,
        rubric_id=rubric.id,
        question_id=question_id,
        reviewed_by=user.id,
        marks=marks,
        feedback=body.feedback.strip(),
    )
    db.add(item)
    record.status = "teacher_review"
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "question.reviewed",
        record.classroom_id,
        submission_id=str(record.id),
        question_id=str(question_id),
        review_id=str(item.id),
    )
    return item


@router.get("/submissions/{submission_id}/history", response_model=s.ReviewHistory)
def review_history(submission_id: UUID, db: Database, user: CurrentUser):
    record = submission(db, submission_id)

    def records(model):
        return list(
            db.scalars(
                select(model)
                .where(model.submission_id == record.id)
                .order_by(model.created_at.desc(), model.id.desc())
            )
        )

    return {
        "decisions": records(m.Decision),
        "releases": records(m.Release),
        "reevaluations": records(m.Reevaluation),
        "rubrics": list(
            db.scalars(
                select(m.Rubric)
                .where(m.Rubric.assessment_id == record.assessment_id)
                .order_by(m.Rubric.version.desc())
            )
        ),
        "extractions": records(m.Extraction),
        "question_reviews": records(m.QuestionReview),
    }


@router.get("/assessments/{assessment_id}/review-queue", response_model=list[s.QueueItem])
def review_queue(assessment_id: UUID, db: Database, user: CurrentUser):
    parent = assessment(db, assessment_id)
    rubric = rubric_for(db, parent)
    entries = []
    for record in db.scalars(
        select(m.Submission)
        .where(m.Submission.assessment_id == parent.id)
        .order_by(m.Submission.created_at)
    ):
        paper = submission_output(db, record)
        failed = sum(j.status == "failed" for j in paper["jobs"])
        stale = bool(rubric and rubric.id != record.rubric_id)
        reasons = []
        if stale:
            reasons.append("New approved rubric available")
        if failed:
            reasons.append("Processing needs attention")
        if not paper["extraction"] or not paper["extraction"].reviewed_by:
            reasons.append("Extraction needs review")
        elif record.status == "teacher_review":
            reasons.append("Question marks need approval")
        if record.status == "approved":
            reasons.append("Ready for release")
        entries.append(
            {
                "submission_id": record.id,
                "student_name": paper["student_name"],
                "registration_number": paper["registration_number"],
                "status": record.status,
                "rubric_version": paper["rubric"].version,
                "latest_rubric_version": rubric.version if rubric else 0,
                "reviewed_questions": len(paper["question_reviews"]),
                "question_count": len(paper["rubric"].questions),
                "failed_jobs": failed,
                "reasons": reasons,
            }
        )
    priority = {
        "uploaded": 0,
        "extraction_review": 0,
        "teacher_review": 1,
        "approved": 2,
        "released": 3,
    }
    return sorted(
        entries,
        key=lambda item: (
            0 if item["failed_jobs"] else 1,
            priority.get(item["status"], 1),
            item["registration_number"],
        ),
    )


@router.post(
    "/submissions/{submission_id}/calibrations", response_model=s.CalibrationOutput, status_code=201
)
def save_calibration(
    submission_id: UUID, body: s.CalibrationInput, db: Database, user: CurrentUser
):
    record = submission(db, submission_id)
    # Capturing references does not rewrite released results, but requires editing permission.
    assessment(db, record.assessment_id, edit=True)
    db.execute(select(m.Submission.id).where(m.Submission.id == record.id).with_for_update())
    db.refresh(record)
    extraction = latest(db, m.Extraction, record.id)
    if (
        not extraction
        or not extraction.reviewed_by
        or extraction.id != body.extraction_id
        or body.rubric_id != record.rubric_id
    ):
        raise HTTPException(409, "Use the current reviewed extraction and rubric for calibration")
    rubric = db.get(m.Rubric, record.rubric_id)
    marks = body.model_dump(mode="json")["marks"]
    expected_total = validate_marks(rubric.questions, marks)
    proposal = db.get(m.Proposal, body.proposal_id) if body.proposal_id else None
    if body.proposal_id and (
        not proposal
        or proposal.submission_id != record.id
        or proposal.extraction_id != extraction.id
        or proposal.rubric_id != rubric.id
    ):
        raise HTTPException(409, "The calibration proposal is stale or belongs to another paper")
    observed = (
        {x["criterion_id"]: Decimal(x["mark"]) for x in proposal.output["criteria"]}
        if proposal
        else {}
    )
    criteria = []
    for mark in marks:
        expected = Decimal(mark["mark"])
        value = observed.get(mark["criterion_id"])
        criteria.append(
            {
                "criterion_id": mark["criterion_id"],
                "expected": str(expected),
                "observed": str(value) if value is not None else None,
                "delta": str(value - expected) if value is not None else None,
            }
        )
    error = sum(abs(Decimal(c["delta"])) for c in criteria) / len(criteria) if observed else None
    snapshot = {
        "expected_total": str(expected_total),
        "observed_total": str(sum(observed.values())) if observed else None,
        "mean_absolute_error": str(error.quantize(Decimal("0.0001")))
        if error is not None
        else None,
        "criteria": criteria,
        "model": proposal.model if proposal else None,
        "model_digest": proposal.model_digest if proposal else None,
        "prompt_version": proposal.prompt_version if proposal else None,
        "answers": extraction.answers,
    }
    item = m.Calibration(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        submission_id=record.id,
        extraction_id=extraction.id,
        rubric_id=rubric.id,
        created_by=user.id,
        band=body.band,
        note=body.note,
        snapshot=snapshot,
    )
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "calibration.captured",
        record.classroom_id,
        calibration_id=str(item.id),
        rubric_id=str(rubric.id),
    )
    return item


@router.get("/assessments/{assessment_id}/calibrations", response_model=list[s.CalibrationOutput])
def list_calibrations(assessment_id: UUID, db: Database, user: CurrentUser):
    assessment(db, assessment_id)
    return list(
        db.scalars(
            select(m.Calibration)
            .join(m.Submission, m.Submission.id == m.Calibration.submission_id)
            .where(m.Submission.assessment_id == assessment_id)
            .order_by(m.Calibration.created_at.desc())
        )
    )
