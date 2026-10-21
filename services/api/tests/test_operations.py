from datetime import UTC, datetime

import httpx
import psycopg
from conftest import auth
from sqlalchemy import text

from chalkmate import operations
from chalkmate.processing import engine


def test_optional_ai_failure_preserves_manual_tools(monkeypatch):
    class BrokenClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args, **kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(operations.httpx, "Client", BrokenClient)
    assert operations.check_service("Local AI")["state"] == "optional"
    assert "manual" in operations.check_service("Local AI")["detail"]
    assert operations.check_service("Private files")["state"] == "unavailable"


def test_worker_heartbeat_is_scoped_and_cannot_be_forged_by_app(
    owner, accounts, api_client, environment
):
    account, workspace, classroom = owner
    with engine().begin() as db:
        db.execute(text("SELECT chalkmate.record_worker_heartbeat()"))
    with psycopg.connect(
        environment.database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute("SELECT set_config('app.user_id',%s,true)", (account["id"],))
        seen = db.execute("SELECT chalkmate.worker_seen(%s)", (classroom["id"],)).fetchone()[0]
        assert abs((datetime.now(UTC) - seen).total_seconds()) < 10
        db.execute("SELECT set_config('app.user_id',%s,true)", (accounts()["id"],))
        assert (
            db.execute("SELECT chalkmate.worker_seen(%s)", (classroom["id"],)).fetchone()[0] is None
        )
        try:
            db.execute("SELECT chalkmate.record_worker_heartbeat()")
            raise AssertionError("API role must not forge worker heartbeats")
        except psycopg.errors.InsufficientPrivilege:
            pass
    assert (
        api_client.get(
            f"/v1/classrooms/{classroom['id']}/readiness", headers=auth(account)
        ).status_code
        == 200
    )
