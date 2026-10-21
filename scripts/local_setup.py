"""Configure this checkout from the running local Supabase stack, without printing keys."""

import json
import os
import secrets
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = subprocess.run(
        [
            str(
                ROOT
                / (
                    "node_modules/.bin/supabase.cmd"
                    if os.name == "nt"
                    else "node_modules/.bin/supabase"
                )
            ),
            "status",
            "-o",
            "json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    details = json.loads(result.stdout)
    password = secrets.token_urlsafe(32)
    worker_password = secrets.token_urlsafe(32)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                existing = urlsplit(line.split("=", 1)[1])
                if existing.username == "chalkmate_app" and existing.hostname == "127.0.0.1":
                    password = existing.password or password
            elif line.startswith("WORKER_DATABASE_URL="):
                existing = urlsplit(line.split("=", 1)[1])
                if existing.username == "chalkmate_worker" and existing.hostname == "127.0.0.1":
                    worker_password = existing.password or worker_password
    admin_url = details["DB_URL"]
    api_url = details["API_URL"]
    database_url = f"postgresql+psycopg://chalkmate_app:{password}@127.0.0.1:54322/postgres"
    backend = {
        "APP_ENV": "development",
        "DATABASE_URL": database_url,
        "WORKER_DATABASE_URL": f"postgresql+psycopg://chalkmate_worker:{worker_password}@127.0.0.1:54322/postgres",
        "WORKER_CONTAINER_DATABASE_URL": f"postgresql+psycopg://chalkmate_worker:{worker_password}@host.docker.internal:54322/postgres",
        "MIGRATION_DATABASE_URL": admin_url.replace("postgresql://", "postgresql+psycopg://"),
        "CELERY_BROKER_URL": "redis://127.0.0.1:6379/0",
        "SUPABASE_URL": api_url,
        "SUPABASE_ANON_KEY": details["ANON_KEY"],
        "SUPABASE_SERVICE_ROLE_KEY": details["SERVICE_ROLE_KEY"],
        "WEB_ORIGIN": os.environ.get("WEB_ORIGIN", "http://localhost:3000"),
        "OLLAMA_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "gemma3:4b",
        "OLLAMA_VISION_MODEL": "gemma3:4b",
    }
    # Preserve user-supplied model selections and unrelated local configuration.
    if env_path.exists():
        existing_values = dict(
            line.split("=", 1)
            for line in env_path.read_text().splitlines()
            if "=" in line and not line.startswith("#")
        )
        for key, value in existing_values.items():
            if key not in backend or key.startswith("OLLAMA_"):
                backend[key] = value
    # This script is intentionally local-only; never point it at hosted credentials.
    if not api_url.startswith("http://127.0.0.1:"):
        raise RuntimeError("Expected local Supabase")
    (ROOT / ".env").write_text("\n".join(f"{k}={v}" for k, v in backend.items()) + "\n")
    from chalkmate.config import get_settings

    get_settings.cache_clear()
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("ALTER ROLE chalkmate_app PASSWORD {}").format(sql.Literal(password))
        )
        connection.execute(
            sql.SQL("ALTER ROLE chalkmate_worker PASSWORD {}").format(sql.Literal(worker_password))
        )
    web = {
        "NEXT_PUBLIC_SUPABASE_URL": api_url,
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": details["ANON_KEY"],
        "NEXT_PUBLIC_API_URL": "http://127.0.0.1:8100",
    }
    (ROOT / "apps/web/.env.local").write_text("\n".join(f"{k}={v}" for k, v in web.items()) + "\n")
    headers = {
        "apikey": details["SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {details['SERVICE_ROLE_KEY']}",
    }
    response = httpx.post(
        f"{api_url}/storage/v1/bucket",
        headers=headers,
        json={
            "id": "classroom-files",
            "name": "classroom-files",
            "public": False,
            "file_size_limit": 10485760,
            "allowed_mime_types": ["application/pdf", "image/jpeg", "image/png"],
        },
        timeout=30,
    )
    if response.status_code not in (200, 201, 409):
        # Storage returns 400 for a bucket that already exists on some versions.
        existing = httpx.get(f"{api_url}/storage/v1/bucket/classroom-files", headers=headers)
        existing.raise_for_status()
        if existing.json().get("public"):
            raise RuntimeError("Expected a private storage bucket")
    print("Local configuration saved; migrations applied; private storage is ready.")


if __name__ == "__main__":
    main()
