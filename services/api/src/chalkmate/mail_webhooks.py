"""Signed, bounded provider events; no public read/write access to delivery records."""

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from chalkmate.config import get_settings
from chalkmate.mail_provider import verify_webhook
from chalkmate.processing import engine

router = APIRouter(prefix="/v1")


@router.post("/webhooks/resend")
async def resend_webhook(request: Request):
    secret = get_settings().resend_webhook_secret.get_secret_value()
    if not secret:
        raise HTTPException(503, "Webhook verification is not configured")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise HTTPException(413, "Webhook payload is too large")
    try:
        event_id = verify_webhook(bytes(body), request.headers, secret)
        event = json.loads(body)
        provider_id, kind = event["data"]["email_id"], event["type"]
        occurred_at = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
        if not occurred_at.tzinfo or occurred_at > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Invalid timestamp")
        if not isinstance(provider_id, str) or len(provider_id) > 180 or len(kind) > 80:
            raise ValueError("Invalid event")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, "Webhook signature or payload is invalid") from exc
    with engine().begin() as connection:
        connection.execute(
            text(
                "SELECT chalkmate.record_delivery_event(:event_id,:provider_id,:kind,:occurred_at)"
            ),
            {
                "event_id": event_id,
                "provider_id": provider_id,
                "kind": kind,
                "occurred_at": occurred_at,
            },
        )
    return {"received": True}
