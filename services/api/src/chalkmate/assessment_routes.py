import csv
import hashlib
import io
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from openpyxl import Workbook
from sqlalchemy import func, select, text

from chalkmate import assessment_models as m
from chalkmate import assessment_schemas as s
from chalkmate import models as core
from chalkmate import ollama_provider
from chalkmate.assessment_rules import latest, validate_marks
from chalkmate.auth import CurrentUser, Database
from chalkmate.config import get_settings
from chalkmate.documents import inspect_document
from chalkmate.export_cells import safe_cell
from chalkmate.routes import audit, classroom
from chalkmate.storage import storage_request

router = APIRouter(prefix="/v1")


def assessment(db, assessment_id, edit=False):
    record = db.get(m.Assessment, assessment_id)
    if not record:
        raise HTTPException(404, "Assessment not found")
    classroom(db, record.classroom_id, edit=edit, active=edit)
    if edit:
        db.execute(select(m.Assessment.id).where(m.Assessment.id == record.id).with_for_update())
        db.refresh(record)
    return record


def rubric_for(db, record, *, newest=False):
    return db.scalar(
        select(m.Rubric)
        .where(
            m.Rubric.assessment_id == record.id,
            *(
                [m.Rubric.approved_at.is_not(None)]
                if record.status == "active" and not newest
                else []
            ),
        )
        .order_by(m.Rubric.version.desc())
        .limit(1)
    )


def assessment_output(db, record):
    newest = rubric_for(db, record, newest=True)
    return {
        "id": record.id,
        "classroom_id": record.classroom_id,
        "title": record.title,
        "instructions": record.instructions,
        "status": record.status,
        "rubric": rubric_for(db, record),
        "draft_rubric": newest
        if newest and not newest.approved_at and record.status == "active"
        else None,
        "submission_count": db.scalar(
            select(func.count())
            .select_from(m.Submission)
            .where(m.Submission.assessment_id == record.id)
        )
        or 0,
        "released_count": db.scalar(
            select(func.count())
            .select_from(m.Submission)
            .where(m.Submission.assessment_id == record.id, m.Submission.status == "released")
        )
        or 0,
    }


def submission(db, submission_id, edit=False):
    record = db.get(m.Submission, submission_id)
    if not record:
        raise HTTPException(404, "Submission not found")
    classroom(db, record.classroom_id, edit=edit, active=edit)
    if edit:
        db.execute(select(m.Submission.id).where(m.Submission.id == record.id).with_for_update())
        db.refresh(record)
        if record.status == "released":
            raise HTTPException(409, "Released work is immutable in this workflow")
    return record


def submission_output(db, record):
    student, file = db.get(core.Student, record.student_id), db.get(core.StoredFile, record.file_id)
    extraction = latest(db, m.Extraction, record.id)
    proposal = latest(db, m.Proposal, record.id)
    decision = latest(db, m.Decision, record.id)

    def current(item):
        return (
            item
            if item
            and extraction
            and item.extraction_id == extraction.id
            and item.rubric_id == record.rubric_id
            else None
        )

    release = latest(db, m.Release, record.id)
    reviews = db.scalars(
        select(m.QuestionReview)
        .where(
            m.QuestionReview.submission_id == record.id,
            m.QuestionReview.rubric_id == record.rubric_id,
        )
        .order_by(m.QuestionReview.created_at.desc(), m.QuestionReview.id.desc())
    ).all()
    by_question = {}
    for review in reviews:
        if extraction and review.extraction_id == extraction.id:
            by_question.setdefault(review.question_id, review)
    return {
        "rubric": db.get(m.Rubric, record.rubric_id),
        "released_decision_id": release.decision_id if release else None,
        "question_reviews": list(by_question.values()),
        **{
            key: getattr(record, key)
            for key in ("id", "assessment_id", "student_id", "file_id", "page_count", "status")
        },
        "student_name": student.name,
        "registration_number": student.registration_number,
        "filename": file.filename,
        "content_type": file.content_type,
        "extraction": extraction,
        "proposal": current(proposal),
        "decision": current(decision) if record.status in ("approved", "released") else None,
        "jobs": list(
            db.scalars(
                select(m.ProcessingJob)
                .where(m.ProcessingJob.submission_id == record.id)
                .order_by(m.ProcessingJob.created_at.desc())
            )
        ),
    }


@router.get("/processing/status", response_model=s.ProcessingStatus)
def processing_status(user: CurrentUser):
    settings = get_settings()
    try:
        names = [
            item["name"]
            for item in ollama_provider.models()
            if "cloud" not in item["name"] and not item.get("remote_model")
        ]
        return {
            "available": True,
            "models": names,
            "grading_model": settings.ollama_model,
            "vision_model": settings.ollama_vision_model,
            "detail": "Local Ollama is connected. Teachers review and approve every result.",
        }
    except Exception:
        return {
            "available": False,
            "models": [],
            "grading_model": settings.ollama_model,
            "vision_model": settings.ollama_vision_model,
            "detail": "Start Ollama for suggestions. PDF text and manual review remain available.",
        }


@router.get("/classrooms/{classroom_id}/assessments", response_model=list[s.AssessmentOutput])
def list_assessments(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id)
    return [
        assessment_output(db, item)
        for item in db.scalars(
            select(m.Assessment)
            .where(m.Assessment.classroom_id == classroom_id)
            .order_by(m.Assessment.created_at.desc())
        )
    ]


@router.post(
    "/classrooms/{classroom_id}/assessments", response_model=s.AssessmentOutput, status_code=201
)
def create_assessment(classroom_id: UUID, body: s.AssessmentInput, db: Database, user: CurrentUser):
    record = classroom(db, classroom_id, edit=True, active=True)
    item = m.Assessment(
        workspace_id=record.workspace_id, classroom_id=record.id, **body.model_dump()
    )
    db.add(item)
    db.flush()
    audit(
        db, user, record.workspace_id, "assessment.created", record.id, assessment_id=str(item.id)
    )
    return assessment_output(db, item)


@router.get("/assessments/{assessment_id}", response_model=s.AssessmentOutput)
def get_assessment(assessment_id: UUID, db: Database, user: CurrentUser):
    return assessment_output(db, assessment(db, assessment_id))


@router.post("/assessments/{assessment_id}/rubrics", response_model=s.RubricOutput, status_code=201)
def save_rubric(assessment_id: UUID, body: s.RubricInput, db: Database, user: CurrentUser):
    record = assessment(db, assessment_id, edit=True)
    previous = rubric_for(db, record, newest=True)
    if record.status == "active" and (body.base_version is None or len(body.reason.strip()) < 3):
        raise HTTPException(409, "A revision needs its base version and a reason")
    if body.base_version is not None and body.base_version != (previous.version if previous else 0):
        raise HTTPException(409, "The rubric changed. Refresh before saving a revision.")
    rubric = m.Rubric(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        assessment_id=record.id,
        reason=body.reason.strip(),
        version=previous.version + 1 if previous else 1,
        questions=body.model_dump(mode="json")["questions"],
        maximum=sum(q.maximum for q in body.questions),
    )
    db.add(rubric)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "rubric.saved",
        record.classroom_id,
        rubric_id=str(rubric.id),
        version=rubric.version,
    )
    return rubric


@router.post("/assessments/{assessment_id}/activate", response_model=s.AssessmentOutput)
def activate(
    assessment_id: UUID, db: Database, user: CurrentUser, body: s.ActivateInput | None = None
):
    record = assessment(db, assessment_id, edit=True)
    rubric = rubric_for(db, record, newest=True)
    if (
        not rubric
        or rubric.approved_at
        or (record.status == "active" and (not body or body.rubric_id != rubric.id))
        or (body and body.rubric_id != rubric.id)
    ):
        raise HTTPException(409, "Review and activate the latest saved draft rubric")
    rubric.approved_at = datetime.now(UTC)
    record.status = "active"
    audit(
        db,
        user,
        record.workspace_id,
        "assessment.activated",
        record.classroom_id,
        assessment_id=str(record.id),
        rubric_id=str(rubric.id),
    )
    return assessment_output(db, record)


@router.get("/assessments/{assessment_id}/submissions", response_model=list[s.SubmissionOutput])
def list_submissions(assessment_id: UUID, db: Database, user: CurrentUser):
    assessment(db, assessment_id)
    return [
        submission_output(db, item)
        for item in db.scalars(
            select(m.Submission)
            .where(m.Submission.assessment_id == assessment_id)
            .order_by(m.Submission.created_at)
        )
    ]


@router.post(
    "/assessments/{assessment_id}/submissions", response_model=s.SubmissionOutput, status_code=201
)
def create_submission(
    assessment_id: UUID, body: s.SubmissionInput, db: Database, user: CurrentUser
):
    record = assessment(db, assessment_id, edit=True)
    rubric = rubric_for(db, record)
    enrollment = db.scalar(
        select(core.Enrollment).where(
            core.Enrollment.classroom_id == record.classroom_id,
            core.Enrollment.student_id == body.student_id,
            core.Enrollment.status == "active",
        )
    )
    file = db.get(core.StoredFile, body.file_id)
    if record.status != "active" or not rubric or not rubric.approved_at:
        raise HTTPException(409, "Activate the rubric before uploading papers")
    if not enrollment or not file or file.classroom_id != record.classroom_id:
        raise HTTPException(422, "Choose an active student and a file from this classroom")
    duplicate = db.scalar(
        select(m.Submission.id)
        .join(core.StoredFile, core.StoredFile.id == m.Submission.file_id)
        .where(m.Submission.assessment_id == record.id, core.StoredFile.checksum == file.checksum)
    )
    if duplicate:
        raise HTTPException(409, "This paper is already uploaded for this assessment")
    content = storage_request(
        "GET", f"object/{get_settings().storage_bucket}/{file.object_path}"
    ).content
    try:
        count = inspect_document(content, file.content_type)
    except Exception as exc:
        raise HTTPException(
            422, "Use a valid unencrypted PDF (1–30 pages), JPEG, or PNG under 25 megapixels"
        ) from exc
    item = m.Submission(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        assessment_id=record.id,
        rubric_id=rubric.id,
        student_id=body.student_id,
        file_id=file.id,
        page_count=count,
    )
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "submission.matched",
        record.classroom_id,
        submission_id=str(item.id),
        student_id=str(body.student_id),
        page_count=count,
    )
    return submission_output(db, item)


@router.get("/submissions/{submission_id}", response_model=s.SubmissionOutput)
def get_submission(submission_id: UUID, db: Database, user: CurrentUser):
    return submission_output(db, submission(db, submission_id))


@router.post(
    "/submissions/{submission_id}/extractions", response_model=s.ExtractionOutput, status_code=201
)
def review_extraction(
    submission_id: UUID, body: s.ExtractionInput, db: Database, user: CurrentUser
):
    record = submission(db, submission_id, edit=True)
    previous = latest(db, m.Extraction, record.id)
    if body.base_version != (previous.version if previous else 0):
        raise HTTPException(409, "Extraction changed. Refresh before saving your review.")
    rubric = db.get(m.Rubric, record.rubric_id)
    if {str(a.question_id) for a in body.answers} != {q["id"] for q in rubric.questions} or len(
        body.answers
    ) != len(rubric.questions):
        raise HTTPException(422, "Map every assessment question exactly once")
    if any(
        answer.page_from > answer.page_to or answer.page_to > record.page_count
        for answer in body.answers
    ):
        raise HTTPException(422, "Answer page references must be inside the uploaded paper")
    reviewed = all(a.readable for a in body.answers)
    item = m.Extraction(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        submission_id=record.id,
        version=body.base_version + 1,
        source="teacher-reviewed",
        pages=previous.pages if previous else [],
        answers=body.model_dump(mode="json")["answers"],
        reviewed_by=user.id if reviewed else None,
    )
    db.add(item)
    record.status = "teacher_review" if reviewed else "extraction_review"
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "extraction.reviewed",
        record.classroom_id,
        submission_id=str(record.id),
        version=item.version,
        readable=reviewed,
    )
    return item


@router.post("/submissions/{submission_id}/jobs", response_model=s.JobOutput, status_code=202)
def queue_job(submission_id: UUID, body: s.JobInput, db: Database, user: CurrentUser):
    record = submission(db, submission_id, edit=True)
    extraction = latest(db, m.Extraction, record.id)
    settings = get_settings()
    if body.kind == "grade" and (not extraction or not extraction.reviewed_by):
        raise HTTPException(409, "Review all extracted answers before requesting suggestions")
    if body.kind == "extract" and extraction:
        raise HTTPException(409, "An extraction already exists; correct it in the review workspace")
    selected_examples = sorted(str(item) for item in body.calibration_ids)
    if len(set(selected_examples)) != len(selected_examples):
        raise HTTPException(422, "Choose each calibration example once")
    if selected_examples and body.kind != "grade":
        raise HTTPException(422, "Calibration examples are only used for grading")
    for example_id in body.calibration_ids:
        example = db.get(m.Calibration, example_id)
        if (
            not example
            or example.classroom_id != record.classroom_id
            or example.rubric_id != record.rubric_id
            or example.submission_id == record.id
        ):
            raise HTTPException(409, "Choose examples from other papers with this exact rubric")
    model = (
        body.model
        if body.model is not None
        else (settings.ollama_model if body.kind == "grade" else settings.ollama_vision_model)
    )
    model_digest = ""
    if body.kind == "grade" or model:
        try:
            model_digest = ollama_provider.model_info(model, vision=body.kind == "extract")
        except Exception as exc:
            raise HTTPException(
                409,
                "Choose an installed model with the required capability, or review manually",
            ) from exc
    base_version = str(extraction.id) if body.kind == "grade" else "original"
    configuration = (
        f"{model}:{model_digest}:{ollama_provider.PROMPT_VERSION}:"
        f"{record.rubric_id}:{selected_examples}"
    )
    version = f"{base_version}:{hashlib.sha256(configuration.encode()).hexdigest()[:12]}"
    existing = db.scalar(
        select(m.ProcessingJob).where(
            m.ProcessingJob.submission_id == record.id,
            m.ProcessingJob.kind == body.kind,
            m.ProcessingJob.input_version == version,
        )
    )
    if existing:
        return existing
    job = m.ProcessingJob(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        submission_id=record.id,
        requested_by=user.id,
        kind=body.kind,
        input_version=version,
        calibration_ids=selected_examples,
        model=model,
    )
    db.add(job)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "processing.queued",
        record.classroom_id,
        job_id=str(job.id),
        kind=body.kind,
        model=model,
    )
    return job


@router.post("/jobs/{job_id}/retry", response_model=s.JobOutput)
def retry_job(job_id: UUID, db: Database, user: CurrentUser):
    job = db.get(m.ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    record = submission(db, job.submission_id, edit=True)
    extraction = latest(db, m.Extraction, record.id)
    if job.status != "failed" or job.attempts >= 3:
        raise HTTPException(409, "Only failed jobs with fewer than three attempts can be retried")
    if job.kind == "grade" and (
        not extraction or str(extraction.id) != job.input_version.split(":")[0]
    ):
        raise HTTPException(409, "This job uses an older extraction. Request a fresh suggestion.")
    job.status, job.error = "queued", None
    audit(
        db, user, record.workspace_id, "processing.retried", record.classroom_id, job_id=str(job.id)
    )
    return job


@router.post("/jobs/{job_id}/cancel", response_model=s.JobOutput)
def cancel_job(job_id: UUID, db: Database, user: CurrentUser):
    job = db.get(m.ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    record = submission(db, job.submission_id, edit=True)
    if job.status not in ("queued", "running"):
        raise HTTPException(409, "This job is no longer pending")
    job.status = "canceled"
    audit(
        db,
        user,
        record.workspace_id,
        "processing.canceled",
        record.classroom_id,
        job_id=str(job.id),
    )
    return job


@router.post(
    "/submissions/{submission_id}/decisions", response_model=s.DecisionOutput, status_code=201
)
def approve_decision(submission_id: UUID, body: s.DecisionInput, db: Database, user: CurrentUser):
    record = submission(db, submission_id, edit=True)
    extraction = latest(db, m.Extraction, record.id)
    if not extraction or not extraction.reviewed_by or extraction.id != body.extraction_id:
        raise HTTPException(409, "Approve the latest readable extraction before approving marks")
    if db.scalar(
        select(m.ProcessingJob.id)
        .where(
            m.ProcessingJob.submission_id == record.id,
            m.ProcessingJob.status.in_(["queued", "running"]),
        )
        .limit(1)
    ):
        raise HTTPException(409, "Wait for or cancel pending processing before approving")
    question_reviews = submission_output(db, record)["question_reviews"]
    if sorted(str(item.id) for item in question_reviews) != sorted(
        str(item) for item in body.question_review_ids
    ):
        raise HTTPException(409, "Question reviews changed. Refresh before approving the result.")
    rubric = db.get(m.Rubric, record.rubric_id)
    marks = body.model_dump(mode="json")["marks"]
    total = validate_marks(rubric.questions, marks)
    proposal = latest(db, m.Proposal, record.id)
    current_proposal = (
        proposal
        if proposal and proposal.extraction_id == extraction.id and proposal.rubric_id == rubric.id
        else None
    )
    if body.proposal_id is not None and (
        not current_proposal or body.proposal_id != current_proposal.id
    ):
        raise HTTPException(409, "The selected suggestion is stale. Refresh before approving.")
    if current_proposal:
        if body.proposal_id != current_proposal.id:
            raise HTTPException(409, "Review the latest suggestion before approving")
        proposed = {
            c["criterion_id"]: Decimal(str(c["mark"])) for c in current_proposal.output["criteria"]
        }
        if (
            any(Decimal(str(mark["mark"])) != proposed[mark["criterion_id"]] for mark in marks)
            and not body.reason.strip()
        ):
            raise HTTPException(422, "Explain why you changed the suggested marks")
    elif not body.reason.strip():
        raise HTTPException(422, "Record a reason for manual grading")
    item = m.Decision(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        submission_id=record.id,
        extraction_id=extraction.id,
        rubric_id=rubric.id,
        proposal_id=body.proposal_id,
        approved_by=user.id,
        marks=marks,
        total=total,
        maximum=rubric.maximum,
        question_feedback={str(r.question_id): r.feedback for r in reversed(question_reviews)},
        feedback=body.feedback,
        reason=body.reason,
    )
    db.add(item)
    record.status = "approved"
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "result.approved",
        record.classroom_id,
        submission_id=str(record.id),
        decision_id=str(item.id),
    )
    return item


@router.post("/submissions/{submission_id}/release", response_model=s.DecisionOutput)
def release_result(submission_id: UUID, body: s.ReleaseInput, db: Database, user: CurrentUser):
    record = submission(db, submission_id, edit=True)
    decision = latest(db, m.Decision, record.id)
    extraction = latest(db, m.Extraction, record.id)
    if (
        record.status != "approved"
        or not decision
        or decision.id != body.decision_id
        or not extraction
        or decision.rubric_id != record.rubric_id
        or decision.extraction_id != extraction.id
    ):
        raise HTTPException(409, "Approve the latest result before releasing it")
    db.add(
        m.Release(
            workspace_id=record.workspace_id,
            classroom_id=record.classroom_id,
            submission_id=record.id,
            decision_id=decision.id,
            released_by=user.id,
        )
    )
    record.status = "released"
    audit(
        db,
        user,
        record.workspace_id,
        "result.released",
        record.classroom_id,
        submission_id=str(record.id),
        decision_id=str(decision.id),
    )
    return decision


@router.get("/classrooms/{classroom_id}/my-results", response_model=list[s.ReleasedResult])
def my_results(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id, staff=False)
    return db.scalar(text("SELECT chalkmate.my_results(:id)"), {"id": classroom_id})


@router.get("/assessments/{assessment_id}/export")
def export_marks(assessment_id: UUID, db: Database, user: CurrentUser, format: str = "csv"):
    record = assessment(db, assessment_id)
    if format not in ("csv", "xlsx"):
        raise HTTPException(422, "Choose CSV or XLSX")
    results = {
        row.student_id: (row, decision)
        for row, decision in db.execute(
            select(m.Submission, m.Decision)
            .join(m.Release, m.Release.submission_id == m.Submission.id)
            .join(m.Decision, m.Decision.id == m.Release.decision_id)
            .where(m.Submission.assessment_id == record.id)
            .order_by(m.Release.created_at, m.Release.id)
        )
    }
    submitted = set(
        db.scalars(select(m.Submission.student_id).where(m.Submission.assessment_id == record.id))
    )
    rows = [
        [
            "Registration number",
            "Name",
            "Enrollment",
            "Result status",
            "Total",
            "Maximum",
            "Feedback",
        ]
    ]
    for student, enrollment in db.execute(
        select(core.Student, core.Enrollment)
        .join(core.Enrollment, core.Enrollment.student_id == core.Student.id)
        .where(core.Enrollment.classroom_id == record.classroom_id)
        .order_by(core.Student.registration_number)
    ):
        result = results.get(student.id)
        rows.append(
            [
                student.registration_number,
                student.name,
                enrollment.status,
                "released" if result else "not released" if student.id in submitted else "missing",
                result[1].total if result else "",
                result[1].maximum if result else "",
                result[1].feedback if result else "",
            ]
        )
    rows = [[safe_cell(cell) for cell in row] for row in rows]
    if format == "csv":
        output = io.StringIO()
        csv.writer(output).writerows(rows)
        content, mime = output.getvalue().encode("utf-8-sig"), "text/csv"
    else:
        book = Workbook()
        sheet = book.active
        sheet.title = "Released marks"
        for row in rows:
            sheet.append(row)
        for row in sheet.iter_rows(min_row=2, min_col=5, max_col=6):
            for cell in row:
                cell.number_format = "0.00"
        sheet.freeze_panes = "A2"
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                60, max(18, max(len(str(c.value or "")) for c in column) + 2)
            )
        output = io.BytesIO()
        book.save(output)
        content, mime = (
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return Response(
        content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="marks-{record.id}.{format}"'},
    )
