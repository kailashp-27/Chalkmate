"""One-recipient mail transports. Development mail is captured, never relayed."""

import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from email.utils import parseaddr
from urllib.parse import urlsplit

import httpx

from chalkmate.config import get_settings


class ProviderFailure(Exception):
    def __init__(self, public_detail, definite=False):
        self.public_detail, self.definite = public_detail, definite
        super().__init__(public_detail)


def mailpit_url():
    settings = get_settings()
    parsed = urlsplit(settings.mailpit_url)
    if (
        settings.app_env not in ("development", "test")
        or parsed.scheme != "http"
        or parsed.hostname not in ("localhost", "127.0.0.1", "host.docker.internal")
        or parsed.username
        or parsed.password
        or parsed.port != 54324
    ):
        raise ProviderFailure("Mailpit capture is restricted to the local development inbox", True)
    return settings.mailpit_url.rstrip("/")


def mail_status():
    settings = get_settings()
    provider = settings.mail_provider
    available, detail, inbox = (
        False,
        "Email is disabled. Configure a transport before approving a send.",
        None,
    )
    if provider == "mailpit":
        try:
            mailpit_url()
            available, detail = (
                True,
                "Development emails are captured in the local inbox. They are not "
                "delivered to Gmail.",
            )
            inbox = "http://127.0.0.1:54324"
        except ProviderFailure as exc:
            detail = exc.public_detail
    elif provider == "resend":
        available = bool(
            settings.enable_external_email
            and settings.resend_api_key.get_secret_value()
            and settings.mail_from
        )
        detail = (
            "External email is enabled through Resend. Each campaign requires teacher approval."
            if available
            else (
                "Set a verified sender, server-side Resend key, and explicit "
                "external-email enable flag."
            )
        )
    return {
        "provider": provider,
        "available": available,
        "external": provider == "resend",
        "detail": detail,
        "inbox_url": inbox,
    }


def message_id(delivery_id):
    return f"chalkmate-{delivery_id}@chalkmate.local"


def captured_message(delivery_id):
    try:
        response = httpx.get(
            f"{mailpit_url()}/api/v1/search",
            params={"query": f"tag:chalkmate-{delivery_id}"},
            timeout=10,
        )
        response.raise_for_status()
        matches = response.json().get("messages", [])
        exact = [
            item
            for item in matches
            if item.get("MessageID", "").strip("<>") == message_id(delivery_id)
        ]
        return exact[0]["ID"] if exact else None
    except httpx.HTTPError as exc:
        raise ProviderFailure(
            "The local inbox could not be checked; delivery remains uncertain"
        ) from exc


def send(provider, delivery_id, payload):
    settings = get_settings()
    ready = mail_status()
    if provider != ready["provider"] or not ready["available"]:
        raise ProviderFailure("The approved mail transport is unavailable or changed", True)
    try:
        if provider == "mailpit":
            try:
                existing = captured_message(delivery_id)
            except ProviderFailure as exc:
                raise ProviderFailure(
                    "The local inbox is unavailable; no new message was sent", True
                ) from exc
            if existing:
                return "captured", existing
            sender_name, sender_email = parseaddr(payload["from"])
            response = httpx.post(
                f"{mailpit_url()}/api/v1/send",
                json={
                    "From": {"Email": sender_email, "Name": sender_name or "Chalkmate"},
                    "To": [{"Email": payload["to"]}],
                    "Subject": payload["subject"],
                    "Text": payload["text"],
                    "Headers": {"Message-ID": f"<{message_id(delivery_id)}>"},
                    "Tags": ["chalkmate", f"chalkmate-{delivery_id}"],
                },
                timeout=20,
            )
            if response.is_success:
                provider_id = response.json().get("ID")
                if not provider_id:
                    raise ProviderFailure(
                        "Mail capture may have succeeded but its receipt is missing"
                    )
                return "captured", provider_id
        elif provider == "resend":
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
                    "Idempotency-Key": f"chalkmate/{delivery_id}",
                },
                json={
                    "from": payload["from"],
                    "to": [payload["to"]],
                    "subject": payload["subject"],
                    "text": payload["text"],
                },
                timeout=20,
            )
            if response.is_success:
                provider_id = response.json().get("id")
                if not provider_id:
                    raise ProviderFailure(
                        "The provider may have accepted this message without returning its receipt"
                    )
                return "accepted", provider_id
        else:
            raise ProviderFailure("No mail transport is configured", True)
    except httpx.ConnectError as exc:
        raise ProviderFailure(
            "Could not connect to the mail service; no request was accepted", True
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderFailure(
            "The mail service response was lost or invalid; reconcile before retrying"
        ) from exc
    # A server error or idempotency conflict may follow acceptance: never retry blindly.
    if 400 <= response.status_code < 500 and response.status_code != 409:
        raise ProviderFailure(
            "The mail service rejected this request. Check sender/transport "
            "configuration before retrying.",
            True,
        )
    raise ProviderFailure("The provider outcome is uncertain. Reconcile before retrying.")


def reconcile(provider, delivery):
    if provider == "mailpit":
        found = captured_message(delivery.id)
        if found:
            return "captured", found
        raise ProviderFailure(
            "No matching captured receipt was found. The item remains "
            "uncertain; do not resend blindly."
        )
    settings = get_settings()
    if provider != "resend" or not settings.resend_api_key.get_secret_value():
        raise ProviderFailure("Configure the original mail provider to reconcile this item")
    if delivery.provider_id:
        try:
            response = httpx.get(
                f"https://api.resend.com/emails/{delivery.provider_id}",
                headers={"Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}"},
                timeout=15,
            )
            response.raise_for_status()
            event = response.json().get("last_event", "sent")
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderFailure("The provider receipt could not be retrieved") from exc
        return {
            "delivered": "delivered",
            "bounced": "bounced",
            "complained": "bounced",
            "failed": "held",
        }.get(event, "accepted"), delivery.provider_id
    if not delivery.first_attempt_at or datetime.now(UTC) - delivery.first_attempt_at > timedelta(
        hours=23
    ):
        raise ProviderFailure(
            "The safe idempotency window has expired. Keep this item held and "
            "verify it with the provider; automatic resend is blocked."
        )
    # Reuse the exact immutable request and key while provider deduplication is valid.
    return send(provider, delivery.id, delivery.payload)


def verify_webhook(body, headers, secret, now=None):
    now = time.time() if now is None else now
    try:
        event_id, timestamp, signatures = (
            headers["svix-id"],
            headers["svix-timestamp"],
            headers["svix-signature"],
        )
        if len(event_id) > 180 or abs(now - int(timestamp)) > 300:
            raise ValueError("Expired webhook")
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
        if len(key) < 16:
            raise ValueError("Invalid secret")
        signed = event_id.encode() + b"." + timestamp.encode() + b"." + body
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
        if not any(hmac.compare_digest(part, f"v1,{expected}") for part in signatures.split()):
            raise ValueError("Invalid signature")
        return event_id
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Webhook signature could not be verified") from exc
