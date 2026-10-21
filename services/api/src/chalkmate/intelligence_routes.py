"""Private evidence inspection, append-only finding review and explicit material approval."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select, text

from chalkmate import (
    followup_models as followup,
)
from chalkmate import (
    intelligence_models as m,
)
from chalkmate import (
    intelligence_schemas as s,
)
from chalkmate.assessment_routes import assessment
from chalkmate.auth import CurrentUser, Database
from chalkmate.config import get_settings
from chalkmate.intelligence_rules import (
    PROMPT_VERSION,
    analysis_snapshot,
    current_review,
    digest,
    export_material,
    material_snapshot,
    staleness,
    student_material,
    summary,
    validate_analysis,
    validate_material,
)
from chalkmate.routes import audit, classroom

router = APIRouter(prefix="/v1")


def lock(db, value):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:id,0))"), {"id": str(value)})


def run_record(db, run_id, edit=False):
    record = db.get(m.IntelligenceRun, run_id)
    if not record:
        raise HTTPException(404, "Teaching analysis not found")
    classroom(db, record.classroom_id, edit=edit, active=edit)
    return record


def run_output(db, record):
    stale, reason = staleness(db, record)
    reviews = list(
        db.scalars(
            select(m.FindingReview)
            .where(m.FindingReview.run_id == record.id)
            .order_by(m.FindingReview.created_at.desc())
        )
    )
    return {
        **{
            k: getattr(record, k)
            for k in [
                "id",
                "assessment_id",
                "rubric_id",
                "kind",
                "model",
                "model_digest",
                "prompt_version",
                "request",
                "input_digest",
                "status",
                "attempts",
                "error",
                "created_at",
                "result",
                "usage",
            ]
        },
        "stale": stale,
        "stale_reason": reason,
        "sources": record.snapshot.get("sources", []),
        "reviews": reviews,
    }


def create_run(db, user, parent, kind, request, snapshot, result=None):
    record = m.IntelligenceRun(
        workspace_id=parent.workspace_id,
        classroom_id=parent.classroom_id,
        assessment_id=parent.id,
        rubric_id=UUID(snapshot["rubric_id"])
        if kind == "analysis"
        else db.get(m.IntelligenceRun, request.source_run_id).rubric_id,
        requested_by=user.id,
        kind=kind,
        model="manual" if result is not None else (request.model or get_settings().ollama_model),
        model_digest="manual" if result is not None else "",
        prompt_version=PROMPT_VERSION,
        request=request.model_dump(mode="json", exclude={"manual_result", "manual_content"}),
        snapshot=snapshot,
        input_digest=digest(snapshot),
        status="succeeded" if result is not None else "queued",
        result=result,
        usage={},
    )
    if not record.model:
        raise HTTPException(
            409, "Configure an installed local Ollama model or use manual authoring"
        )
    db.add(record)
    db.flush()
    audit(
        db,
        user,
        parent.workspace_id,
        "intelligence.created",
        parent.classroom_id,
        run_id=str(record.id),
        kind=kind,
        model=record.model,
    )
    if kind == "material" and result is not None:
        db.add(
            m.TeachingMaterial(
                workspace_id=parent.workspace_id,
                classroom_id=parent.classroom_id,
                run_id=record.id,
                version=1,
                created_by=user.id,
                content=result,
                reason="Initial teacher-authored material",
            )
        )
        db.flush()
    return run_output(db, record)


@router.get("/assessments/{assessment_id}/topic-summary", response_model=s.SummaryOutput)
def topic_summary(assessment_id: UUID, db: Database, user: CurrentUser):
    return summary(db, assessment(db, assessment_id))


@router.get("/assessments/{assessment_id}/intelligence-runs", response_model=list[s.RunOutput])
def list_runs(assessment_id: UUID, db: Database, user: CurrentUser):
    assessment(db, assessment_id)
    return [
        run_output(db, r)
        for r in db.scalars(
            select(m.IntelligenceRun)
            .where(m.IntelligenceRun.assessment_id == assessment_id)
            .order_by(m.IntelligenceRun.created_at.desc())
        )
    ]


@router.post(
    "/assessments/{assessment_id}/intelligence-runs", response_model=s.RunOutput, status_code=201
)
def analyze(assessment_id: UUID, body: s.AnalysisInput, db: Database, user: CurrentUser):
    parent = assessment(db, assessment_id, edit=True)
    snapshot = analysis_snapshot(db, parent, body)
    try:
        result = (
            validate_analysis(body.manual_result.model_dump(), snapshot)
            if body.manual_result
            else None
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return create_run(db, user, parent, "analysis", body, snapshot, result)


@router.post("/assessments/{assessment_id}/evidence-preview", response_model=list[s.EvidenceSource])
def evidence_preview(assessment_id: UUID, body: s.AnalysisInput, db: Database, user: CurrentUser):
    return analysis_snapshot(db, assessment(db, assessment_id), body)["sources"]


@router.get("/intelligence-runs/{run_id}", response_model=s.RunOutput)
def get_run(run_id: UUID, db: Database, user: CurrentUser):
    return run_output(db, run_record(db, run_id))


@router.post("/intelligence-runs/{run_id}/cancel", response_model=s.RunOutput)
def cancel_run(run_id: UUID, db: Database, user: CurrentUser):
    record = run_record(db, run_id, edit=True)
    lock(db, record.id)
    db.refresh(record)
    if record.status not in ("queued", "running", "failed"):
        raise HTTPException(409, "This run has already completed")
    record.status = "canceled"
    record.error = "Canceled by teacher"
    audit(
        db,
        user,
        record.workspace_id,
        "intelligence.canceled",
        record.classroom_id,
        run_id=str(record.id),
    )
    return run_output(db, record)


@router.post("/intelligence-runs/{run_id}/retry", response_model=s.RunOutput)
def retry_run(run_id: UUID, db: Database, user: CurrentUser):
    record = run_record(db, run_id, edit=True)
    lock(db, record.id)
    db.refresh(record)
    if record.status != "failed" or record.attempts >= 3:
        raise HTTPException(409, "Only failed runs with fewer than three attempts can be retried")
    stale, reason = staleness(db, record)
    if stale:
        raise HTTPException(409, reason)
    record.status = "queued"
    record.error = None
    audit(
        db,
        user,
        record.workspace_id,
        "intelligence.retried",
        record.classroom_id,
        run_id=str(record.id),
    )
    return run_output(db, record)


@router.post(
    "/intelligence-runs/{run_id}/findings/{index}/reviews",
    response_model=s.ReviewOutput,
    status_code=201,
)
def review_finding(
    run_id: UUID, index: int, body: s.FindingReviewInput, db: Database, user: CurrentUser
):
    record = run_record(db, run_id, edit=True)
    lock(db, record.id)
    if (
        record.kind != "analysis"
        or record.status != "succeeded"
        or not 0 <= index < len(record.result["findings"])
    ):
        raise HTTPException(404, "Finding not found")
    stale, reason = staleness(db, record)
    if stale:
        raise HTTPException(409, reason)
    old = current_review(db, record.id, index)
    if body.base_version != (old.version if old else 0):
        raise HTTPException(409, "This finding review changed; refresh before reviewing again")
    review = m.FindingReview(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        run_id=record.id,
        finding_index=index,
        version=body.base_version + 1,
        disposition=body.disposition,
        reason=body.reason,
        reviewed_by=user.id,
    )
    db.add(review)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "finding.reviewed",
        record.classroom_id,
        run_id=str(record.id),
        finding_index=index,
        disposition=review.disposition,
    )
    return review


@router.post(
    "/assessments/{assessment_id}/teaching-material", response_model=s.RunOutput, status_code=201
)
def generate_material(assessment_id: UUID, body: s.GenerateInput, db: Database, user: CurrentUser):
    parent = assessment(db, assessment_id, edit=True)
    snapshot = material_snapshot(db, parent, body)
    try:
        result = (
            validate_material(body.manual_content.model_dump(), snapshot)
            if body.manual_content
            else None
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return create_run(db, user, parent, "material", body, snapshot, result)


def material_output(db, item):
    approval = db.scalar(
        select(m.MaterialApproval).where(m.MaterialApproval.material_id == item.id)
    )
    stale, reason = staleness(db, db.get(m.IntelligenceRun, item.run_id))
    return {
        **{
            k: getattr(item, k)
            for k in ["id", "run_id", "classroom_id", "version", "content", "reason", "created_at"]
        },
        "approval_assignment_version_id": approval.assignment_version_id if approval else None,
        "stale": stale,
        "stale_reason": reason,
    }


@router.get("/intelligence-runs/{run_id}/materials", response_model=list[s.MaterialOutput])
def material_versions(run_id: UUID, db: Database, user: CurrentUser):
    run_record(db, run_id)
    return [
        material_output(db, item)
        for item in db.scalars(
            select(m.TeachingMaterial)
            .where(m.TeachingMaterial.run_id == run_id)
            .order_by(m.TeachingMaterial.version.desc())
        )
    ]


@router.post(
    "/intelligence-runs/{run_id}/materials", response_model=s.MaterialOutput, status_code=201
)
def edit_material(run_id: UUID, body: s.MaterialEdit, db: Database, user: CurrentUser):
    record = run_record(db, run_id, edit=True)
    lock(db, record.id)
    if record.kind != "material" or record.status != "succeeded":
        raise HTTPException(409, "Wait for this material run to complete")
    stale, reason = staleness(db, record)
    if stale:
        raise HTTPException(409, reason)
    previous = db.scalar(
        select(m.TeachingMaterial)
        .where(m.TeachingMaterial.run_id == run_id)
        .order_by(m.TeachingMaterial.version.desc())
        .limit(1)
    )
    if not previous or body.base_version != previous.version:
        raise HTTPException(409, "The material changed; refresh before saving")
    try:
        content = validate_material(body.content.model_dump(), record.snapshot)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    item = m.TeachingMaterial(
        workspace_id=record.workspace_id,
        classroom_id=record.classroom_id,
        run_id=record.id,
        version=body.base_version + 1,
        created_by=user.id,
        content=content,
        reason=body.reason,
    )
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "material.revised",
        record.classroom_id,
        material_id=str(item.id),
        version=item.version,
    )
    return material_output(db, item)


@router.post(
    "/teaching-materials/{material_id}/approve", response_model=s.ApprovalOutput, status_code=201
)
def approve_material(material_id: UUID, body: s.MaterialApprove, db: Database, user: CurrentUser):
    item = db.get(m.TeachingMaterial, material_id)
    if not item:
        raise HTTPException(404, "Material not found")
    record = run_record(db, item.run_id, edit=True)
    lock(db, record.id)
    existing = db.scalar(
        select(m.MaterialApproval).where(m.MaterialApproval.material_id == item.id)
    )
    if existing:
        return existing
    newest = db.scalar(
        select(m.TeachingMaterial)
        .where(m.TeachingMaterial.run_id == record.id)
        .order_by(m.TeachingMaterial.version.desc())
        .limit(1)
    )
    if body.base_version != item.version or newest.id != item.id:
        raise HTTPException(409, "Approve the latest reviewed material version")
    stale, reason = staleness(db, record)
    if stale:
        raise HTTPException(409, reason)
    content = validate_material(item.content, record.snapshot)
    instructions = student_material(content)
    scope = {"workspace_id": item.workspace_id, "classroom_id": item.classroom_id}
    assignment = followup.Assignment(**scope, created_by=user.id)
    db.add(assignment)
    db.flush()
    version = followup.AssignmentVersion(
        **scope,
        assignment_id=assignment.id,
        version=1,
        title=content["title"],
        instructions=instructions,
        due_at=None,
        published_at=None,
        reason="Approved teaching material; review audience before publication",
    )
    db.add(version)
    db.flush()
    approval = m.MaterialApproval(
        **scope,
        material_id=item.id,
        assignment_version_id=version.id,
        approved_by=user.id,
        reason=body.reason,
    )
    db.add(approval)
    db.flush()
    audit(
        db,
        user,
        item.workspace_id,
        "material.approved",
        item.classroom_id,
        material_id=str(item.id),
        assignment_version_id=str(version.id),
    )
    return approval


@router.get("/teaching-materials/{material_id}/export")
def export(material_id: UUID, db: Database, user: CurrentUser, answer_key: bool = False):
    item = db.get(m.TeachingMaterial, material_id)
    if not item:
        raise HTTPException(404, "Material not found")
    record = run_record(db, item.run_id)
    approved = bool(
        db.scalar(select(m.MaterialApproval.id).where(m.MaterialApproval.material_id == item.id))
    )
    prefix = (
        "Approved material" if approved else "DRAFT — teacher review required"
    ) + f" · version {item.version}\n\n"
    if not db.scalar(
        text("SELECT chalkmate.record_material_export(:id,:key)"),
        {"id": item.id, "key": answer_key},
    ):
        raise HTTPException(404, "Material not found")
    filename = f"chalkmate-{record.request['material_type']}-v{item.version}"
    filename += "-teacher-key.md" if answer_key else "-student.md"
    return Response(
        prefix + export_material(item.content, answer_key),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
