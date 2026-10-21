"""Lease-based recipient dispatch from the transactional campaign outbox."""

from uuid import UUID

from sqlalchemy import select, text

from chalkmate import followup_models as m
from chalkmate.auth import Identity
from chalkmate.followup_rules import revalidate_delivery
from chalkmate.mail_provider import ProviderFailure, send
from chalkmate.processing import engine, scoped_session
from chalkmate.worker import celery_app


@celery_app.task(name="chalkmate.dispatch_deliveries")
def dispatch_deliveries():
    with engine().begin() as connection:
        ids = list(connection.scalars(text("SELECT chalkmate.pending_deliveries()")))
    for delivery_id in ids:
        process_delivery.delay(str(delivery_id))


@celery_app.task(name="chalkmate.process_delivery", soft_time_limit=90, time_limit=110)
def process_delivery(delivery_id):
    delivery_id = UUID(delivery_id)
    with engine().begin() as connection:
        claim = connection.execute(
            text("SELECT * FROM chalkmate.claim_delivery(:id)"), {"id": delivery_id}
        ).first()
    if not claim:
        return
    actor = Identity(claim.actor_id, claim.email)
    try:
        with scoped_session(actor) as db:
            item = db.scalar(
                select(m.Delivery).where(m.Delivery.id == delivery_id).with_for_update()
            )
            if not item or item.status != "sending":
                return
            parent = db.scalar(
                select(m.Campaign).where(m.Campaign.id == item.campaign_id).with_for_update()
            )
            status, detail = revalidate_delivery(db, parent, item)
            provider_id = None
            if not status:
                try:
                    status, provider_id = send(parent.provider, item.id, item.payload)
                except ProviderFailure as exc:
                    status, detail = ("failed" if exc.definite else "uncertain"), exc.public_detail
                else:
                    detail = (
                        "Captured in the local test inbox"
                        if status == "captured"
                        else "Accepted by the email provider; awaiting delivery confirmation"
                    )
            item.status, item.detail, item.provider_id = status, detail, provider_id
            item.lease_until = None
            db.add(
                m.DeliveryAttempt(
                    workspace_id=item.workspace_id,
                    classroom_id=item.classroom_id,
                    delivery_id=item.id,
                    outcome=status,
                    detail=detail,
                    provider_id=provider_id,
                )
            )
            db.commit()
    except Exception:
        # No blind resend: the claim remains sending until lease expiry marks it uncertain.
        # This covers a provider accepting mail followed by a lost DB commit or worker crash.
        return
