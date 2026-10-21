"""Integration fixtures use real local Supabase and an already-running API."""

import os
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from chalkmate.config import get_settings


@pytest.fixture(scope="session")
def environment():
    settings = get_settings()
    if settings.app_env != "development" or not settings.supabase_url.startswith(
        "http://127.0.0.1:"
    ):
        pytest.fail("Integration tests run only against the local development stack")
    return settings


@pytest.fixture(scope="session")
def accounts(environment):
    created = []
    settings = environment
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }

    def make():
        email = f"test-{uuid4().hex}@example.com"
        password = f"Test-{uuid4().hex}!"
        response = httpx.post(
            f"{settings.supabase_url}/auth/v1/admin/users",
            headers=headers,
            json={"email": email, "password": password, "email_confirm": True},
        )
        response.raise_for_status()
        user = response.json()
        response = httpx.post(
            f"{settings.supabase_url}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.supabase_anon_key},
            json={"email": email, "password": password},
        )
        response.raise_for_status()
        account = {
            "id": user["id"],
            "email": email,
            "password": password,
            "token": response.json()["access_token"],
        }
        created.append(account)
        return account

    yield make

    admin_url = settings.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(admin_url) as connection:
        ids = [item["id"] for item in created]
        workspaces = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM chalkmate.workspaces WHERE owner_id=ANY(%s::uuid[])", (ids,)
            )
        ]
        # Remove only synthetic records created by these tests, never preexisting workspaces.
        if workspaces:
            objects = connection.execute(
                "SELECT object_path FROM chalkmate.files WHERE workspace_id=ANY(%s::uuid[])",
                (workspaces,),
            ).fetchall()
            if objects:
                httpx.request(
                    "DELETE",
                    f"{settings.supabase_url}/storage/v1/object/classroom-files",
                    headers=headers,
                    json={"prefixes": [row[0] for row in objects]},
                )
            response_paths = connection.execute(
                (
                    "SELECT file_path FROM chalkmate.assignment_responses "
                    "WHERE workspace_id=ANY(%s::uuid[]) AND file_path IS NOT NULL"
                ),
                (workspaces,),
            ).fetchall()
            if response_paths:
                httpx.request(
                    "DELETE",
                    f"{settings.supabase_url}/storage/v1/object/classroom-files",
                    headers=headers,
                    json={"prefixes": [r[0] for r in response_paths]},
                )
            connection.execute(
                (
                    "DELETE FROM chalkmate.delivery_events WHERE provider_id IN "
                    "(SELECT provider_id FROM chalkmate.deliveries "
                    "WHERE workspace_id=ANY(%s::uuid[]))"
                ),
                (workspaces,),
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
                connection.execute(
                    sql.SQL("DELETE FROM chalkmate.{} WHERE workspace_id=ANY(%s::uuid[])").format(
                        sql.Identifier(table)
                    ),
                    (workspaces,),
                )
            connection.execute(
                "DELETE FROM chalkmate.workspaces WHERE id=ANY(%s::uuid[])", (workspaces,)
            )
        connection.execute("DELETE FROM chalkmate.users WHERE id=ANY(%s::uuid[])", (ids,))
    for account in created:
        httpx.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{account['id']}", headers=headers
        )


@pytest.fixture
def api_client():
    with httpx.Client(
        base_url=os.environ.get("TEST_API_URL", "http://127.0.0.1:8100"), timeout=30
    ) as client:
        yield client


def auth(account):
    return {"Authorization": f"Bearer {account['token']}"}


@pytest.fixture
def owner(accounts, api_client):
    account = accounts()
    response = api_client.post(
        "/v1/workspaces", headers=auth(account), json={"name": "Test workspace"}
    )
    assert response.status_code == 201, response.text
    workspace = response.json()
    response = api_client.post(
        f"/v1/workspaces/{workspace['id']}/classrooms",
        headers=auth(account),
        json={"name": "Class A", "subject": "Data Structures", "term": "2026"},
    )
    assert response.status_code == 201, response.text
    return account, workspace, response.json()
