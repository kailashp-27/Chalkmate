"""Restore the application schema into an isolated local database and compare table hashes.

Does not alter the source database or test Supabase Auth/Storage recovery. Leaves the
isolated copy for inspection by default. --cleanup drops only the generated drill DB.
"""

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from chalkmate.config import get_settings


def docker(container, *args):
    result = subprocess.run(
        ["docker", "exec", container, *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError(f"Local database drill command failed: {args[0]}")
    return result.stdout.strip()


def hashes(container, database):
    tables = docker(
        container,
        "psql",
        "-U",
        "postgres",
        "-d",
        database,
        "-Atc",
        "SELECT tablename FROM pg_tables WHERE schemaname='chalkmate' ORDER BY tablename",
    ).splitlines()
    output = {}
    for table in tables:
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError("Unexpected table identifier")
        # Hash every row without exposing records; stable order independent of physical storage.
        query = (
            "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) "
            f"FROM (SELECT md5(row_to_json(t)::text) h FROM chalkmate.{table} t) rows"
        )
        output[table] = docker(container, "psql", "-U", "postgres", "-d", database, "-Atc", query)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", default="supabase_db_Chalkmate")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if (
        settings.app_env != "development"
        or not settings.supabase_url.startswith("http://127.0.0.1:")
        or not re.fullmatch(r"supabase_db_[A-Za-z0-9_-]+", args.container)
    ):
        raise RuntimeError("Restore drills are restricted to local development Supabase")
    target = f"chalkmate_drill_{uuid4().hex}"
    archive = f"/tmp/{target}.dump"
    started = datetime.now(UTC)
    # Use an exported MVCC snapshot for both the archive and source checksums.
    import psycopg

    with psycopg.connect(
        settings.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as source:
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        snapshot = source.execute("SELECT pg_export_snapshot()").fetchone()[0]
        docker(
            args.container,
            "pg_dump",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-n",
            "chalkmate",
            "-Fc",
            "--snapshot",
            snapshot,
            "-f",
            archive,
        )
        docker(args.container, "createdb", "-U", "postgres", target)
        docker(
            args.container, "pg_restore", "-U", "postgres", "-d", target, "--exit-on-error", archive
        )
        source_hashes = {}
        for (table,) in source.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='chalkmate' ORDER BY tablename"
        ):
            if not re.fullmatch(r"[a-z_]+", table):
                raise ValueError("Unexpected table identifier")
            value = source.execute(
                (
                    "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) "
                    f"FROM (SELECT md5(row_to_json(t)::text) h FROM chalkmate.{table} t) rows"
                )
            ).fetchone()
            source_hashes[table] = f"{value[0]}|{value[1]}"
    restored = hashes(args.container, target)
    matched = source_hashes == restored
    # Verify restored RLS and restricted app role still deny anonymous classroom reads.
    # Supabase's postgres role cannot SET ROLE to every login. Exercise the actual
    # restricted login with its existing local credential instead of broadening grants.
    app_url = make_url(settings.database_url).set(database=target)
    if app_url.host not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("The application database must also be local")
    with psycopg.connect(
        app_url.render_as_string(hide_password=False).replace(
            "postgresql+psycopg://", "postgresql://"
        )
    ) as restricted:
        isolated = (
            restricted.execute("SELECT count(*) FROM chalkmate.planning_documents").fetchone()[0]
            == 0
        )
    if args.cleanup and re.fullmatch(r"chalkmate_drill_[a-f0-9]{32}", target):
        docker(args.container, "dropdb", "-U", "postgres", target)
        docker(args.container, "rm", "--", archive)
    report = {
        "started_at": started.isoformat(),
        "duration_seconds": (datetime.now(UTC) - started).total_seconds(),
        "tables": len(restored),
        "checksums_match": matched,
        "restored_rls_denies_anonymous_reads": isolated,
        "target": target,
        "cleaned_up": args.cleanup,
        "scope": (
            "Application PostgreSQL schema only. Auth users and Storage objects "
            "require separate backup/restore."
        ),
    }
    path = Path(".tmp/restore-drill.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not matched or not isolated:
        raise RuntimeError("Restore verification failed; inspect .tmp/restore-drill.json")
    print(
        f"Restored {len(restored)} application tables; checksums and anonymous RLS verified. "
        f"Report: {path}"
    )


if __name__ == "__main__":
    main()
