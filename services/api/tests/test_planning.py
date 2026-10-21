"""Planning review gates, source versions, role isolation and durable recovery."""

from uuid import UUID

import psycopg
import pytest
from conftest import auth
from sqlalchemy import text

from chalkmate import planning_worker as worker
from chalkmate.planning_rules import checks, command_preview
from chalkmate.planning_schemas import PlanningContent
from chalkmate.processing import engine


def ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json()


@pytest.fixture
def planning_case(owner, api_client):
    account, workspace, classroom = owner
    url = f"/v1/classrooms/{classroom['id']}/planning"
    source = ok(
        api_client.post(
            url,
            headers=auth(account),
            json={
                "kind": "syllabus",
                "title": "Stack syllabus",
                "content": {
                    "topics": [
                        {
                            "name": "Stacks",
                            "text": (
                                "A stack uses LIFO ordering. "
                                "Push adds an item; pop removes the latest item."
                            ),
                        }
                    ]
                },
            },
        ),
        201,
    )
    ok(api_client.post(f"/v1/planning/{source['id']}/approve", headers=auth(account)))
    return account, classroom, source, url


def paper(source):
    return {
        "kind": "paper",
        "title": "Stack paper",
        "source_ids": [source["id"]],
        "content": {
            "total_marks": "5",
            "questions": [
                {
                    "topic": "Stacks",
                    "text": "Explain how a stack removes an item.",
                    "marks": "5",
                    "solution": "PRIVATE-KEY LIFO",
                    "rubric": "Award five for correct ordering and example.",
                    "references": [{"source_id": "S1", "quote": "A stack uses LIFO ordering."}],
                }
            ],
        },
    }


def test_planning_versions_approval_and_private_exports(planning_case, api_client, accounts):
    account, classroom, source, url = planning_case
    created = ok(api_client.post(url, headers=auth(account), json=paper(source)), 201)
    assert not created["issues"] and not created["approved"]
    ok(api_client.post(f"/v1/planning/{created['id']}/approve", headers=auth(account)))
    export = api_client.get(f"/v1/planning/{created['id']}/export", headers=auth(account))
    assert export.status_code == 200 and "PRIVATE-KEY" not in export.text
    assert (
        "PRIVATE-KEY"
        in api_client.get(
            f"/v1/planning/{created['id']}/export?teacher_key=true", headers=auth(account)
        ).text
    )
    other = accounts()
    assert api_client.get(url, headers=auth(other)).status_code == 404
    assert (
        api_client.get(
            f"/v1/planning/{created['id']}/export?teacher_key=true", headers=auth(other)
        ).status_code
        == 404
    )
    revised = {**paper(source), "base_version": 1, "title": "Paper v2"}
    version = ok(
        api_client.post(
            f"/v1/planning/{created['id']}/versions", headers=auth(account), json=revised
        ),
        201,
    )
    assert version["version"] == 2 and not version["approved"]
    assert (
        api_client.post(f"/v1/planning/{created['id']}/approve", headers=auth(account)).status_code
        == 409
    )
    assert (
        api_client.post(
            f"/v1/planning/{created['id']}/versions", headers=auth(account), json=revised
        ).status_code
        == 409
    )


def test_checks_and_stale_source_block_approval(planning_case, api_client):
    account, classroom, source, url = planning_case
    body = paper(source)
    body["content"]["questions"][0]["references"][0]["quote"] = "Invented quotation"
    body["content"]["total_marks"] = "10"
    created = ok(api_client.post(url, headers=auth(account), json=body), 201)
    assert len(created["issues"]) >= 2
    assert (
        api_client.post(f"/v1/planning/{created['id']}/approve", headers=auth(account)).status_code
        == 409
    )
    ok(
        api_client.post(
            f"/v1/planning/{source['id']}/versions",
            headers=auth(account),
            json={
                "kind": "syllabus",
                "title": source["title"],
                "content": source["content"],
                "base_version": 1,
            },
        ),
        201,
    )
    assert api_client.post(url, headers=auth(account), json=paper(source)).status_code == 409
    rows = ok(api_client.get(url, headers=auth(account)))
    assert any(
        "newer version" in issue
        for row in rows
        if row["id"] == created["id"]
        for issue in row["issues"]
    )


def test_blueprint_and_variant_checks():
    syllabus = {
        "source_id": "S1",
        "kind": "syllabus",
        "content": {"topics": [{"name": "Stacks", "text": "A stack uses LIFO ordering."}]},
    }
    body = paper({"id": "unused"})["content"]
    blueprint = {
        "source_id": "S2",
        "kind": "blueprint",
        "content": {
            "total_marks": "10",
            "allocations": [{"topic": "Stacks", "count": 2, "marks": "5"}],
        },
    }
    issues = checks("paper", body, [syllabus, blueprint])
    assert any("blueprint" in v for v in issues)
    variant = {"source_id": "S2", "kind": "paper", "content": body}
    assert any("Variant repeats" in v for v in checks("paper", body, [syllabus, variant]))
    body["questions"] *= 2
    assert any("Repeated" in v for v in checks("paper", body, [syllabus]))


def test_commands_never_execute_changes(planning_case, api_client):
    account, classroom, _, _ = planning_case
    path = f"/v1/classrooms/{classroom['id']}/command-preview"
    assert (
        ok(api_client.post(path, headers=auth(account), json={"text": "open planning"}))[
            "destination"
        ]
        == "Planning"
    )
    assert command_preview("send remedial assignment below 25")["destination"] is None
    assert command_preview("open planning and roster")["destination"] is None
    assert command_preview("delete all students")["destination"] is None


def test_reports_use_recorded_data(planning_case, api_client):
    account, classroom, _, url = planning_case
    template = ok(
        api_client.post(
            url,
            headers=auth(account),
            json={
                "kind": "report_template",
                "title": "Course summary",
                "content": {
                    "columns": [
                        "classroom",
                        "students",
                        "assessments",
                        "approved_decisions",
                        "activity_events",
                    ]
                },
            },
        ),
        201,
    )
    assert (
        api_client.post(f"/v1/planning/{template['id']}/report", headers=auth(account)).status_code
        == 409
    )
    ok(api_client.post(f"/v1/planning/{template['id']}/approve", headers=auth(account)))
    report = ok(
        api_client.post(f"/v1/planning/{template['id']}/report", headers=auth(account)), 201
    )
    assert "Students: 0" in report["content"]["text"]
    assert "Approved Decisions: 0" in report["content"]["text"]
    assert not report["approved"]


def test_worker_drafts_and_failure_recovery(planning_case, api_client, monkeypatch):
    account, classroom, source, url = planning_case
    path = f"/v1/classrooms/{classroom['id']}/planning-jobs"
    request = {
        "kind": "paper",
        "title": "Local paper",
        "source_ids": [source["id"]],
        "model": "local-test",
        "total_marks": "5",
    }
    job = ok(api_client.post(path, headers=auth(account), json=request), 201)
    assert api_client.post(path, headers=auth(account), json=request).status_code == 409
    monkeypatch.setattr(
        worker,
        "generate",
        lambda model, request: (
            PlanningContent.model_validate(paper(source)["content"]).model_dump(mode="json"),
            "test-digest",
            {"eval_count": 25},
        ),
    )
    worker.process_planning(job["id"])
    completed = ok(api_client.get(path, headers=auth(account)))[0]
    assert completed["status"] == "succeeded" and completed["model_digest"] == "test-digest"
    rows = ok(api_client.get(url, headers=auth(account)))
    assert not next(d for d in rows if d["id"] == completed["result_id"])["approved"]

    def fail(*args):
        raise ValueError("Model not available")

    monkeypatch.setattr(worker, "generate", fail)
    job = ok(api_client.post(path, headers=auth(account), json=request), 201)
    worker.process_planning(job["id"])
    for attempt in (2, 3):
        ok(api_client.post(f"/v1/planning-jobs/{job['id']}/retry", headers=auth(account)))
        worker.process_planning(job["id"])
    assert (
        api_client.post(f"/v1/planning-jobs/{job['id']}/retry", headers=auth(account)).status_code
        == 409
    )
    ready = ok(api_client.get(f"/v1/classrooms/{classroom['id']}/readiness", headers=auth(account)))
    assert ready["attempts_today"] == 4 and ready["generated_tokens"] == 25


def test_queue_cancellation_and_expired_lease(planning_case, api_client, environment):
    account, classroom, source, _ = planning_case
    path = f"/v1/classrooms/{classroom['id']}/planning-jobs"
    request = {
        "kind": "meeting",
        "title": "Meeting",
        "model": "local-test",
        "original": "Discuss chapter two. No owners or deadlines supplied.",
    }
    job = ok(api_client.post(path, headers=auth(account), json=request), 201)
    with engine().begin() as db:
        claim = db.execute(
            text("SELECT * FROM chalkmate.claim_planning(:id)"), {"id": UUID(job["id"])}
        ).first()
        assert claim.attempt == 1
    with psycopg.connect(
        environment.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute(
            "UPDATE chalkmate.planning_jobs SET lease_until=now()-interval '1 second' WHERE id=%s",
            (job["id"],),
        )
    with engine().begin() as db:
        list(db.execute(text("SELECT chalkmate.pending_planning()")))
    assert ok(api_client.get(path, headers=auth(account)))[0]["status"] == "failed"
    ok(api_client.post(f"/v1/planning-jobs/{job['id']}/cancel", headers=auth(account)))
    assert (
        api_client.post(f"/v1/planning-jobs/{job['id']}/retry", headers=auth(account)).status_code
        == 409
    )


def test_reviewer_and_student_planning_isolation(planning_case, api_client, accounts, environment):
    account, classroom, source, url = planning_case
    reviewer, student = accounts(), accounts()
    with psycopg.connect(
        environment.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        from uuid import uuid4

        # Register verified users through the API before attaching scoped fixture roles.
        ok(api_client.get("/v1/session", headers=auth(reviewer)))
        ok(api_client.get("/v1/session", headers=auth(student)))
        for person, role in [(reviewer, "reviewer"), (student, "student")]:
            db.execute(
                "INSERT INTO "
                "chalkmate.memberships(id,workspace_id,user_id,role) VALUES(%s,%s,%s,%s)",
                (uuid4(), classroom["workspace_id"], person["id"], role),
            )
        db.execute(
            "INSERT INTO "
            "chalkmate.classroom_teachers(id,workspace_id,classroom_id,user_id,role) "
            "VALUES(%s,%s,%s,%s,'reviewer')",
            (uuid4(), classroom["workspace_id"], classroom["id"], reviewer["id"]),
        )
    assert api_client.get(url, headers=auth(reviewer)).status_code == 200
    assert api_client.post(url, headers=auth(reviewer), json=paper(source)).status_code == 404
    assert (
        api_client.get(f"/v1/planning/{source['id']}/export", headers=auth(reviewer)).status_code
        == 200
    )
    assert api_client.get(url, headers=auth(student)).status_code == 404
    assert (
        api_client.get(
            f"/v1/planning/{source['id']}/export?teacher_key=true", headers=auth(student)
        ).status_code
        == 404
    )
    with psycopg.connect(
        environment.database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute("SELECT set_config('app.user_id',%s,true)", (student["id"],))
        assert db.execute("SELECT count(*) FROM chalkmate.planning_documents").fetchone()[0] == 0


def test_live_local_planning_worker(owner, api_client):
    import os
    import time

    if os.getenv("RUN_LIVE_PLANNING") != "1":
        pytest.skip("Optional real local model and Docker worker verification")
    account, _, classroom = owner
    path = f"/v1/classrooms/{classroom['id']}/planning-jobs"
    original = "We decided to revise stack operations next Monday. No owner was assigned."
    job = ok(
        api_client.post(
            path,
            headers=auth(account),
            json={
                "kind": "meeting",
                "title": "Synthetic local meeting draft",
                "original": original,
                "model": os.getenv("PLANNING_TEST_MODEL", "llama3.2:1b"),
            },
        ),
        201,
    )
    deadline = time.monotonic() + 550
    while time.monotonic() < deadline:
        current = next(
            r for r in ok(api_client.get(path, headers=auth(account))) if r["id"] == job["id"]
        )
        if current["status"] in ("succeeded", "failed", "canceled"):
            break
        time.sleep(3)
    assert current["status"] == "succeeded", current["error"]
    assert current["model_digest"] and current["usage"].get("eval_count")
    documents = ok(
        api_client.get(f"/v1/classrooms/{classroom['id']}/planning", headers=auth(account))
    )
    document = next(r for r in documents if r["id"] == current["result_id"])
    assert document["content"]["original"] == original and not document["approved"]
    assert not document["issues"]
