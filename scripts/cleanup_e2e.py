"""Remove only an explicitly supplied synthetic e2e account and its owned records."""

import sys
from uuid import UUID

import httpx
import psycopg
from psycopg import sql

from chalkmate.config import get_settings

settings = get_settings()
user_id = str(UUID(sys.argv[1]))
if settings.app_env != "development" or not settings.supabase_url.startswith("http://127.0.0.1:"):
    raise RuntimeError("Local tests only")
headers = {
    "apikey": settings.supabase_service_role_key,
    "Authorization": f"Bearer {settings.supabase_service_role_key}",
}
user = httpx.get(f"{settings.supabase_url}/auth/v1/admin/users/{user_id}", headers=headers)
user.raise_for_status()
if not user.json()["email"].startswith("e2e-"):
    raise RuntimeError("Refusing to remove a non-test account")
with psycopg.connect(
    settings.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
) as db:
    ids = [
        row[0]
        for row in db.execute("SELECT id FROM chalkmate.workspaces WHERE owner_id=%s", (user_id,))
    ]
    if ids:
        paths = [
            row[0]
            for row in db.execute(
                "SELECT object_path FROM chalkmate.files WHERE workspace_id=ANY(%s::uuid[])", (ids,)
            )
        ]
        if paths:
            httpx.request(
                "DELETE",
                f"{settings.supabase_url}/storage/v1/object/classroom-files",
                headers=headers,
                json={"prefixes": paths},
            )
        response_paths = db.execute(
            (
                "SELECT file_path FROM chalkmate.assignment_responses "
                "WHERE workspace_id=ANY(%s::uuid[]) AND file_path IS NOT NULL"
            ),
            (ids,),
        ).fetchall()
        if response_paths:
            httpx.request(
                "DELETE",
                f"{settings.supabase_url}/storage/v1/object/classroom-files",
                headers=headers,
                json={"prefixes": [r[0] for r in response_paths]},
            )
        db.execute(
            (
                "DELETE FROM chalkmate.delivery_events WHERE provider_id IN "
                "(SELECT provider_id FROM chalkmate.deliveries "
                "WHERE workspace_id=ANY(%s::uuid[]))"
            ),
            (ids,),
        )
        for table in [
            "review_requests",
            "question_links",
            "marks_exports",
            "planning_approvals",
            "planning_jobs",
            "planning_documents",
            "material_approvals",
            "teaching_materials",
            "finding_reviews",
            "intelligence_runs",
            "delivery_attempts",
            "deliveries",
            "campaigns",
            "campaign_previews",
            "assignment_responses",
            "assignment_audiences",
            "assignment_versions",
            "assignments",
            "question_reviews",
            "calibrations",
            "reevaluations",
            "processing_jobs",
            "releases",
            "decisions",
            "proposals",
            "extractions",
            "submissions",
            "rubrics",
            "assessments",
            "audit_events",
            "files",
            "invitations",
            "import_batches",
            "enrollments",
            "classroom_teachers",
            "classrooms",
            "students",
            "memberships",
        ]:
            db.execute(
                sql.SQL("DELETE FROM chalkmate.{} WHERE workspace_id=ANY(%s::uuid[])").format(
                    sql.Identifier(table)
                ),
                (ids,),
            )
        db.execute("DELETE FROM chalkmate.workspaces WHERE id=ANY(%s::uuid[])", (ids,))
    db.execute("DELETE FROM chalkmate.users WHERE id=%s", (user_id,))
httpx.delete(
    f"{settings.supabase_url}/auth/v1/admin/users/{user_id}", headers=headers
).raise_for_status()
