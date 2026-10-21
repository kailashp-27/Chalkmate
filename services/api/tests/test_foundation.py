import io
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import httpx
import psycopg
import pytest
from conftest import auth
from fastapi import HTTPException
from openpyxl import Workbook

from chalkmate.rosters import parse_roster


def preview(client, account, classroom, content):
    return client.post(
        f"/v1/classrooms/{classroom['id']}/imports/preview",
        headers=auth(account),
        files={"file": ("roster.csv", content, "text/csv")},
    )


def confirm(client, account, classroom, batch):
    return client.post(
        f"/v1/classrooms/{classroom['id']}/imports/{batch['id']}/confirm", headers=auth(account)
    )


def invite(client, account, classroom, email, role, student_id=None):
    result = client.post(
        f"/v1/classrooms/{classroom['id']}/invitations",
        headers=auth(account),
        json={"email": email, "role": role, "student_id": student_id},
    )
    assert result.status_code == 201, result.text
    return parse_qs(urlsplit(result.json()["url"]).fragment)["token"][0]


def test_authentication_is_required(api_client):
    assert api_client.get("/v1/session").status_code == 401
    assert (
        api_client.get("/v1/session", headers={"Authorization": "Bearer forged"}).status_code == 401
    )


def test_two_owners_are_isolated_at_api_and_database(owner, accounts, api_client, environment):
    account, workspace, classroom = owner
    other = accounts()
    other_workspace = api_client.post(
        "/v1/workspaces", headers=auth(other), json={"name": "Other workspace"}
    )
    assert other_workspace.status_code == 201, other_workspace.text
    for suffix in ("", "/students", "/files", "/audit", "/invitations"):
        assert (
            api_client.get(
                f"/v1/classrooms/{classroom['id']}{suffix}", headers=auth(other)
            ).status_code
            == 404
        )
    assert (
        preview(
            api_client, other, classroom, b"registration_number,name,email\nA,A,a@example.com"
        ).status_code
        == 404
    )
    assert (
        api_client.patch(
            f"/v1/classrooms/{classroom['id']}", headers=auth(other), json={"name": "stolen"}
        ).status_code
        == 404
    )
    connection_url = environment.database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(connection_url) as db:
        db.execute("SELECT set_config('app.user_id', %s, true)", (other["id"],))
        assert (
            db.execute(
                "SELECT id FROM chalkmate.classrooms WHERE id=%s", (classroom["id"],)
            ).fetchall()
            == []
        )
        assert (
            db.execute(
                "SELECT id FROM chalkmate.workspaces WHERE id=%s", (workspace["id"],)
            ).fetchall()
            == []
        )
        role = db.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        assert role == (False, False)


def test_roster_preview_atomic_import_and_replay(owner, api_client):
    account, _, classroom = owner
    result = preview(
        api_client,
        account,
        classroom,
        b"registration_number,name,email\nA001,Ada,ada@example.com\nA002,Lin,invalid",
    )
    assert result.status_code == 200, result.text
    batch = result.json()
    assert len(batch["issues"]) == 1 and batch["issues"][0]["severity"] == "warning"
    assert (
        api_client.get(f"/v1/classrooms/{classroom['id']}/students", headers=auth(account)).json()
        == []
    )
    result = confirm(api_client, account, classroom, batch)
    assert result.status_code == 200, result.text
    assert result.json()["imported"] == 2
    assert confirm(api_client, account, classroom, batch).status_code == 409
    roster = api_client.get(
        f"/v1/classrooms/{classroom['id']}/students", headers=auth(account)
    ).json()
    assert roster[1]["email"] is None
    duplicate = preview(
        api_client, account, classroom, b"registration_number,name,email\nA001,Ada,ada@example.com"
    ).json()
    assert any(item["severity"] == "error" for item in duplicate["issues"])
    assert confirm(api_client, account, classroom, duplicate).status_code == 409


def test_duplicate_and_missing_roster_values_block_import(owner, api_client):
    account, _, classroom = owner
    result = preview(
        api_client,
        account,
        classroom,
        b"registration_number,name,email\nA,Ada,ada@example.com\na,,lin@example.com",
    )
    assert result.status_code == 200, result.text
    assert len([i for i in result.json()["issues"] if i["severity"] == "error"]) == 2
    assert confirm(api_client, account, classroom, result.json()).status_code == 409


def test_concurrent_confirmation_imports_once(owner, api_client):
    account, _, classroom = owner
    batch = preview(
        api_client, account, classroom, b"registration_number,name,email\nC001,Ada,ada@example.com"
    ).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(lambda _: confirm(api_client, account, classroom, batch).status_code, range(2))
        )
    assert sorted(statuses) == [200, 409]


def test_reviewers_read_only_assigned_class(owner, accounts, api_client):
    account, workspace, classroom = owner
    reviewer = accounts()
    token = invite(api_client, account, classroom, reviewer["email"], "reviewer")
    accepted = api_client.post(
        "/v1/invitations/accept", headers=auth(reviewer), json={"token": token}
    )
    assert accepted.status_code == 200, accepted.text
    result = api_client.get(f"/v1/classrooms/{classroom['id']}", headers=auth(reviewer))
    assert result.status_code == 200, result.text
    assert result.json()["can_edit"] is False
    assert (
        api_client.patch(
            f"/v1/classrooms/{classroom['id']}", headers=auth(reviewer), json={"name": "edited"}
        ).status_code
        == 404
    )
    result = api_client.post(
        f"/v1/workspaces/{workspace['id']}/classrooms",
        headers=auth(reviewer),
        json={"name": "No", "subject": "No", "term": "No"},
    )
    assert result.status_code == 403
    unassigned = api_client.post(
        f"/v1/workspaces/{workspace['id']}/classrooms",
        headers=auth(account),
        json={"name": "Class B", "subject": "Algorithms", "term": "2026"},
    ).json()
    assert (
        api_client.get(f"/v1/classrooms/{unassigned['id']}", headers=auth(reviewer)).status_code
        == 404
    )


def test_verified_student_invitation_never_links_peer(owner, accounts, api_client, environment):
    account, _, classroom = owner
    student, peer = accounts(), accounts()
    content = (
        f"registration_number,name,email\nS001,Student,{student['email']}\n"
        f"S002,Peer,{peer['email']}"
    ).encode()
    batch = preview(api_client, account, classroom, content).json()
    assert confirm(api_client, account, classroom, batch).status_code == 200
    roster = api_client.get(
        f"/v1/classrooms/{classroom['id']}/students", headers=auth(account)
    ).json()
    target = roster[0]
    token = invite(api_client, account, classroom, student["email"], "student", target["id"])
    assert (
        api_client.post(
            "/v1/invitations/accept", headers=auth(peer), json={"token": token}
        ).status_code
        == 404
    )
    result = api_client.post("/v1/invitations/accept", headers=auth(student), json={"token": token})
    assert result.status_code == 200, result.text
    assert (
        api_client.post(
            "/v1/invitations/accept", headers=auth(student), json={"token": token}
        ).status_code
        == 409
    )
    assert (
        api_client.get(f"/v1/classrooms/{classroom['id']}", headers=auth(student)).status_code
        == 200
    )
    for suffix in ("students", "files", "audit"):
        assert (
            api_client.get(
                f"/v1/classrooms/{classroom['id']}/{suffix}", headers=auth(student)
            ).status_code
            == 404
        )
    with psycopg.connect(
        environment.database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute("SELECT set_config('app.user_id', %s, true)", (student["id"],))
        rows = db.execute("SELECT id FROM chalkmate.students").fetchall()
        assert [str(row[0]) for row in rows] == [target["id"]]


def test_private_file_upload_and_download(owner, accounts, api_client, environment):
    account, _, classroom = owner
    from test_assessments import pdf

    content = pdf()
    result = api_client.post(
        f"/v1/classrooms/{classroom['id']}/files",
        headers=auth(account),
        files={"file": ("resource.pdf", content, "application/pdf")},
    )
    assert result.status_code == 201, result.text
    record = result.json()
    result = api_client.get(
        f"/v1/classrooms/{classroom['id']}/files/{record['id']}/download", headers=auth(account)
    )
    assert result.status_code == 200, result.text
    assert result.json()["expires_in"] == 60
    assert httpx.get(result.json()["url"]).content == content
    other = accounts()
    assert (
        api_client.get(
            f"/v1/classrooms/{classroom['id']}/files/{record['id']}/download", headers=auth(other)
        ).status_code
        == 404
    )
    public_url = (
        result.json()["url"].split("/object/sign/")[0]
        + "/object/public/"
        + result.json()["url"].split("/object/sign/")[1].split("?")[0]
    )
    assert httpx.get(public_url).status_code != 200


def test_xlsx_parser_and_formula_rejection():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["registration_number", "name", "email"])
    sheet.append(["X001", "Student", "student@example.com"])
    output = io.BytesIO()
    workbook.save(output)
    rows, issues = parse_roster("roster.xlsx", output.getvalue())
    assert len(rows) == 1 and not issues
    sheet.append(["X002", "=1+1", "student@example.com"])
    output = io.BytesIO()
    workbook.save(output)
    assert any(i["severity"] == "error" for i in parse_roster("roster.xlsx", output.getvalue())[1])
    with pytest.raises(HTTPException):
        parse_roster("not-a-roster.pdf", b"%PDF-")


def test_unverified_signup_cannot_sign_in(api_client, environment):
    from uuid import uuid4

    email = f"test-unverified-{uuid4().hex}@example.com"
    password = f"Test-{uuid4().hex}!"
    headers = {"apikey": environment.supabase_anon_key}
    result = httpx.post(
        f"{environment.supabase_url}/auth/v1/signup",
        headers=headers,
        json={"email": email, "password": password},
    )
    assert result.status_code == 200, result.text
    user_id = result.json()["user"]["id"] if "user" in result.json() else result.json()["id"]
    try:
        result = httpx.post(
            f"{environment.supabase_url}/auth/v1/token?grant_type=password",
            headers=headers,
            json={"email": email, "password": password},
        )
        assert result.status_code == 400
        assert result.json()["error_code"] == "email_not_confirmed"
    finally:
        httpx.delete(
            f"{environment.supabase_url}/auth/v1/admin/users/{user_id}",
            headers={
                "apikey": environment.supabase_service_role_key,
                "Authorization": f"Bearer {environment.supabase_service_role_key}",
            },
        )


def test_student_identity_is_reused_across_classes(owner, api_client):
    account, workspace, classroom = owner
    content = b"registration_number,name,email\nR001,Ada,ada@example.com"
    batch = preview(api_client, account, classroom, content).json()
    assert confirm(api_client, account, classroom, batch).status_code == 200
    first = api_client.get(
        f"/v1/classrooms/{classroom['id']}/students", headers=auth(account)
    ).json()
    second_class = api_client.post(
        f"/v1/workspaces/{workspace['id']}/classrooms",
        headers=auth(account),
        json={"name": "Class B", "subject": "Algorithms", "term": "2026"},
    ).json()
    batch = preview(api_client, account, second_class, content).json()
    assert confirm(api_client, account, second_class, batch).status_code == 200
    second = api_client.get(
        f"/v1/classrooms/{second_class['id']}/students", headers=auth(account)
    ).json()
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["enrollment_id"] != second[0]["enrollment_id"]


def test_expired_preview_and_archived_class_block_import(owner, api_client, environment):
    account, _, classroom = owner
    batch = preview(
        api_client, account, classroom, b"registration_number,name,email\nE001,Ada,ada@example.com"
    ).json()
    with psycopg.connect(
        environment.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute(
            "UPDATE chalkmate.import_batches SET expires_at=now()-interval '1 minute' WHERE id=%s",
            (batch["id"],),
        )
    assert confirm(api_client, account, classroom, batch).status_code == 409
    result = api_client.patch(
        f"/v1/classrooms/{classroom['id']}", headers=auth(account), json={"archived": True}
    )
    assert result.status_code == 200, result.text
    assert (
        preview(
            api_client,
            account,
            classroom,
            b"registration_number,name,email\nE001,Ada,ada@example.com",
        ).status_code
        == 409
    )
    result = api_client.patch(
        f"/v1/classrooms/{classroom['id']}", headers=auth(account), json={"archived": False}
    )
    assert result.status_code == 200
