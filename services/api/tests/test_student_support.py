"""Actual local role and release-boundary coverage for student review requests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from conftest import auth
from test_assessments import decision_body, review

pytest_plugins = ["test_assessments"]


def approve_release(client, case):
    teacher, classroom, exam, rubric, paper, pupil = case
    extraction = review(client, teacher, paper, rubric)
    assert extraction.status_code == 201
    decision = client.post(
        f"/v1/submissions/{paper['id']}/decisions",
        headers=auth(teacher),
        json=decision_body(extraction.json(), rubric),
    )
    assert decision.status_code == 201, decision.text
    release = client.post(
        f"/v1/submissions/{paper['id']}/release",
        headers=auth(teacher),
        json={"decision_id": decision.json()["id"]},
    )
    assert release.status_code == 200
    return client.get(f"/v1/classrooms/{classroom['id']}/my-results", headers=auth(pupil)).json()[0]


def test_released_question_request_reply_permissions_and_no_mark_mutation(
    assessment_case, api_client, accounts, environment
):
    teacher, classroom, exam, rubric, paper, pupil = assessment_case
    path = f"/v1/classrooms/{classroom['id']}/review-requests"
    unreleased = {
        "submission_id": paper["id"],
        "question_id": rubric["questions"][0]["id"],
        "released_at": datetime.now(UTC).isoformat(),
        "reason": "Please check this answer before publication.",
    }
    assert api_client.post(path, headers=auth(pupil), json=unreleased).status_code == 404
    result = approve_release(api_client, assessment_case)
    body = {
        "submission_id": paper["id"],
        "question_id": rubric["questions"][0]["id"],
        "released_at": result["released_at"],
        "reason": "Please review the LIFO explanation in my answer.",
    }
    assert api_client.post(path, headers=auth(accounts()), json=body).status_code == 404
    assert (
        api_client.post(
            path, headers=auth(pupil), json={**body, "question_id": str(uuid4())}
        ).status_code
        == 404
    )
    stale = {**body, "released_at": "2000-01-01T00:00:00Z"}
    assert api_client.post(path, headers=auth(pupil), json=stale).status_code == 409
    created = api_client.post(path, headers=auth(pupil), json=body)
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["question_label"] == "Q1" and item["student_label"] == "Student · S001"
    assert api_client.post(path, headers=auth(pupil), json=body).status_code == 409
    assert len(api_client.get(path, headers=auth(teacher)).json()) == 1
    reviewer = accounts()
    invitation = api_client.post(
        f"/v1/classrooms/{classroom['id']}/invitations",
        headers=auth(teacher),
        json={"email": reviewer["email"], "role": "reviewer"},
    ).json()
    assert (
        api_client.post(
            "/v1/invitations/accept",
            headers=auth(reviewer),
            json={"token": invitation["url"].split("#token=")[1]},
        ).status_code
        == 200
    )
    response_path = f"/v1/review-requests/{item['id']}/resolve"
    reply = {"response": "I checked the rubric and your answer; the released marks remain correct."}
    assert len(api_client.get(path, headers=auth(reviewer)).json()) == 1
    assert api_client.post(response_path, headers=auth(reviewer), json=reply).status_code == 404
    assert api_client.post(response_path, headers=auth(pupil), json=reply).status_code == 404
    response = api_client.post(response_path, headers=auth(teacher), json=reply)
    assert response.status_code == 200, response.text
    assert response.json()["resolved_at"] and response.json()["response"] == reply["response"]
    assert api_client.post(response_path, headers=auth(teacher), json=reply).status_code == 409
    after = api_client.get(
        f"/v1/classrooms/{classroom['id']}/my-results", headers=auth(pupil)
    ).json()[0]
    assert after == result
    assert api_client.get(path, headers=auth(pupil)).json()[0]["response"] == reply["response"]
    with psycopg.connect(
        environment.database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute("SELECT set_config('app.user_id',%s,true)", (accounts()["id"],))
        assert db.execute("SELECT id FROM chalkmate.review_requests").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE chalkmate.review_requests SET response='forged'")


def test_overview_counts_missing_replies_and_archived_request_guard(
    assessment_case, api_client, environment
):
    teacher, classroom, exam, rubric, paper, pupil = assessment_case
    path = f"/v1/classrooms/{classroom['id']}"
    initial = api_client.get(path + "/overview", headers=auth(teacher))
    assert initial.status_code == 200, initial.text
    counts = {t["label"]: t["count"] for t in initial.json()["tasks"]}
    assert counts["Papers to review"] == 1 and counts["Student review requests"] == 0
    assert api_client.get(path + "/overview", headers=auth(pupil)).status_code == 404
    assignment = api_client.post(
        path + "/assignments",
        headers=auth(teacher),
        json={
            "title": "Overdue practice",
            "instructions": "Explain a stack.",
            "due_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert assignment.status_code == 201, assignment.text
    version = assignment.json()["version"]
    published = api_client.post(
        f"/v1/assignment-versions/{version['id']}/publish", headers=auth(teacher), json={}
    )
    assert published.status_code == 200, published.text
    with psycopg.connect(
        environment.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute(
            "UPDATE chalkmate.assignment_versions SET due_at=now()-interval '1 day' WHERE id=%s",
            (version["id"],),
        )
    counts = {
        t["label"]: t["count"]
        for t in api_client.get(path + "/overview", headers=auth(teacher)).json()["tasks"]
    }
    assert counts["Overdue responses"] == 2
    result = approve_release(api_client, assessment_case)
    body = {
        "submission_id": paper["id"],
        "question_id": rubric["questions"][0]["id"],
        "released_at": result["released_at"],
        "reason": "Please look at my explanation again.",
    }
    assert (
        api_client.post(path + "/review-requests", headers=auth(pupil), json=body).status_code
        == 201
    )
    assert api_client.patch(path, headers=auth(teacher), json={"archived": True}).status_code == 200
    assert (
        api_client.post(path + "/review-requests", headers=auth(pupil), json=body).status_code
        == 409
    )
