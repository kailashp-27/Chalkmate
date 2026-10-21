import logging
from functools import lru_cache
from uuid import UUID

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from chalkmate import assessment_models as m
from chalkmate import models as core
from chalkmate import ollama_provider
from chalkmate.assessment_rules import latest, validate_suggestion
from chalkmate.auth import Identity
from chalkmate.config import get_settings
from chalkmate.db import set_identity
from chalkmate.documents import extract_embedded, render_pages
from chalkmate.routes import audit
from chalkmate.storage import storage_request
from chalkmate.worker import celery_app

logger = logging.getLogger(__name__)


@lru_cache
def engine():
    url = get_settings().worker_database_url
    if not url:
        raise RuntimeError("Configure the restricted worker database connection")
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


@celery_app.task(name="chalkmate.dispatch_pending")
def dispatch_pending():
    with engine().begin() as connection:
        ids = list(connection.scalars(text("SELECT chalkmate.pending_jobs()")))
    for job_id in ids:
        process_job.delay(str(job_id))


def scoped_session(actor):
    session = Session(engine(), expire_on_commit=False)
    session.begin()
    set_identity(session, str(actor.id), actor.email)
    return session


@celery_app.task(name="chalkmate.process_job", soft_time_limit=1000, time_limit=1100)
def process_job(job_id):
    job_id = UUID(job_id)
    with engine().begin() as connection:
        claimed = connection.execute(
            text("SELECT * FROM chalkmate.claim_job(:id)"), {"id": job_id}
        ).first()
    if not claimed:
        return
    actor = Identity(claimed.actor_id, claimed.email)
    try:
        with scoped_session(actor) as db:
            job = db.get(m.ProcessingJob, job_id)
            record = db.get(m.Submission, job.submission_id)
            file = db.get(core.StoredFile, record.file_id)
            rubric = db.get(m.Rubric, record.rubric_id)
            extraction = latest(db, m.Extraction, record.id)
            kind, model, object_path, content_type = (
                job.kind,
                job.model,
                file.object_path,
                file.content_type,
            )
            submission_id, rubric_id, questions = record.id, rubric.id, rubric.questions
            extraction_id = extraction.id if extraction else None
            answers = extraction.answers if extraction else []
            calibration_ids = list(job.calibration_ids)
            calibration_examples = []
            for example_id in calibration_ids:
                example = db.get(m.Calibration, UUID(example_id))
                if (
                    not example
                    or example.rubric_id != rubric.id
                    or example.classroom_id != record.classroom_id
                    or example.submission_id == record.id
                ):
                    raise ValueError("Calibration example no longer matches this grading run")
                calibration_examples.append(
                    {
                        "example_id": str(example.id),
                        "band": example.band,
                        "reviewed_answers": example.snapshot["answers"],
                        "reference_marks": [
                            {"criterion_id": c["criterion_id"], "mark": c["expected"]}
                            for c in example.snapshot["criteria"]
                        ],
                    }
                )
            if record.status == "released" or (kind == "extract" and extraction):
                job.status = "canceled"
                db.commit()
                return
            if kind == "grade" and (
                not extraction
                or not extraction.reviewed_by
                or str(extraction.id) != job.input_version.split(":")[0]
            ):
                job.status = "canceled"
                db.commit()
                return
        if kind == "extract":
            content = storage_request(
                "GET", f"object/{get_settings().storage_bucket}/{object_path}"
            ).content
            pages = extract_embedded(content, content_type)
            source = "pdf-embedded-text"
            if not pages or not any(page["text"].strip() for page in pages):
                if not model:
                    raise ValueError(
                        "No embedded text. Select a local vision model or transcribe manually."
                    )
                digest = ollama_provider.model_info(model, vision=True)
                pages = [
                    {"page": number, "text": ollama_provider.transcribe(model, image)}
                    for number, image in enumerate(render_pages(content, content_type), 1)
                ]
                source = f"ollama:{model}:{digest[:16]}"
        else:
            output, digest, usage = ollama_provider.grade(
                model, questions, answers, calibration_examples=calibration_examples
            )
            output = validate_suggestion(questions, answers, output)
        with scoped_session(actor) as db:
            record = db.scalar(
                select(m.Submission).where(m.Submission.id == submission_id).with_for_update()
            )
            job = db.get(m.ProcessingJob, job_id)
            current = latest(db, m.Extraction, submission_id) if record else None
            class_record = db.get(core.Classroom, record.classroom_id) if record else None
            stale = (current.id if current else None) != extraction_id
            if (
                not record
                or not class_record
                or class_record.archived
                or record.status == "released"
                or record.rubric_id != rubric_id
                or job.status != "running"
                or stale
            ):
                if job and job.status == "running":
                    job.status = "canceled"
                db.commit()
                return
            scope = {
                "workspace_id": record.workspace_id,
                "classroom_id": record.classroom_id,
                "submission_id": record.id,
            }
            if kind == "extract":
                db.add(m.Extraction(**scope, version=1, source=source, pages=pages, answers=[]))
                record.status = "extraction_review"
            else:
                db.add(
                    m.Proposal(
                        **scope,
                        extraction_id=extraction_id,
                        rubric_id=rubric_id,
                        calibration_ids=calibration_ids,
                        model=model,
                        model_digest=digest,
                        prompt_version=ollama_provider.PROMPT_VERSION,
                        output=output,
                        usage=usage,
                    )
                )
                record.status = "teacher_review"
            job.status = "succeeded"
            audit(
                db,
                actor,
                record.workspace_id,
                "processing.completed",
                record.classroom_id,
                job_id=str(job.id),
                kind=kind,
            )
            db.commit()
    except Exception as exc:
        logger.warning("Processing job %s failed (%s)", job_id, type(exc).__name__)
        with scoped_session(actor) as db:
            job = db.get(m.ProcessingJob, job_id)
            if job and job.status == "running":
                job.status = "failed"
                job.error = (
                    "Processing could not finish. Check the selected local model and paper, "
                    "then retry, correct the extraction, or grade manually."
                )
                db.commit()
