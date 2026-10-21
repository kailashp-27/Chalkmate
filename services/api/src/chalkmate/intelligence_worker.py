"""Durable local teaching generation with leases, scoped identity and stale-source checks."""

import logging
from uuid import UUID

from sqlalchemy import select, text

from chalkmate import intelligence_models as m
from chalkmate import intelligence_provider
from chalkmate.auth import Identity
from chalkmate.intelligence_rules import staleness, validate_analysis, validate_material
from chalkmate.processing import engine, scoped_session
from chalkmate.routes import audit
from chalkmate.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="chalkmate.dispatch_intelligence")
def dispatch_intelligence():
    with engine().begin() as db:
        ids = list(db.scalars(text("SELECT chalkmate.pending_intelligence()")))
    for value in ids:
        process_intelligence.delay(str(value))


@celery_app.task(name="chalkmate.process_intelligence", soft_time_limit=600, time_limit=650)
def process_intelligence(run_id):
    run_id = UUID(run_id)
    with engine().begin() as db:
        claim = db.execute(
            text("SELECT * FROM chalkmate.claim_intelligence(:id)"), {"id": run_id}
        ).first()
    if not claim:
        return
    actor = Identity(claim.actor_id, claim.email)
    try:
        with scoped_session(actor) as db:
            run = db.get(m.IntelligenceRun, run_id)
            if not run:
                return
            stale, reason = staleness(db, run)
            if stale:
                run.status, run.error = "canceled", reason
                db.commit()
                return
            kind, model, snapshot = run.kind, run.model, run.snapshot
        output, model_digest, usage = intelligence_provider.generate(kind, model, snapshot)
        output = (
            validate_analysis(output, snapshot)
            if kind == "analysis"
            else validate_material(output, snapshot)
        )
        with scoped_session(actor) as db:
            run = db.scalar(
                select(m.IntelligenceRun).where(m.IntelligenceRun.id == run_id).with_for_update()
            )
            if not run or run.status != "running":
                return
            stale, reason = staleness(db, run)
            if stale:
                run.status, run.error = "canceled", reason
            else:
                run.result, run.model_digest, run.usage = output, model_digest, usage
                run.status = "succeeded"
                run.error = None
                if kind == "material":
                    db.add(
                        m.TeachingMaterial(
                            workspace_id=run.workspace_id,
                            classroom_id=run.classroom_id,
                            run_id=run.id,
                            version=1,
                            created_by=run.requested_by,
                            content=output,
                            reason="Local Ollama draft — teacher review required",
                        )
                    )
            run.lease_until = None
            audit(
                db,
                actor,
                run.workspace_id,
                "intelligence.completed",
                run.classroom_id,
                run_id=str(run.id),
                status=run.status,
                kind=kind,
            )
            db.commit()
    except Exception as exc:
        logger.warning("Teaching run %s failed (%s)", run_id, type(exc).__name__)
        with scoped_session(actor) as db:
            run = db.get(m.IntelligenceRun, run_id)
            if run and run.status == "running":
                run.status = "failed"
                run.lease_until = None
                run.error = (
                    "Local generation failed or its evidence/output did not validate. "
                    "Inspect sources and the local model, retry, or use manual authoring."
                )
                db.commit()
