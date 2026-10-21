"""Bounded staff-only dependency checks; no connection strings or student records."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
from redis import Redis
from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from chalkmate.config import get_settings
from chalkmate.db import Base
from chalkmate.ollama_provider import local_url


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def check_service(name):
    settings = get_settings()
    try:
        if name == "Queue":
            with Redis.from_url(
                settings.celery_broker_url, socket_connect_timeout=2, socket_timeout=2
            ) as broker:
                broker.ping()
        else:
            headers = {}
            if name == "Local AI":
                url = local_url() + "/api/tags"
            else:
                url = settings.supabase_url + (
                    "/auth/v1/health" if name == "Sign-in" else "/storage/v1/status"
                )
                headers = {
                    "apikey": settings.supabase_anon_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                }
            with httpx.Client(timeout=2, follow_redirects=False) as client:
                client.get(url, headers=headers).raise_for_status()
        return {"name": name, "state": "ready", "detail": "Responding locally"}
    except Exception:
        return {
            "name": name,
            "state": "optional" if name == "Local AI" else "unavailable",
            "detail": "Start local Ollama for AI drafts; manual tools remain available"
            if name == "Local AI"
            else "Not responding; check the local service",
        }


def service_checks(db, class_id):
    db.execute(text("SELECT 1"))
    checks = [
        {"name": "Database", "state": "ready", "detail": "Connection and classroom access verified"}
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        checks += list(pool.map(check_service, ["Sign-in", "Private files", "Queue", "Local AI"]))
    last = db.scalar(text("SELECT chalkmate.worker_seen(:id)"), {"id": class_id})
    healthy = last is not None and (datetime.now(UTC) - last).total_seconds() < 50
    checks.append(
        {
            "name": "Worker",
            "state": "ready" if healthy else "unavailable",
            "detail": "Seen within the last 50 seconds"
            if healthy
            else "No recent heartbeat; resume the worker and scheduler",
        }
    )
    recovery = {"verified": False, "verified_at": None}
    try:
        report = json.loads(Path(get_settings().recovery_report_path).read_text(encoding="utf-8"))
        # Expose only these fields. Bundles, paths and other classrooms remain private.
        recovery = {
            "verified": report.get("verified") is True,
            "verified_at": datetime.fromisoformat(report["verified_at"]).isoformat(),
        }
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return checks, recovery
