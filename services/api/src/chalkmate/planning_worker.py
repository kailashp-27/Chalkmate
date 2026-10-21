"""Leased local planning jobs. Results are drafts and never published."""

import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text

from chalkmate import planning_models as m
from chalkmate.auth import Identity
from chalkmate.planning_routes import current_sources, save
from chalkmate.planning_rules import generate
from chalkmate.planning_schemas import PlanningContent, PlanningInput
from chalkmate.processing import engine, scoped_session
from chalkmate.routes import classroom
from chalkmate.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="chalkmate.dispatch_planning")
def dispatch_planning():
    with engine().begin() as db:
        ids = list(db.scalars(text("SELECT chalkmate.pending_planning()")))
    for value in ids:
        process_planning.delay(str(value))


@celery_app.task(name="chalkmate.process_planning", soft_time_limit=600, time_limit=650)
def process_planning(job_id):
    job_id = UUID(job_id)
    with engine().begin() as db:
        claim = db.execute(
            text("SELECT * FROM chalkmate.claim_planning(:id)"), {"id": job_id}
        ).first()
    if not claim:
        return
    actor = Identity(claim.actor_id, claim.email)
    try:
        with scoped_session(actor) as db:
            job = db.get(m.PlanningJob, job_id)
            if not job:
                return
            classroom(db, job.classroom_id, edit=True, active=True)
            current_sources(db, job.classroom_id, job.request["sources"])
            request, model, attempt = job.request, job.model, claim.attempt
        content, digest, usage = generate(model, request)
        with scoped_session(actor) as db:
            job = db.scalar(
                select(m.PlanningJob).where(m.PlanningJob.id == job_id).with_for_update()
            )
            if not job or job.status != "running" or job.attempts != attempt:
                return
            parent = classroom(db, job.classroom_id, edit=True, active=True)
            current_sources(db, job.classroom_id, request["sources"])
            body = PlanningInput(
                kind=request["kind"],
                title=request["title"],
                content=PlanningContent.model_validate(content),
            )
            row = save(db, actor, parent, body, request["sources"])
            job.result_id, job.status = row.id, "succeeded"
            job.model_digest, job.usage, job.lease_until = digest, usage, None
            db.commit()
    except Exception as exc:
        logger.warning("Planning job %s failed (%s)", job_id, type(exc).__name__)
        with scoped_session(actor) as db:
            job = db.get(m.PlanningJob, job_id)
            if job and job.status == "running" and job.attempts == claim.attempt:
                job.status = "canceled" if isinstance(exc, HTTPException) else "failed"
                job.error = (
                    "Source or teaching access changed; create a new request."
                    if isinstance(exc, HTTPException)
                    else (
                        "Local generation failed validation. Check the model and sources, "
                        "retry or author manually."
                    )
                )
                job.lease_until = None
                db.commit()
