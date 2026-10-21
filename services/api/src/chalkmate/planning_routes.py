"""Teacher-reviewed planning; no publication or delivery side effects."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select, text

from chalkmate import assessment_models as assessment
from chalkmate import followup_models as followup
from chalkmate import models as core
from chalkmate import planning_models as m
from chalkmate import planning_schemas as s
from chalkmate.auth import CurrentUser, Database
from chalkmate.intelligence_routes import lock
from chalkmate.intelligence_rules import cohort
from chalkmate.operations import service_checks
from chalkmate.planning_rules import PROMPT_VERSION, checks, command_preview, export_document
from chalkmate.routes import audit, classroom

router = APIRouter(prefix="/v1")


def record(db, document_id, edit=False):
    row = db.get(m.PlanningDocument, document_id)
    if not row:
        raise HTTPException(404, "Planning document not found")
    classroom(db, row.classroom_id, edit=edit, active=edit)
    return row


def latest(db, row):
    return (
        db.scalar(
            select(func.max(m.PlanningDocument.version)).where(
                m.PlanningDocument.classroom_id == row.classroom_id,
                m.PlanningDocument.family_id == row.family_id,
            )
        )
        == row.version
    )


def approved(db, row):
    return (
        db.scalar(select(m.PlanningApproval.id).where(m.PlanningApproval.document_id == row.id))
        is not None
    )


def sources(db, class_id, ids):
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Select each source only once")
    output = []
    for i, value in enumerate(ids, 1):
        row = record(db, value)
        if row.classroom_id != class_id or not latest(db, row) or not approved(db, row):
            raise HTTPException(409, "Choose current approved sources from this classroom")
        output.append(
            {
                "source_id": f"S{i}",
                "id": str(row.id),
                "title": row.title,
                "kind": row.kind,
                "version": row.version,
                "content": row.content,
            }
        )
    if len(json.dumps(output)) > 18000:
        raise HTTPException(
            422, "Sources exceed the local budget. Select fewer or shorter sources."
        )
    return output


def current_sources(db, class_id, snapshot):
    sources(db, class_id, [UUID(v["id"]) for v in snapshot])


def output(db, row):
    issues = checks(row.kind, row.content, row.sources)
    try:
        current_sources(db, row.classroom_id, row.sources)
    except HTTPException:
        issues.append(
            "A selected source has a newer version. Create a new draft with "
            "current approved sources."
        )
    return {
        **{
            k: getattr(row, k)
            for k in (
                "id",
                "family_id",
                "version",
                "kind",
                "title",
                "content",
                "sources",
                "created_at",
            )
        },
        "approved": approved(db, row),
        "latest": latest(db, row),
        "issues": issues,
    }


def save(db, user, parent, body, snapshot, family_id=None, version=1):
    if len(json.dumps(body.content.model_dump(mode="json"))) > 45000:
        raise HTTPException(422, "Draft is too large. Split it into smaller documents.")
    row = m.PlanningDocument(
        workspace_id=parent.workspace_id,
        classroom_id=parent.id,
        family_id=family_id or uuid4(),
        version=version,
        kind=body.kind,
        title=body.title,
        content=body.content.model_dump(mode="json"),
        sources=snapshot,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        user,
        parent.workspace_id,
        "planning.created",
        parent.id,
        document_id=str(row.id),
        kind=row.kind,
        version=version,
    )
    return row


@router.get("/classrooms/{class_id}/planning", response_model=list[s.PlanningOutput])
def documents(class_id: UUID, db: Database, user: CurrentUser):
    classroom(db, class_id)
    rows = list(
        db.scalars(
            select(m.PlanningDocument)
            .where(m.PlanningDocument.classroom_id == class_id)
            .order_by(m.PlanningDocument.created_at.desc())
        )
    )
    return [output(db, row) for row in rows]


@router.post("/classrooms/{class_id}/planning", response_model=s.PlanningOutput, status_code=201)
def create(class_id: UUID, body: s.PlanningInput, db: Database, user: CurrentUser):
    parent = classroom(db, class_id, edit=True, active=True)
    if body.kind == "report":
        raise HTTPException(
            422, "Build reports from recorded classroom activity using a saved template"
        )
    return output(db, save(db, user, parent, body, sources(db, class_id, body.source_ids)))


@router.post("/planning/{document_id}/versions", response_model=s.PlanningOutput, status_code=201)
def revise(document_id: UUID, body: s.VersionInput, db: Database, user: CurrentUser):
    old = record(db, document_id, edit=True)
    lock(db, old.family_id)
    if not latest(db, old) or body.base_version != old.version:
        raise HTTPException(409, "A newer version exists. Refresh before editing.")
    if body.kind != old.kind or old.kind == "report":
        raise HTTPException(
            422, "Keep the same document kind; regenerate reports from the source records"
        )
    parent = classroom(db, old.classroom_id, edit=True, active=True)
    return output(
        db,
        save(
            db,
            user,
            parent,
            body,
            sources(db, parent.id, body.source_ids),
            old.family_id,
            old.version + 1,
        ),
    )


@router.post("/planning/{document_id}/approve", response_model=s.PlanningOutput)
def approve(document_id: UUID, db: Database, user: CurrentUser):
    row = record(db, document_id, edit=True)
    lock(db, row.family_id)
    result = output(db, row)
    if not result["latest"] or result["issues"]:
        raise HTTPException(409, "Resolve checks and use the latest version before approving")
    if not result["approved"]:
        db.add(
            m.PlanningApproval(
                workspace_id=row.workspace_id,
                classroom_id=row.classroom_id,
                document_id=row.id,
                approved_by=user.id,
            )
        )
        audit(
            db,
            user,
            row.workspace_id,
            "planning.approved",
            row.classroom_id,
            document_id=str(row.id),
        )
        db.flush()
    return output(db, row)


@router.get("/planning/{document_id}/export")
def export(document_id: UUID, db: Database, user: CurrentUser, teacher_key: bool = False):
    row = record(db, document_id)
    db.execute(
        text("SELECT chalkmate.record_planning_export(:id,:key)"),
        {"id": row.id, "key": teacher_key},
    )
    return Response(
        export_document(row, teacher_key, approved(db, row)),
        media_type="text/markdown",
        headers={
            "Content-Disposition": 'attachment; filename="chalkmate-planning.md"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/planning/{document_id}/report", response_model=s.PlanningOutput, status_code=201)
def build_report(document_id: UUID, db: Database, user: CurrentUser):
    template = record(db, document_id, edit=True)
    if template.kind != "report_template" or not approved(db, template) or not latest(db, template):
        raise HTTPException(409, "Choose a current approved report template")
    parent = classroom(db, template.classroom_id, edit=True, active=True)

    def count(model, *conditions):
        return (
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.classroom_id == parent.id, *conditions)
            )
            or 0
        )

    # Reuse the same current-rubric, reviewed-extraction eligibility as teaching summaries.
    approved_count = sum(
        sum(row["disposition"] == "reviewed" for row in cohort(db, exam)[1])
        for exam in db.scalars(
            select(assessment.Assessment).where(assessment.Assessment.classroom_id == parent.id)
        )
    )
    values = {
        "classroom": parent.name,
        "students": count(core.Enrollment, core.Enrollment.status == "active"),
        "assessments": count(assessment.Assessment),
        "approved_decisions": approved_count,
        "assignments": count(followup.Assignment),
        "activity_events": count(core.AuditEvent),
    }
    rendered = "\n".join(
        f"{col.replace('_', ' ').title()}: {values[col]}" for col in template.content["columns"]
    )
    body = s.PlanningInput(
        kind="report",
        title=f"{template.title} · {datetime.now(UTC).date()}",
        content=s.PlanningContent(
            text=f"Recorded at {datetime.now(UTC).isoformat()}\n\n{rendered}"
        ),
    )
    return output(db, save(db, user, parent, body, sources(db, parent.id, [template.id])))


def budget(db, class_id):
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    jobs = list(db.scalars(select(m.PlanningJob).where(m.PlanningJob.classroom_id == class_id)))
    return jobs, sum(j.budget_attempts for j in jobs if j.budget_day >= start)


@router.post("/classrooms/{class_id}/planning-jobs", response_model=s.JobOutput, status_code=201)
def generate(class_id: UUID, body: s.GenerateInput, db: Database, user: CurrentUser):
    parent = classroom(db, class_id, edit=True, active=True)
    lock(db, class_id)
    jobs, attempts = budget(db, class_id)
    if any(j.status in ("queued", "running") for j in jobs) or attempts >= 20:
        raise HTTPException(
            409,
            "One active planning job at a time; daily limit is 20 attempts. "
            "Cancel an active job or use manual authoring.",
        )
    snapshot = sources(db, class_id, body.source_ids)
    if body.kind in ("paper", "question_bank") and not any(
        s["kind"] == "syllabus" for s in snapshot
    ):
        raise HTTPException(422, "Select an approved syllabus")
    if body.kind in ("meeting", "announcement") and not body.original:
        raise HTTPException(422, "Supply original notes or announcement text")
    request = {
        **body.model_dump(mode="json", exclude={"source_ids", "model"}),
        "sources": snapshot,
        "prompt_version": PROMPT_VERSION,
    }
    if len(json.dumps(request)) > 21000:
        raise HTTPException(422, "Input exceeds the local budget. Select fewer sources.")
    row = m.PlanningJob(
        workspace_id=parent.workspace_id,
        classroom_id=class_id,
        requested_by=user.id,
        model=body.model,
        budget_day=datetime.now(UTC),
        request=request,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        user,
        parent.workspace_id,
        "planning.queued",
        class_id,
        job_id=str(row.id),
        model=body.model,
    )
    return row


@router.get("/classrooms/{class_id}/planning-jobs", response_model=list[s.JobOutput])
def jobs(class_id: UUID, db: Database, user: CurrentUser):
    classroom(db, class_id)
    return list(
        db.scalars(
            select(m.PlanningJob)
            .where(m.PlanningJob.classroom_id == class_id)
            .order_by(m.PlanningJob.created_at.desc())
            .limit(50)
        )
    )


@router.post("/planning-jobs/{job_id}/{action}", response_model=s.JobOutput)
def recover(job_id: UUID, action: str, db: Database, user: CurrentUser):
    row = db.get(m.PlanningJob, job_id)
    if not row:
        raise HTTPException(404, "Planning job not found")
    classroom(db, row.classroom_id, edit=True, active=True)
    lock(db, row.classroom_id)
    db.refresh(row, with_for_update=True)
    if action == "cancel" and row.status in ("queued", "running", "failed"):
        row.status, row.error = "canceled", "Canceled by teacher"
    elif action == "retry" and row.status == "failed" and row.attempts < 3:
        records, attempts = budget(db, row.classroom_id)
        if attempts >= 20 or any(j.status in ("queued", "running") for j in records):
            raise HTTPException(409, "Planning budget reached or another job is active")
        current_sources(db, row.classroom_id, row.request["sources"])
        now = datetime.now(UTC)
        row.budget_attempts = row.budget_attempts + 1 if row.budget_day.date() == now.date() else 1
        row.budget_day = now
        row.status, row.error = "queued", None
    else:
        raise HTTPException(
            409, "Only active jobs can be canceled and failed jobs retried up to three attempts"
        )
    audit(db, user, row.workspace_id, f"planning.{action}", row.classroom_id, job_id=str(row.id))
    return row


@router.post("/classrooms/{class_id}/command-preview", response_model=s.CommandOutput)
def preview_command(class_id: UUID, body: s.CommandInput, db: Database, user: CurrentUser):
    classroom(db, class_id)
    return command_preview(body.text)


@router.get("/classrooms/{class_id}/readiness", response_model=s.ReadinessOutput)
def readiness(class_id: UUID, db: Database, user: CurrentUser):
    classroom(db, class_id)
    rows, attempts = budget(db, class_id)
    now = datetime.now(UTC)
    services, recovery = service_checks(db, class_id)
    return {
        "services": services,
        "recovery": recovery,
        "queued": sum(j.status in ("queued", "running") for j in rows),
        "failed": sum(j.status == "failed" for j in rows),
        "expired": sum(
            j.status == "running" and j.lease_until is not None and j.lease_until < now
            for j in rows
        ),
        "attempts_today": attempts,
        "daily_limit": 20,
        "generated_tokens": sum(int(j.usage.get("eval_count") or 0) for j in rows),
        "pilot_status": "Teacher pilot pending consented samples and measured review time",
    }
