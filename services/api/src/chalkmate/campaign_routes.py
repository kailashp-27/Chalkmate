"""Private recipient previews and explicit campaign approvals."""

import secrets
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, text

from chalkmate import followup_models as m
from chalkmate import followup_schemas as s
from chalkmate.assignment_routes import version_record
from chalkmate.auth import CurrentUser, Database
from chalkmate.followup_rules import (
    build_snapshot,
    personal_message,
    revalidate_delivery,
    snapshot_digest,
)
from chalkmate.mail_provider import mail_status
from chalkmate.routes import audit, classroom

router = APIRouter(prefix="/v1")


def campaign(db, campaign_id, edit=False):
    record = db.get(m.Campaign, campaign_id)
    if not record:
        raise HTTPException(404, "Campaign not found")
    classroom(db, record.classroom_id, edit=edit, active=edit)
    return record


def campaign_output(db, record):
    counts = Counter(
        db.scalars(select(m.Delivery.status).where(m.Delivery.campaign_id == record.id))
    )
    return {
        **{
            key: getattr(record, key)
            for key in [
                "id",
                "assignment_version_id",
                "scheduled_at",
                "provider",
                "canceled",
                "created_at",
                "request",
            ]
        },
        "counts": dict(counts),
    }


def delivery(db, delivery_id, edit=False):
    record = db.get(m.Delivery, delivery_id)
    if not record:
        raise HTTPException(404, "Delivery not found")
    parent = campaign(db, record.campaign_id, edit)
    if edit:
        db.execute(select(m.Delivery.id).where(m.Delivery.id == record.id).with_for_update())
        db.refresh(record)
    return record, parent


def delivery_output(record):
    return {
        **{
            key: getattr(record, key)
            for key in [
                "id",
                "student_id",
                "status",
                "attempts",
                "provider_id",
                "detail",
                "created_at",
            ]
        },
        "student_name": record.snapshot["student_name"],
        "email": record.snapshot["email"],
    }


@router.get("/mail/status", response_model=s.MailStatus)
def email_status(user: CurrentUser):
    return mail_status()


@router.post(
    "/classrooms/{classroom_id}/campaign-previews", response_model=s.PreviewOutput, status_code=201
)
def create_preview(classroom_id: UUID, body: s.PreviewInput, db: Database, user: CurrentUser):
    parent = classroom(db, classroom_id, edit=True, active=True)
    snapshot = build_snapshot(db, classroom_id, body)
    values = body.model_dump(mode="json")
    preview = m.CampaignPreview(
        workspace_id=parent.workspace_id,
        classroom_id=parent.id,
        assignment_version_id=body.assignment_version_id,
        created_by=user.id,
        request=values,
        snapshot=snapshot,
        digest=snapshot_digest({"request": values, "snapshot": snapshot}),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(preview)
    db.flush()
    audit(
        db,
        user,
        parent.workspace_id,
        "campaign.previewed",
        parent.id,
        preview_id=str(preview.id),
        selected=snapshot["selected_count"],
    )
    return preview


@router.get(
    "/campaign-previews/{preview_id}/recipients/{student_id}", response_model=s.PersonalMessage
)
def preview_message(preview_id: UUID, student_id: UUID, db: Database, user: CurrentUser):
    preview = db.get(m.CampaignPreview, preview_id)
    if not preview:
        raise HTTPException(404, "Preview not found")
    classroom(db, preview.classroom_id)
    row = next(
        (
            r
            for r in preview.snapshot["rows"]
            if r["student_id"] == str(student_id)
            and r["eligible"]
            and not r["excluded"]
            and not r["blocked"]
        ),
        None,
    )
    if not row:
        raise HTTPException(404, "Contactable preview recipient not found")
    request = s.PreviewInput.model_validate(preview.request)
    message = personal_message(preview.assignment_version_id, request, preview.snapshot, row)
    return {
        **message,
        "student_id": student_id,
        "assignment_link": (
            f"{preview.snapshot['web_origin'].rstrip('/')}/assignments/"
            f"{preview.assignment_version_id}"
        ),
    }


@router.post(
    "/classrooms/{classroom_id}/campaigns", response_model=s.CampaignOutput, status_code=201
)
def approve_campaign(classroom_id: UUID, body: s.ApproveCampaign, db: Database, user: CurrentUser):
    parent = classroom(db, classroom_id, edit=True, active=True)
    preview = db.get(m.CampaignPreview, body.preview_id)
    if not preview or preview.classroom_id != classroom_id:
        raise HTTPException(404, "Preview not found")
    if not secrets.compare_digest(preview.digest, body.digest):
        raise HTTPException(409, "Preview approval does not match")
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": preview.id.int % (2**63 - 1)})
    existing = db.scalar(select(m.Campaign).where(m.Campaign.preview_id == preview.id))
    if existing:
        return campaign_output(db, existing)
    if preview.expires_at < datetime.now(UTC):
        raise HTTPException(409, "Preview expired. Create a fresh preview.")
    request = s.PreviewInput.model_validate(preview.request)
    current = build_snapshot(db, classroom_id, request)
    if snapshot_digest({"request": preview.request, "snapshot": current}) != preview.digest:
        raise HTTPException(
            409, "Scores, contacts, enrollment, or assignment changed. Create a fresh preview."
        )
    if current["blocked_count"] or not current["selected_count"]:
        raise HTTPException(
            409, "Resolve or explicitly exclude blocked recipients, and select at least one student"
        )
    provider = mail_status()
    if not provider["available"]:
        raise HTTPException(409, provider["detail"])
    scheduled = body.scheduled_at or datetime.now(UTC)
    if scheduled < datetime.now(UTC) - timedelta(seconds=30) or scheduled > datetime.now(
        UTC
    ) + timedelta(days=365):
        raise HTTPException(422, "Choose a send time now or within the next year")
    version = version_record(db, preview.assignment_version_id)
    record = m.Campaign(
        workspace_id=parent.workspace_id,
        classroom_id=parent.id,
        assignment_version_id=version.id,
        preview_id=preview.id,
        approved_by=user.id,
        request=preview.request,
        scheduled_at=scheduled,
        provider=provider["provider"],
    )
    db.add(record)
    db.flush()
    for row in current["rows"]:
        if row["eligible"] and not row["excluded"]:
            db.add(
                m.Delivery(
                    workspace_id=parent.workspace_id,
                    classroom_id=parent.id,
                    campaign_id=record.id,
                    student_id=UUID(row["student_id"]),
                    snapshot=row,
                    payload=personal_message(version.id, request, current, row),
                )
            )
    db.flush()
    audit(
        db,
        user,
        parent.workspace_id,
        "campaign.approved",
        parent.id,
        campaign_id=str(record.id),
        preview_id=str(preview.id),
        recipients=current["selected_count"],
        scheduled_at=scheduled.isoformat(),
        provider=provider["provider"],
    )
    return campaign_output(db, record)


@router.get("/classrooms/{classroom_id}/campaigns", response_model=list[s.CampaignOutput])
def list_campaigns(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id)
    return [
        campaign_output(db, item)
        for item in db.scalars(
            select(m.Campaign)
            .where(m.Campaign.classroom_id == classroom_id)
            .order_by(m.Campaign.created_at.desc())
        )
    ]


@router.get("/campaigns/{campaign_id}/deliveries", response_model=list[s.DeliveryOutput])
def list_deliveries(campaign_id: UUID, db: Database, user: CurrentUser):
    campaign(db, campaign_id)
    return [
        delivery_output(item)
        for item in db.scalars(
            select(m.Delivery)
            .where(m.Delivery.campaign_id == campaign_id)
            .order_by(m.Delivery.created_at, m.Delivery.id)
        )
    ]


@router.get("/deliveries/{delivery_id}/attempts", response_model=list[s.AttemptOutput])
def delivery_attempts(delivery_id: UUID, db: Database, user: CurrentUser):
    delivery(db, delivery_id)
    return list(
        db.scalars(
            select(m.DeliveryAttempt)
            .where(m.DeliveryAttempt.delivery_id == delivery_id)
            .order_by(m.DeliveryAttempt.created_at.desc())
        )
    )


@router.post("/campaigns/{campaign_id}/cancel", response_model=s.CampaignOutput)
def cancel_campaign(campaign_id: UUID, db: Database, user: CurrentUser):
    record = campaign(db, campaign_id, edit=True)
    record.canceled = True
    for item in db.scalars(
        select(m.Delivery).where(
            m.Delivery.campaign_id == record.id, m.Delivery.status.in_(["queued", "failed", "held"])
        )
    ):
        item.status, item.detail = "canceled", "Teacher canceled this campaign"
    audit(
        db,
        user,
        record.workspace_id,
        "campaign.canceled",
        record.classroom_id,
        campaign_id=str(record.id),
    )
    db.flush()
    return campaign_output(db, record)


@router.post("/deliveries/{delivery_id}/retry", response_model=s.DeliveryOutput)
def retry_delivery(delivery_id: UUID, db: Database, user: CurrentUser):
    item, parent = delivery(db, delivery_id, edit=True)
    if item.status != "failed" or item.attempts >= 3:
        raise HTTPException(
            409, "Only confirmed failures with fewer than three attempts can be retried"
        )
    status, detail = revalidate_delivery(db, parent, item)
    if status:
        raise HTTPException(409, detail)
    item.status, item.detail = "queued", "Teacher requested a retry after confirmed failure"
    audit(
        db, user, item.workspace_id, "delivery.retried", item.classroom_id, delivery_id=str(item.id)
    )
    return delivery_output(item)


@router.post("/deliveries/{delivery_id}/cancel", response_model=s.DeliveryOutput)
def cancel_delivery(delivery_id: UUID, db: Database, user: CurrentUser):
    item, _ = delivery(db, delivery_id, edit=True)
    if item.status not in ("queued", "failed", "held"):
        raise HTTPException(409, "Only pending or confirmed-unsent messages can be canceled")
    item.status, item.detail = "canceled", "Teacher canceled this recipient"
    audit(
        db,
        user,
        item.workspace_id,
        "delivery.canceled",
        item.classroom_id,
        delivery_id=str(item.id),
    )
    return delivery_output(item)


@router.post("/deliveries/{delivery_id}/reconcile", response_model=s.DeliveryOutput)
def reconcile_delivery(delivery_id: UUID, db: Database, user: CurrentUser):
    from chalkmate.mail_provider import ProviderFailure, reconcile

    item, parent = delivery(db, delivery_id, edit=True)
    if item.status not in ("uncertain", "accepted"):
        raise HTTPException(
            409, "Only uncertain or provider-accepted deliveries need reconciliation"
        )
    # An existing provider ID can be looked up even after eligibility changes; this never sends.
    if not item.provider_id:
        status, detail = revalidate_delivery(db, parent, item)
        if status:
            raise HTTPException(409, detail)
    try:
        outcome, provider_id = reconcile(parent.provider, item)
    except ProviderFailure as exc:
        raise HTTPException(409, exc.public_detail) from exc
    item.status, item.provider_id, item.detail = (
        outcome,
        provider_id,
        "Teacher reconciled the provider outcome",
    )
    db.add(
        m.DeliveryAttempt(
            workspace_id=item.workspace_id,
            classroom_id=item.classroom_id,
            delivery_id=item.id,
            outcome=outcome,
            detail=item.detail,
            provider_id=provider_id,
        )
    )
    audit(
        db,
        user,
        item.workspace_id,
        "delivery.reconciled",
        item.classroom_id,
        delivery_id=str(item.id),
    )
    return delivery_output(item)
