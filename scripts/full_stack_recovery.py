"""Local signed backup bundles and isolated Supabase recovery rehearsals.

Commands: backup; drill BUNDLE [--cleanup]; rehearse [--cleanup].
Never restore into the source stack. No raw records, keys or passwords are printed.
"""

import argparse
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql

from chalkmate.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / ("node_modules/.bin/supabase.cmd" if os.name == "nt" else "node_modules/.bin/supabase")
EXCLUDE = "realtime,imgproxy,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor"
SCHEMAS = ("chalkmate", "auth", "storage")
OMIT = {("auth", "schema_migrations"), ("storage", "migrations")}


def run(args, *, data=None, env=None, timeout=300):
    try:
        value = subprocess.run(
            [str(a) for a in args], input=data, capture_output=True, env=env, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "Local recovery tool did not finish; original stack was not restored over"
        ) from exc
    if value.returncode:
        raise RuntimeError(
            f"Local recovery operation failed ({Path(str(args[0])).name}); no credentials logged"
        )
    return value.stdout


def docker(*args, **kwargs):
    return run(["docker", *args], **kwargs)


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        rows = list(csv.reader(io.StringIO(run(["whoami", "/user", "/fo", "csv", "/nh"]).decode())))
        sid = rows[0][-1]
        if not re.fullmatch(r"S-1-[0-9-]+", sid):
            raise RuntimeError("Could not determine the current Windows identity")
        run(["icacls", path, "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"])
    else:
        path.chmod(0o700)


def signing_key(create=False):
    folder = ROOT / ".tmp/recovery-secrets"
    path = folder / "signing.key"
    if not path.exists():
        if not create:
            raise ValueError(
                "Recovery signing key is missing; keep it separately with your backups"
            )
        private_folder(folder)
        path.write_bytes(secrets.token_bytes(32))
        if os.name != "nt":
            path.chmod(0o600)
    if path.is_symlink() or len(path.read_bytes()) != 32:
        raise ValueError("Invalid local signing key")
    return path.read_bytes()


def safe_path(folder, relative):
    item = PurePosixPath(relative)
    if (
        item.is_absolute()
        or not item.parts
        or any(p in ("..", ".") or ":" in p or "\\" in p for p in item.parts)
    ):
        raise ValueError("Unsafe backup path")
    target = folder.joinpath(*item.parts)
    for parent in [target, *target.parents]:
        if parent == folder.parent:
            break
        if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
            raise ValueError("Linked backup paths are not allowed")
    if not target.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Backup path escaped its folder")
    return target


def artifacts(folder):
    output = {}
    for path in folder.rglob("*"):
        if path.name in ("manifest.json", "manifest.signature"):
            continue
        relative = path.relative_to(folder).as_posix()
        safe_path(folder, relative)
        if path.is_file():
            output[relative] = {"sha256": sha(path), "bytes": path.stat().st_size}
    return output


def load_bundle(folder):
    folder = Path(folder).resolve()
    if not folder.is_relative_to(ROOT / ".tmp"):
        raise ValueError("Copy private recovery bundles under this checkout's ignored .tmp folder")
    safe_path(folder, "manifest.json")
    safe_path(folder, "manifest.signature")
    raw = (folder / "manifest.json").read_bytes()
    expected = hmac.new(signing_key(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, (folder / "manifest.signature").read_text().strip()):
        raise ValueError("Backup signature did not verify")
    manifest = json.loads(raw)
    if manifest.get("version") != 1 or artifacts(folder) != manifest["artifacts"]:
        raise ValueError("Backup content is missing or changed")
    return folder, manifest


def local_settings():
    settings = get_settings()
    if (
        settings.app_env != "development"
        or urlsplit(settings.supabase_url).hostname not in ("127.0.0.1", "localhost")
        or urlsplit(settings.migration_database_url).hostname not in ("127.0.0.1", "localhost")
    ):
        raise ValueError("Only the local development stack is supported")
    return settings


def cli_status(workdir=ROOT):
    return json.loads(run([CLI, "status", "--workdir", workdir, "-o", "json"]))


def table_hashes(db):
    output = {}
    for schema, table in db.execute(
        "SELECT schemaname,tablename FROM pg_tables WHERE schemaname=ANY(%s) ORDER BY 1,2",
        (list(SCHEMAS),),
    ):
        if (schema, table) in OMIT:
            continue
        query = sql.SQL(
            "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) "
            "FROM (SELECT md5(row_to_json(t)::text) h FROM {}.{} t) rows"
        ).format(sql.Identifier(schema), sql.Identifier(table))
        count, checksum = db.execute(query).fetchone()
        output[f"{schema}.{table}"] = {"count": count, "checksum": checksum}
    return output


def request(method, url, **kwargs):
    r = httpx.request(method, url, timeout=30, **kwargs)
    if r.is_error:
        raise RuntimeError(f"Local recovery HTTP check failed ({r.status_code})")
    return r


def auth_headers(key):
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def storage_layout(info):
    env = dict(item.split("=", 1) for item in info["Config"]["Env"])
    folder = env.get("FILE_STORAGE_BACKEND_PATH", "")
    if (
        env.get("STORAGE_BACKEND") != "file"
        or not folder.startswith("/")
        or ".." in PurePosixPath(folder).parts
    ):
        raise ValueError("Only local file-backed Storage is supported")
    if not any(
        m["Type"] == "volume" and PurePosixPath(folder).is_relative_to(m["Destination"])
        for m in info.get("Mounts", [])
    ):
        raise ValueError("Storage files are not in the expected data volume")
    return {"path": folder, "tenant": env.get("TENANT_ID"), "bucket": env.get("GLOBAL_S3_BUCKET")}


def create_probe():
    settings = local_settings()
    email, password = f"e2e-recovery-{uuid4().hex}@example.com", secrets.token_urlsafe(28)
    user = request(
        "POST",
        settings.supabase_url + "/auth/v1/admin/users",
        headers=auth_headers(settings.supabase_service_role_key),
        json={"email": email, "password": password, "email_confirm": True},
    ).json()
    token = request(
        "POST",
        settings.supabase_url + "/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key},
        json={"email": email, "password": password},
    ).json()["access_token"]
    api_url = "http://127.0.0.1:8100/v1"
    headers = {"Authorization": f"Bearer {token}"}
    ws = request(
        "POST", api_url + "/workspaces", headers=headers, json={"name": "Synthetic recovery probe"}
    ).json()
    classroom = request(
        "POST",
        api_url + f"/workspaces/{ws['id']}/classrooms",
        headers=headers,
        json={
            "name": "Recovery probe",
            "subject": "Synthetic verification",
            "term": "Local rehearsal",
        },
    ).json()
    from create_test_pdf import paper_bytes

    content = paper_bytes()
    file = request(
        "POST",
        api_url + f"/classrooms/{classroom['id']}/files",
        headers=headers,
        files={"file": ("recovery-probe.pdf", content, "application/pdf")},
    ).json()
    return {
        "user_id": user["id"],
        "email": email,
        "password": password,
        "classroom_id": classroom["id"],
        "file_id": file["id"],
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def backup(probe=None):
    settings = local_settings()
    config = (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    project = tomllib.loads(config)["project_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project):
        raise ValueError("Unexpected local project name")
    container = f"supabase_db_{project}"
    storage = f"supabase_storage_{project}"
    info = json.loads(docker("inspect", container))[0]
    auth_info = json.loads(docker("inspect", f"supabase_auth_{project}"))[0]
    storage_info = json.loads(docker("inspect", storage))[0]
    layout = storage_layout(storage_info)
    bundle = ROOT / ".tmp/backups" / uuid4().hex
    private_folder(bundle)
    (bundle / "supabase.toml").write_text(config, encoding="utf-8")
    print("Capturing a consistent local database snapshot…", flush=True)
    with psycopg.connect(
        settings.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        snapshot = db.execute("SELECT pg_export_snapshot()").fetchone()[0]
        hashes = table_hashes(db)
        objects = [
            dict(zip(["bucket", "name", "version"], row, strict=True))
            for row in db.execute(
                "SELECT bucket_id,name,version FROM storage.objects ORDER BY bucket_id,name"
            )
        ]
        selections = {
            "application": ["--schema=chalkmate"],
            "auth": ["--schema=auth", "--data-only", "--exclude-table-data=auth.schema_migrations"],
            "storage": [
                "--schema=storage",
                "--data-only",
                "--exclude-table-data=storage.migrations",
            ],
            "migration": ["--table=public.alembic_version"],
        }
        for name, flags in selections.items():
            remote = f"/tmp/chalkmate-backup-{bundle.name}-{name}.dump"
            docker(
                "exec",
                container,
                "pg_dump",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-Fc",
                "--snapshot",
                snapshot,
                "-f",
                remote,
                *flags,
            )
            docker("cp", f"{container}:{remote}", str(bundle / f"{name}.dump"))
            docker("exec", container, "rm", "--", remote)
    print("Saving private files and checking their hashes…", flush=True)
    for item in objects:
        url = (
            settings.supabase_url
            + "/storage/v1/object/"
            + quote(item["bucket"], safe="")
            + "/"
            + quote(item["name"], safe="/")
        )
        content = request(
            "GET", url, headers=auth_headers(settings.supabase_service_role_key)
        ).content
        item["sha256"], item["bytes"] = hashlib.sha256(content).hexdigest(), len(content)
    docker("cp", f"{storage}:{layout['path']}", str(bundle / "storage-files"))
    # A concurrent object replacement/deletion must invalidate the bundle.
    with psycopg.connect(
        settings.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        current = {
            (b, n): v
            for b, n, v in db.execute("SELECT bucket_id,name,version FROM storage.objects")
        }
        if any(current.get((o["bucket"], o["name"])) != o["version"] for o in objects):
            raise RuntimeError("Files changed during backup; retry during a quiet period")
    manifest = {
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "database_image": info["Image"],
        "auth_image": auth_info["Image"],
        "storage_image": storage_info["Image"],
        "storage_layout": layout,
        "tables": hashes,
        "objects": objects,
        "probe": probe,
        "artifacts": artifacts(bundle),
    }
    raw = canonical(manifest)
    (bundle / "manifest.json").write_bytes(raw)
    (bundle / "manifest.signature").write_text(
        hmac.new(signing_key(create=True), raw, hashlib.sha256).hexdigest()
    )
    print(f"Signed private backup saved: {bundle}", flush=True)
    return bundle


def ports():
    for base in range(55001, 56001, 30):
        opened = []
        try:
            for port in range(base, base + 20):
                item = socket.socket()
                item.bind(("127.0.0.1", port))
                opened.append(item)
            return base
        except OSError:
            pass
        finally:
            for item in opened:
                item.close()
    raise RuntimeError("No isolated local port block is available")


def verify_probe(status, manifest, api_port, app_password, work):
    probe = manifest.get("probe")
    if not probe:
        return {"sign_in": False, "private_download": False, "cross_user_denied": False}
    auth_url = status["API_URL"]
    token = request(
        "POST",
        auth_url + "/auth/v1/token?grant_type=password",
        headers={"apikey": status["ANON_KEY"]},
        json={"email": probe["email"], "password": probe["password"]},
    ).json()
    if token["user"]["id"] != probe["user_id"]:
        raise RuntimeError("Restored identity mismatch")
    db_url = urlsplit(status["DB_URL"])
    env = {
        **os.environ,
        "APP_ENV": "development",
        "DATABASE_URL": f"postgresql+psycopg://chalkmate_app:{app_password}@127.0.0.1:{db_url.port}/postgres",
        "SUPABASE_URL": auth_url,
        "SUPABASE_ANON_KEY": status["ANON_KEY"],
        "SUPABASE_SERVICE_ROLE_KEY": status["SERVICE_ROLE_KEY"],
        "MAIL_PROVIDER": "disabled",
        "ENABLE_EXTERNAL_EMAIL": "false",
        "CELERY_BROKER_URL": "redis://127.0.0.1:1/0",
    }
    with (work / "api.log").open("wb") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "chalkmate.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            env=env,
            stdout=log,
            stderr=log,
            cwd=ROOT,
        )
        try:
            api = f"http://127.0.0.1:{api_port}"
            for _ in range(60):
                try:
                    if httpx.get(api + "/health", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.5)
            path = f"/v1/classrooms/{probe['classroom_id']}/files/{probe['file_id']}/download"
            headers = {"Authorization": f"Bearer {token['access_token']}"}
            download = request("GET", api + path, headers=headers).json()
            restored = request("GET", download["url"]).content
            if hashlib.sha256(restored).hexdigest() != probe["sha256"]:
                raise RuntimeError("Authorized download hash mismatch")
            if httpx.get(api + path, timeout=5).status_code != 401:
                raise RuntimeError("Anonymous access was not denied")
            other_email = f"e2e-isolated-{uuid4().hex}@example.com"
            other_password = secrets.token_urlsafe(28)
            request(
                "POST",
                auth_url + "/auth/v1/admin/users",
                headers=auth_headers(status["SERVICE_ROLE_KEY"]),
                json={"email": other_email, "password": other_password, "email_confirm": True},
            )
            other = request(
                "POST",
                auth_url + "/auth/v1/token?grant_type=password",
                headers={"apikey": status["ANON_KEY"]},
                json={"email": other_email, "password": other_password},
            ).json()
            if (
                httpx.get(
                    api + path,
                    headers={"Authorization": f"Bearer {other['access_token']}"},
                    timeout=10,
                ).status_code
                != 404
            ):
                raise RuntimeError("Unrelated account access was not denied")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return {"sign_in": True, "private_download": True, "cross_user_denied": True}


def drill(folder, cleanup=False):
    local_settings()
    bundle, manifest = load_bundle(folder)
    source_config = tomllib.loads((bundle / "supabase.toml").read_text(encoding="utf-8"))
    project = "chalkmate_recovery_" + uuid4().hex[:12]
    work = ROOT / ".tmp/recovery" / project
    private_folder(work)
    (work / "supabase").mkdir()
    base = ports()
    config = (bundle / "supabase.toml").read_text(encoding="utf-8")
    config = re.sub(r"^project_id\s*=.*$", f'project_id = "{project}"', config, flags=re.M)
    replacements = {
        54321: base,
        54322: base + 1,
        54320: base + 2,
        54329: base + 3,
        54323: base + 4,
        54324: base + 5,
        54327: base + 9,
    }
    config = re.sub(
        r"^(\s*(?:port|shadow_port|smtp_port|pop3_port)\s*=\s*)(\d+)",
        lambda m: m[1] + str(replacements.get(int(m[2]), base + 10)),
        config,
        flags=re.M,
    )
    if source_config["project_id"] == project:
        raise RuntimeError("Recovery project must differ from the original")
    (work / "supabase/config.toml").write_text(config, encoding="utf-8")
    started = datetime.now(UTC)
    report = {
        "verified": False,
        "verified_at": None,
        "scope": (
            "Current local Supabase application, Auth identities and private Storage; "
            "no external provider secrets or production SLA"
        ),
    }
    target = f"supabase_db_{project}"
    target_auth, target_storage = f"supabase_auth_{project}", f"supabase_storage_{project}"
    print("Starting a separate local recovery stack…", flush=True)
    try:
        run([CLI, "start", "--workdir", work, "--exclude", EXCLUDE], timeout=600)
        status = cli_status(work)
        if (
            urlsplit(status["DB_URL"]).port == urlsplit(get_settings().migration_database_url).port
            or urlsplit(status["API_URL"]).port == urlsplit(get_settings().supabase_url).port
        ):
            raise RuntimeError("Recovery ports overlap the original stack")
        actual = json.loads(docker("inspect", target))[0]
        if actual["Image"] != manifest["database_image"]:
            raise RuntimeError("Database image differs from the signed backup")
        auth_info = json.loads(docker("inspect", target_auth))[0]
        storage_info = json.loads(docker("inspect", target_storage))[0]
        if (
            auth_info["Image"] != manifest["auth_image"]
            or storage_info["Image"] != manifest["storage_image"]
            or storage_layout(storage_info) != manifest["storage_layout"]
        ):
            raise RuntimeError("Auth/Storage images or file layout differ from the signed backup")
        docker("stop", target_auth, target_storage)
        target_url = status["DB_URL"].replace(
            "postgresql://postgres:", "postgresql://supabase_admin:"
        )
        app_password = secrets.token_urlsafe(32)
        with psycopg.connect(target_url, autocommit=True) as db:
            for name in ("chalkmate_app", "chalkmate_worker"):
                db.execute(
                    sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                        sql.Identifier(name), sql.Literal(app_password)
                    )
                )
            db.execute("GRANT chalkmate_app TO chalkmate_worker")
            tables = [
                (s, t)
                for s, t in db.execute(
                    "SELECT schemaname,tablename FROM pg_tables "
                    "WHERE schemaname IN ('auth','storage')"
                )
                if (s, t) not in OMIT
            ]
            if tables:
                db.execute(
                    sql.SQL("TRUNCATE {} CASCADE").format(
                        sql.SQL(",").join(sql.Identifier(s, t) for s, t in tables)
                    )
                )
        print("Restoring identities, file metadata and classroom records…", flush=True)
        for name in ("auth", "storage", "application", "migration"):
            remote = f"/tmp/{name}.dump"
            docker("cp", str(bundle / f"{name}.dump"), f"{target}:{remote}")
            docker(
                "exec",
                target,
                "pg_restore",
                "-U",
                "supabase_admin",
                "-d",
                "postgres",
                "--exit-on-error",
                *(["--disable-triggers"] if name in ("auth", "storage") else []),
                remote,
            )
        with psycopg.connect(target_url) as db:
            if table_hashes(db) != manifest["tables"]:
                raise RuntimeError("Restored database checksums differ")
        docker(
            "cp",
            str(bundle / "storage-files") + "/.",
            f"{target_storage}:{manifest['storage_layout']['path']}",
        )
        docker("start", target_auth, target_storage)
        ready = False
        for _ in range(60):
            try:
                auth_ready = (
                    httpx.get(
                        status["API_URL"] + "/auth/v1/health",
                        headers={"apikey": status["ANON_KEY"]},
                        timeout=2,
                    ).status_code
                    == 200
                )
                files_ready = (
                    httpx.get(
                        status["API_URL"] + "/storage/v1/status",
                        headers=auth_headers(status["SERVICE_ROLE_KEY"]),
                        timeout=2,
                    ).status_code
                    == 200
                )
                if auth_ready and files_ready:
                    ready = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        if not ready:
            raise RuntimeError("Restored sign-in/private-file services did not become ready")
        for item in manifest["objects"]:
            url = (
                status["API_URL"]
                + "/storage/v1/object/"
                + quote(item["bucket"], safe="")
                + "/"
                + quote(item["name"], safe="/")
            )
            restored = request("GET", url, headers=auth_headers(status["SERVICE_ROLE_KEY"])).content
            if hashlib.sha256(restored).hexdigest() != item["sha256"]:
                raise RuntimeError("Restored private-file checksum differs")
        checks = verify_probe(status, manifest, base + 18, app_password, work)
        report.update(checks)
        report.update(
            {
                "verified": all(checks.values()),
                "verified_at": datetime.now(UTC).isoformat(),
                "duration_seconds": (datetime.now(UTC) - started).total_seconds(),
                "tables_checked": len(manifest["tables"]),
                "files_checked": len(manifest["objects"]),
                "database_hashes": True,
                "private_file_hashes": True,
            }
        )
        (work / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (ROOT / ".tmp/recovery-last-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(
            f"Recovery checks completed. Verified: {report['verified']}. "
            f"Report: {work / 'report.json'}",
            flush=True,
        )
        return report
    finally:
        if (
            cleanup
            and re.fullmatch(r"chalkmate_recovery_[a-f0-9]{12}", project)
            and work.resolve().is_relative_to(ROOT / ".tmp/recovery")
        ):
            run(
                [CLI, "stop", "--workdir", work, "--project-id", project, "--no-backup"],
                timeout=180,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "drill", "rehearse"])
    parser.add_argument("bundle", nargs="?", type=Path)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    if args.action == "backup":
        backup()
    elif args.action == "drill":
        if not args.bundle:
            parser.error("Choose a signed local backup bundle")
        drill(args.bundle, args.cleanup)
    else:
        probe = create_probe()
        try:
            bundle = backup(probe)
        finally:
            run([sys.executable, ROOT / "scripts/cleanup_e2e.py", probe["user_id"]])
        if not drill(bundle, args.cleanup)["verified"]:
            raise RuntimeError("Full local recovery verification did not pass")


if __name__ == "__main__":
    main()
