"""Phase 5 evidence, privacy, immutable review and durable-generation checks."""

import os
import time
from uuid import uuid4

import psycopg
import pytest
from conftest import auth
from sqlalchemy import text
from test_assessments import decision_body, review

from chalkmate import intelligence_worker as worker
from chalkmate.intelligence_rules import (
    model_evidence,
    student_material,
    validate_analysis,
    validate_material,
)
from chalkmate.processing import engine

pytest_plugins = ["test_assessments"]


def ok(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def admin(environment):
    return psycopg.connect(
        environment.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    )


def finding(quote="A stack uses LIFO", source="S1", page=1):
    return {
        "findings": [
            {
                "title": "Explain LIFO with an example",
                "kind": "needs_practice",
                "explanation": (
                    "The reviewed answer identifies stack ordering; "
                    "an example would help practice applying it."
                ),
                "citations": [{"source_id": source, "quote": quote, "page": page}],
                "suggested_action": "Ask students to trace push and pop operations.",
            }
        ],
        "limitations": "One reviewed answer is a limited sample, not a class-wide diagnosis.",
    }


def content(kind="remedial"):
    return {
        "title": "Stack ordering practice",
        "introduction": "Practice the order of stack operations.",
        "objectives": ["Trace push and pop operations."],
        "revision_notes": ["A stack removes the most recently added item first."]
        if kind == "revision"
        else [],
        "items": [
            {
                "question": "Push A then B. Which item is removed first?",
                "hint": "Think about the item added last.",
                "answer": "PRIVATE-KEY-ANSWER: B is removed before A.",
                "rationale": "PRIVATE-KEY-RATIONALE: Connects a concrete operation to LIFO.",
            }
        ],
    }


@pytest.fixture
def intelligence_case(assessment_case, api_client):
    account, classroom, assessment, rubric, paper, pupil = assessment_case
    extraction = ok(review(api_client, account, paper, rubric), 201)
    ok(
        api_client.post(
            f"/v1/submissions/{paper['id']}/decisions",
            headers=auth(account),
            json=decision_body(extraction, rubric),
        ),
        201,
    )
    request = {"question_id": rubric["questions"][0]["id"], "topic": "Stack ordering"}
    return account, classroom, assessment, rubric, paper, pupil, request


def analyzed(client, case, manual=True):
    return ok(
        client.post(
            f"/v1/assessments/{case[2]['id']}/intelligence-runs",
            headers=auth(case[0]),
            json={**case[6], **({"manual_result": finding()} if manual else {})},
        ),
        201,
    )


def accepted(client, case):
    run = analyzed(client, case)
    review = ok(
        client.post(
            f"/v1/intelligence-runs/{run['id']}/findings/0/reviews",
            headers=auth(case[0]),
            json={
                "base_version": 0,
                "disposition": "accepted",
                "reason": "Checked the exact reviewed answer and rubric.",
            },
        ),
        201,
    )
    return run, review


def material(client, case, run, review, kind="remedial", manual=True):
    request = {
        "source_run_id": run["id"],
        "review_ids": [review["id"]],
        "material_type": kind,
        "model": case[6].get("model"),
    }
    if manual:
        request["manual_content"] = content(kind)
    result = ok(
        client.post(
            f"/v1/assessments/{case[2]['id']}/teaching-material",
            headers=auth(case[0]),
            json=request,
        ),
        201,
    )
    return result


def getrun(client, case, rid):
    return ok(client.get(f"/v1/intelligence-runs/{rid}", headers=auth(case[0])))


def test_summary_evidence_and_student_database_isolation(
    intelligence_case, api_client, environment, accounts
):
    c = intelligence_case
    h = auth(c[0])
    aid = c[2]["id"]
    summary = ok(api_client.get(f"/v1/assessments/{aid}/topic-summary", headers=h))
    assert summary["missing"] == 1 and summary["unapproved"] == 0
    assert summary["topics"][0]["average"] == "4.50"
    assert summary["topics"][0]["partial_credit"] == 1 and summary["topics"][0]["analyzable"] == 1
    sources = ok(api_client.post(f"/v1/assessments/{aid}/evidence-preview", headers=h, json=c[6]))
    assert sources[0]["student_name"] == "Student" and sources[0]["mark"] == "4.50"
    for who in [c[5], accounts()]:
        assert (
            api_client.get(f"/v1/assessments/{aid}/topic-summary", headers=auth(who)).status_code
            == 404
        )
        assert (
            api_client.post(
                f"/v1/assessments/{aid}/evidence-preview", headers=auth(who), json=c[6]
            ).status_code
            == 404
        )
    run, review = accepted(api_client, c)
    generated = material(api_client, c, run, review, "revision")
    versions = ok(api_client.get(f"/v1/intelligence-runs/{generated['id']}/materials", headers=h))
    assert (
        api_client.get(f"/v1/intelligence-runs/{run['id']}", headers=auth(c[5])).status_code == 404
    )
    assert (
        api_client.get(
            f"/v1/teaching-materials/{versions[0]['id']}/export?answer_key=true", headers=auth(c[5])
        ).status_code
        == 404
    )
    with psycopg.connect(
        environment.database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute("SELECT set_config('app.user_id',%s,true)", (c[5]["id"],))
        for table in [
            "intelligence_runs",
            "finding_reviews",
            "teaching_materials",
            "material_approvals",
        ]:
            assert db.execute(f"SELECT id FROM chalkmate.{table}").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT chalkmate.pending_intelligence()")


def test_material_versions_answer_separation_and_explicit_idempotent_approval(
    intelligence_case, api_client
):
    c = intelligence_case
    h = auth(c[0])
    run, review = accepted(api_client, c)
    generated = material(api_client, c, run, review, "revision")
    first = ok(api_client.get(f"/v1/intelligence-runs/{generated['id']}/materials", headers=h))[0]
    student = api_client.get(f"/v1/teaching-materials/{first['id']}/export", headers=h)
    teacher = api_client.get(
        f"/v1/teaching-materials/{first['id']}/export?answer_key=true", headers=h
    )
    assert student.status_code == teacher.status_code == 200
    assert "PRIVATE-KEY" not in student.text and "PRIVATE-KEY-ANSWER" in teacher.text
    assert "DRAFT" in student.text
    revised = content("revision")
    revised["title"] = "Revised stack practice"
    body = {"base_version": 1, "content": revised, "reason": "Clarify the practice title."}
    second = ok(
        api_client.post(f"/v1/intelligence-runs/{generated['id']}/materials", headers=h, json=body),
        201,
    )
    assert second["version"] == 2
    assert (
        api_client.post(
            f"/v1/intelligence-runs/{generated['id']}/materials", headers=h, json=body
        ).status_code
        == 409
    )
    approve = {
        "base_version": 2,
        "confirmed": True,
        "reason": "Teacher checked the student practice and private answer key.",
    }
    assert (
        api_client.post(
            f"/v1/teaching-materials/{first['id']}/approve",
            headers=h,
            json={**approve, "base_version": 1},
        ).status_code
        == 409
    )
    approved = ok(
        api_client.post(f"/v1/teaching-materials/{second['id']}/approve", headers=h, json=approve),
        201,
    )
    again = ok(
        api_client.post(f"/v1/teaching-materials/{second['id']}/approve", headers=h, json=approve),
        201,
    )
    assert approved["id"] == again["id"]
    draft = ok(
        api_client.get(f"/v1/assignment-versions/{approved['assignment_version_id']}", headers=h)
    )
    assert draft["version"]["published_at"] is None and draft["audience_count"] == 0
    assert "PRIVATE-KEY" not in draft["version"]["instructions"]
    assert (
        api_client.get(
            f"/v1/assignment-versions/{approved['assignment_version_id']}", headers=auth(c[5])
        ).status_code
        == 404
    )
    ok(
        api_client.post(
            f"/v1/assignment-versions/{approved['assignment_version_id']}/publish",
            headers=h,
            json={},
        )
    )
    pupil = ok(
        api_client.get(
            f"/v1/assignment-versions/{approved['assignment_version_id']}", headers=auth(c[5])
        )
    )
    assert pupil["can_submit"] and "PRIVATE-KEY" not in pupil["version"]["instructions"]
    assert (
        len(ok(api_client.get(f"/v1/intelligence-runs/{generated['id']}/materials", headers=h)))
        == 2
    )


def test_review_history_dismissal_and_source_drift(intelligence_case, api_client):
    c = intelligence_case
    h = auth(c[0])
    run, reviewed = accepted(api_client, c)
    generated = material(api_client, c, run, reviewed)
    item = ok(api_client.get(f"/v1/intelligence-runs/{generated['id']}/materials", headers=h))[0]
    dismissed = ok(
        api_client.post(
            f"/v1/intelligence-runs/{run['id']}/findings/0/reviews",
            headers=h,
            json={
                "base_version": 1,
                "disposition": "dismissed",
                "reason": "Interpretation needs further classroom evidence.",
            },
        ),
        201,
    )
    assert dismissed["version"] == 2
    assert len(getrun(api_client, c, run["id"])["reviews"]) == 2
    assert getrun(api_client, c, generated["id"])["stale"]
    assert (
        api_client.post(
            f"/v1/teaching-materials/{item['id']}/approve",
            headers=h,
            json={"base_version": 1, "confirmed": True, "reason": "Cannot approve stale material."},
        ).status_code
        == 409
    )
    # New reviewed extraction changes the pinned evidence even when the words are similar.
    revised = review(api_client, c[0], c[4], c[3], base=1)
    assert revised.status_code == 201, revised.text
    assert getrun(api_client, c, run["id"])["stale"]
    assert (
        api_client.post(
            f"/v1/intelligence-runs/{run['id']}/findings/0/reviews",
            headers=h,
            json={
                "base_version": 2,
                "disposition": "accepted",
                "reason": "Stale source must be rejected.",
            },
        ).status_code
        == 409
    )


def test_context_selection_no_silent_sampling_and_invalid_citations(intelligence_case, api_client):
    c = intelligence_case
    h = auth(c[0])
    url = f"/v1/assessments/{c[2]['id']}/intelligence-runs"
    for invalid in [finding("invented exact quote"), finding(source="S999"), finding(page=2)]:
        assert (
            api_client.post(url, headers=h, json={**c[6], "manual_result": invalid}).status_code
            == 422
        )
    assert (
        api_client.post(url, headers=h, json={**c[6], "student_ids": [str(uuid4())]}).status_code
        == 422
    )
    roster = ok(api_client.get(f"/v1/classrooms/{c[1]['id']}/students", headers=h))
    missing = next(s for s in roster if s["registration_number"] == "S002")
    assert (
        api_client.post(url, headers=h, json={**c[6], "student_ids": [missing["id"]]}).status_code
        == 409
    )


def test_durable_worker_validation_retry_cancel_and_lease(
    intelligence_case, api_client, environment, monkeypatch
):
    c = intelligence_case
    h = auth(c[0])
    run = analyzed(api_client, c, manual=False)

    def good(kind, model, snapshot):
        return validate_analysis(finding(), snapshot), "synthetic-model-digest", {"eval_count": 10}

    monkeypatch.setattr(worker.intelligence_provider, "generate", good)
    worker.process_intelligence.run(run["id"])
    done = getrun(api_client, c, run["id"])
    assert done["status"] == "succeeded" and done["attempts"] == 1
    worker.process_intelligence.run(run["id"])
    assert getrun(api_client, c, run["id"])["attempts"] == 1
    failed = analyzed(api_client, c, manual=False)

    def bad(*args):
        raise ValueError("Synthetic invalid model evidence")

    monkeypatch.setattr(worker.intelligence_provider, "generate", bad)
    worker.process_intelligence.run(failed["id"])
    assert getrun(api_client, c, failed["id"])["status"] == "failed"
    ok(api_client.post(f"/v1/intelligence-runs/{failed['id']}/retry", headers=h))
    ok(api_client.post(f"/v1/intelligence-runs/{failed['id']}/cancel", headers=h))
    worker.process_intelligence.run(failed["id"])
    assert getrun(api_client, c, failed["id"])["status"] == "canceled"
    lost = analyzed(api_client, c, manual=False)
    with engine().begin() as db:
        assert db.execute(
            text("SELECT * FROM chalkmate.claim_intelligence(:id)"), {"id": lost["id"]}
        ).first()
    with admin(environment) as db:
        db.execute(
            "UPDATE chalkmate.intelligence_runs SET lease_until=now()-interval '1 minute' "
            "WHERE id=%s",
            (lost["id"],),
        )
    with engine().begin() as db:
        list(db.scalars(text("SELECT chalkmate.pending_intelligence()")))
    assert getrun(api_client, c, lost["id"])["status"] == "failed"


@pytest.mark.parametrize("change", ["quote", "page", "id", "duplicate", "extra"])
def test_exact_evidence_validator(change):
    data = finding()
    snapshot = {
        "sources": [
            {
                "source_id": "S1",
                "text": "A stack uses LIFO: last in first out.",
                "page_from": 1,
                "page_to": 1,
            }
        ]
    }
    if change == "quote":
        data["findings"][0]["citations"][0]["quote"] = "Invented"
    if change == "page":
        data["findings"][0]["citations"][0]["page"] = 2
    if change == "id":
        data["findings"][0]["citations"][0]["source_id"] = "S2"
    if change == "duplicate":
        data["findings"][0]["citations"] *= 2
    if change == "extra":
        data["confidence"] = 0.99
    with pytest.raises(ValueError):
        validate_analysis(data, snapshot)


def test_generation_schema_and_identity_separation():
    snapshot = {
        "topic": "Stacks",
        "question": {},
        "sources": [
            {
                "source_id": "S1",
                "student_name": "Private Name",
                "student_id": str(uuid4()),
                "text": "Reviewed answer",
                "page_from": 1,
                "page_to": 1,
                "mark": "3",
                "maximum": "5",
            }
        ],
    }
    assert "Private Name" not in str(model_evidence(snapshot)) and "student_id" not in str(
        model_evidence(snapshot)
    )
    assert "PRIVATE-KEY" not in student_material(content())
    with pytest.raises(ValueError):
        validate_material(content(), {"material_type": "revision"})


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_INTELLIGENCE") != "1", reason="Explicit local Ollama integration check"
)
def test_live_local_ollama_analysis_and_revision_pack(intelligence_case, api_client):
    c = (
        *intelligence_case[:6],
        {**intelligence_case[6], "model": os.environ.get("INTELLIGENCE_TEST_MODEL", "gemma3:4b")},
    )
    h = auth(c[0])
    run = analyzed(api_client, c, manual=False)

    def wait(rid):
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            result = ok(api_client.get(f"/v1/intelligence-runs/{rid}", headers=h, timeout=90))
            if result["status"] not in ("queued", "running"):
                assert result["status"] == "succeeded", result["error"]
                assert result["model_digest"] and result["usage"].get("eval_count", 0) > 0
                return result
            time.sleep(2)
        pytest.fail("Local teaching run did not finish within ten minutes")

    analysis = wait(run["id"])
    if not analysis["result"]["findings"]:
        # Insufficient evidence is a valid model conclusion. A teacher may still author a finding.
        run = analyzed(api_client, c)
    reviewed = ok(
        api_client.post(
            f"/v1/intelligence-runs/{run['id']}/findings/0/reviews",
            headers=h,
            json={
                "base_version": 0,
                "disposition": "accepted",
                "reason": "Inspected cited answer; this is a synthetic integration check.",
            },
        ),
        201,
    )
    generated = material(api_client, c, run, reviewed, "revision", manual=False)
    result = wait(generated["id"])
    versions = ok(api_client.get(f"/v1/intelligence-runs/{result['id']}/materials", headers=h))
    assert versions and versions[0]["content"]["revision_notes"]
    assert not versions[0]["approval_assignment_version_id"]
    assert len(ok(api_client.get(f"/v1/classrooms/{c[1]['id']}/assignments", headers=h))) == 0


def test_authenticated_reads_do_not_require_a_user_update_lock(
    intelligence_case, api_client, environment
):
    c = intelligence_case
    with admin(environment) as db:
        db.execute("UPDATE chalkmate.users SET email=email WHERE id=%s", (c[0]["id"],))
        result = api_client.get(
            f"/v1/assessments/{c[2]['id']}/topic-summary", headers=auth(c[0]), timeout=5
        )
        assert result.status_code == 200, result.text


def test_assigned_reviewer_can_inspect_and_export_but_cannot_mutate(
    intelligence_case, api_client, accounts
):
    c = intelligence_case
    run, reviewed = accepted(api_client, c)
    generated = material(api_client, c, run, reviewed, "revision")
    item = ok(
        api_client.get(f"/v1/intelligence-runs/{generated['id']}/materials", headers=auth(c[0]))
    )[0]
    reviewer = accounts()
    invitation = ok(
        api_client.post(
            f"/v1/classrooms/{c[1]['id']}/invitations",
            headers=auth(c[0]),
            json={"email": reviewer["email"], "role": "reviewer"},
        ),
        201,
    )
    ok(
        api_client.post(
            "/v1/invitations/accept",
            headers=auth(reviewer),
            json={"token": invitation["url"].split("#token=")[1]},
        )
    )
    h = auth(reviewer)
    assert api_client.get(f"/v1/intelligence-runs/{run['id']}", headers=h).status_code == 200
    exported = api_client.get(
        f"/v1/teaching-materials/{item['id']}/export?answer_key=true", headers=h
    )
    assert exported.status_code == 200 and "PRIVATE-KEY-ANSWER" in exported.text
    assert (
        api_client.post(
            f"/v1/intelligence-runs/{run['id']}/findings/0/reviews",
            headers=h,
            json={
                "base_version": 1,
                "disposition": "dismissed",
                "reason": "Read-only role cannot mutate.",
            },
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            f"/v1/teaching-materials/{item['id']}/approve",
            headers=h,
            json={"base_version": 1, "confirmed": True, "reason": "Read-only role cannot publish."},
        ).status_code
        == 404
    )
