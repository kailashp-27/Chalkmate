"""Create a confirmed account for this local development installation only."""

import json
import secrets
from pathlib import Path
from urllib.parse import urlparse

import httpx

from chalkmate.config import get_settings

settings = get_settings()
url = urlparse(settings.supabase_url)
if settings.app_env != "development" or url.hostname not in {"127.0.0.1", "localhost"}:
    raise RuntimeError("Demo accounts may only be created on local development Supabase")
credentials = Path(".tmp/demo-credentials.json")
credentials.parent.mkdir(exist_ok=True)
if not credentials.exists():
    email = f"teacher.demo.{secrets.token_hex(3)}@example.com"
    password = f"Chalkmate-{secrets.token_urlsafe(12)}!"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    created = httpx.post(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=headers,
        json={"email": email, "password": password, "email_confirm": True},
        timeout=30,
    )
    created.raise_for_status()
    credentials.write_text(json.dumps({"email": email, "password": password}), encoding="utf-8")
account = json.loads(credentials.read_text(encoding="utf-8"))
login = httpx.post(
    f"{settings.supabase_url}/auth/v1/token?grant_type=password",
    headers={"apikey": settings.supabase_anon_key},
    json=account,
    timeout=30,
)
login.raise_for_status()
with httpx.Client(
    base_url="http://127.0.0.1:8100",
    timeout=30,
    headers={"Authorization": f"Bearer {login.json()['access_token']}"},
) as api:
    session = api.get("/v1/session")
    session.raise_for_status()
    if not session.json()["workspaces"]:
        workspace = api.post("/v1/workspaces", json={"name": "Demo teaching workspace"})
        workspace.raise_for_status()
        classroom = api.post(
            f"/v1/workspaces/{workspace.json()['id']}/classrooms",
            json={
                "name": "Computer Science · Section A",
                "subject": "Data Structures",
                "term": "2026–27",
            },
        )
        classroom.raise_for_status()
print("Confirmed demo account is ready. Credentials saved in ignored .tmp/demo-credentials.json")
