"""Phase 3 regression tests use only synthetic accounts and local infrastructure."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from conftest import auth
from sqlalchemy.orm import Session
from test_assessments import decision_body, review

from chalkmate import assessment_models as m
from chalkmate.db import get_engine, set_identity
from chalkmate.review_routes import changes

pytest_plugins = ["test_assessments"]


def test_revision_reevaluation_preserves_releases_and_history(
    assessment_case, api_client, accounts
):
    account, classroom, assessment, rubric, paper, student = assessment_case
    headers = auth(account)
    url = f"/v1/submissions/{paper['id']}"
    extraction = review(api_client, account, paper, rubric).json()
    question = rubric["questions"][0]
    marks = decision_body(extraction, rubric)["marks"]
    saved = api_client.post(
        f"{url}/questions/{question['id']}/reviews",
        headers=headers,
        json={
            "extraction_id": extraction["id"],
            "rubric_id": rubric["id"],
            "marks": marks,
            "feedback": "Good LIFO explanation. Add a push/pop example.",
        },
    )
    assert saved.status_code == 201, saved.text
    stale = api_client.post(
        f"{url}/questions/{question['id']}/reviews",
        headers=headers,
        json={
            "extraction_id": extraction["id"],
            "rubric_id": rubric["id"],
            "marks": marks,
            "feedback": "Stale browser copy",
        },
    )
    assert stale.status_code == 409
    approval_body = decision_body(extraction, rubric)
    assert (
        api_client.post(f"{url}/decisions", headers=headers, json=approval_body).status_code == 409
    )
    approval_body["question_review_ids"] = [saved.json()["id"]]
    approved = api_client.post(f"{url}/decisions", headers=headers, json=approval_body)
    assert approved.status_code == 201, approved.text
    assert approved.json()["question_feedback"][question["id"]].startswith("Good LIFO")
    released = api_client.post(
        f"{url}/release", headers=headers, json={"decision_id": approved.json()["id"]}
    )
    assert released.status_code == 200, released.text
    questions = deepcopy(rubric["questions"])
    questions[0]["criteria"][0]["maximum"] = "4.00"
    questions[0]["criteria"][0]["guidance"] = "Explain the ordering, with a correct example."
    questions[0]["maximum"] = "6.00"
    questions[0]["accepted_alternatives"] = ["Last item pushed is the first item popped."]
    revision_body = {
        "questions": questions,
        "base_version": 1,
        "reason": "Clarify the credit for ordering and examples.",
    }
    revision = api_client.post(
        f"/v1/assessments/{assessment['id']}/rubrics", headers=headers, json=revision_body
    )
    assert revision.status_code == 201, revision.text
    assert (
        api_client.post(
            f"/v1/assessments/{assessment['id']}/rubrics", headers=headers, json=revision_body
        ).status_code
        == 409
    )
    revision = revision.json()
    current = api_client.get(f"/v1/assessments/{assessment['id']}", headers=headers).json()
    assert current["rubric"]["id"] == rubric["id"]
    assert current["draft_rubric"]["id"] == revision["id"]
    diff = api_client.get(
        f"/v1/assessments/{assessment['id']}/rubrics/{revision['id']}/diff", headers=headers
    )
    assert diff.status_code == 200, diff.text
    assert diff.json()["affected_submissions"] == 1
    assert any("maximum" in change["path"] for change in diff.json()["changes"])
    assert (
        api_client.post(f"/v1/assessments/{assessment['id']}/activate", headers=headers).status_code
        == 409
    )
    activated = api_client.post(
        f"/v1/assessments/{assessment['id']}/activate",
        headers=headers,
        json={"rubric_id": revision["id"]},
    )
    assert activated.status_code == 200, activated.text
    queue = api_client.get(
        f"/v1/assessments/{assessment['id']}/review-queue", headers=headers
    ).json()
    assert queue[0]["rubric_version"] == 1 and queue[0]["latest_rubric_version"] == 2
    assert api_client.get(url, headers=headers).json()["rubric"]["id"] == rubric["id"]
    reopened = api_client.post(
        f"{url}/reevaluate",
        headers=headers,
        json={
            "rubric_id": revision["id"],
            "base_extraction_version": 1,
            "reason": "Apply the clarified rubric consistently.",
        },
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["decision"] is None
    assert reopened.json()["extraction"]["reviewed_by"] is None
    assert reopened.json()["question_reviews"] == []
    assert (
        api_client.post(
            f"{url}/release", headers=headers, json={"decision_id": approved.json()["id"]}
        ).status_code
        == 409
    )
    prior = api_client.get(
        f"/v1/classrooms/{classroom['id']}/my-results", headers=auth(student)
    ).json()
    assert len(prior) == 1 and prior[0]["total"] == "4.50" and prior[0]["maximum"] == "5.00"
    assert prior[0]["questions"][0]["criteria"][0]["maximum"] == "3.00"
    assert (
        "4.50" in api_client.get(f"/v1/assessments/{assessment['id']}/export", headers=headers).text
    )
    revised_extraction = review(api_client, account, paper, revision, base=2)
    assert revised_extraction.status_code == 201, revised_extraction.text
    body = decision_body(revised_extraction.json(), revision)
    body["marks"][0]["mark"] = "4.00"
    body["feedback"] = "Re-evaluated feedback using the clarified rubric."
    second = api_client.post(f"{url}/decisions", headers=headers, json=body)
    assert second.status_code == 201, second.text
    assert (
        api_client.post(
            f"{url}/release", headers=headers, json={"decision_id": second.json()["id"]}
        ).status_code
        == 200
    )
    results = api_client.get(
        f"/v1/classrooms/{classroom['id']}/my-results", headers=auth(student)
    ).json()
    assert len(results) == 1 and results[0]["total"] == "6.00" and results[0]["maximum"] == "6.00"
    assert results[0]["questions"][0]["model_answer"] == ""
    assert results[0]["questions"][0]["accepted_alternatives"] == []
    assert results[0]["questions"][0]["criteria"][0]["guidance"] == ""
    history = api_client.get(f"{url}/history", headers=headers).json()
    assert len(history["releases"]) == 2 and len(history["decisions"]) == 2
    assert history["reevaluations"][0]["reason"].startswith("Apply")
    assert len(history["extractions"]) == 3
    other = accounts()
    for path in [
        f"{url}/history",
        f"/v1/assessments/{assessment['id']}/review-queue",
        f"/v1/assessments/{assessment['id']}/calibrations",
        f"/v1/assessments/{assessment['id']}/rubrics",
    ]:
        assert api_client.get(path, headers=auth(student)).status_code == 404
        assert api_client.get(path, headers=auth(other)).status_code == 404


def test_calibration_snapshots_and_stale_question_rejection(assessment_case, api_client):
    account, classroom, assessment, rubric, paper, _ = assessment_case
    headers = auth(account)
    extraction = review(api_client, account, paper, rubric).json()
    url = f"/v1/submissions/{paper['id']}"
    body = {
        "extraction_id": extraction["id"],
        "rubric_id": rubric["id"],
        "band": "middle",
        "note": "A representative partially correct response.",
        "marks": decision_body(extraction, rubric)["marks"],
    }
    reference = api_client.post(f"{url}/calibrations", headers=headers, json=body)
    assert reference.status_code == 201, reference.text
    assert reference.json()["snapshot"]["mean_absolute_error"] is None
    with Session(get_engine()) as db, db.begin():
        set_identity(db, account["id"], account["email"])
        proposal = m.Proposal(
            workspace_id=UUID(classroom["workspace_id"]),
            classroom_id=UUID(classroom["id"]),
            submission_id=UUID(paper["id"]),
            extraction_id=UUID(extraction["id"]),
            rubric_id=UUID(rubric["id"]),
            model="synthetic-calibration",
            model_digest="fixture-digest",
            prompt_version="fixture-v1",
            output={
                "criteria": [
                    {
                        "criterion_id": c["id"],
                        "question_id": rubric["questions"][0]["id"],
                        "mark": c["maximum"],
                        "explanation": "Test fixture",
                        "evidence_page": 1,
                        "evidence_quote": "LIFO",
                    }
                    for c in rubric["questions"][0]["criteria"]
                ],
                "feedback": "Fixture feedback",
                "review_reasons": [],
            },
        )
        db.add(proposal)
        db.flush()
        body["proposal_id"] = str(proposal.id)
    compared = api_client.post(f"{url}/calibrations", headers=headers, json=body)
    assert compared.status_code == 201, compared.text
    snapshot = compared.json()["snapshot"]
    assert snapshot["mean_absolute_error"] == "0.2500"
    assert snapshot["observed_total"] == "5.00"
    assert snapshot["model_digest"] == "fixture-digest"
    assert snapshot["answers"][0]["text"].startswith("A stack")
    invalid = deepcopy(body)
    invalid["marks"][0]["mark"] = "3.01"
    assert api_client.post(f"{url}/calibrations", headers=headers, json=invalid).status_code == 422
    invalid = {**body, "proposal_id": str(uuid4())}
    assert api_client.post(f"{url}/calibrations", headers=headers, json=invalid).status_code == 409
    assert review(api_client, account, paper, rubric, base=1).status_code == 201
    assert api_client.post(f"{url}/calibrations", headers=headers, json=body).status_code == 409
    question = rubric["questions"][0]
    assert (
        api_client.post(
            f"{url}/questions/{question['id']}/reviews",
            headers=headers,
            json={
                "extraction_id": extraction["id"],
                "rubric_id": rubric["id"],
                "marks": body["marks"],
                "feedback": "Old extraction",
            },
        ).status_code
        == 409
    )
    saved = api_client.get(
        f"/v1/assessments/{assessment['id']}/calibrations", headers=headers
    ).json()
    assert len(saved) == 2 and saved[0]["snapshot"]["mean_absolute_error"] == "0.2500"


def test_diff_tracks_added_removed_and_reordered_questions():
    before = [
        {"id": "a", "label": "Q1", "maximum": "5"},
        {"id": "b", "label": "Q2", "maximum": "3"},
    ]
    assert changes(before, list(reversed(before)), "questions")[0]["path"] == "questions.order"
    assert changes(before, before[:1], "questions")[0]["after"] == "—"


def test_selected_calibration_is_pinned_to_grading_and_cannot_use_own_answer(
    assessment_case, api_client, monkeypatch
):
    from fastapi import HTTPException
    from test_assessments import pdf

    from chalkmate import ollama_provider
    from chalkmate.assessment_routes import approve_decision, queue_job
    from chalkmate.assessment_schemas import DecisionInput, JobInput
    from chalkmate.auth import Identity

    account, classroom, assessment, rubric, paper, _ = assessment_case
    headers = auth(account)
    extraction = review(api_client, account, paper, rubric).json()
    reference = api_client.post(
        f"/v1/submissions/{paper['id']}/calibrations",
        headers=headers,
        json={
            "extraction_id": extraction["id"],
            "rubric_id": rubric["id"],
            "band": "high",
            "note": "Teacher-selected reference",
            "marks": decision_body(extraction, rubric)["marks"],
        },
    ).json()
    roster = api_client.get(f"/v1/classrooms/{classroom['id']}/students", headers=headers).json()
    other_student = next(s for s in roster if s["id"] != paper["student_id"])
    file = api_client.post(
        f"/v1/classrooms/{classroom['id']}/files",
        headers=headers,
        files={"file": ("second.pdf", pdf() + b"\n% second synthetic paper\n", "application/pdf")},
    ).json()
    target = api_client.post(
        f"/v1/assessments/{assessment['id']}/submissions",
        headers=headers,
        json={"student_id": other_student["id"], "file_id": file["id"], "identity_confirmed": True},
    )
    assert target.status_code == 201, target.text
    target = target.json()
    target_extraction = review(api_client, account, target, rubric)
    assert target_extraction.status_code == 201
    monkeypatch.setattr(ollama_provider, "model_info", lambda *a, **kw: "fixture-digest")
    actor = Identity(UUID(account["id"]), account["email"])
    with Session(get_engine()) as db:
        set_identity(db, account["id"], account["email"])
        selected = JobInput(kind="grade", model="synthetic", calibration_ids=[reference["id"]])
        job = queue_job(UUID(target["id"]), selected, db, actor)
        assert job.calibration_ids == [reference["id"]]
        assert queue_job(UUID(target["id"]), selected, db, actor).id == job.id
        plain = queue_job(UUID(target["id"]), JobInput(kind="grade", model="synthetic"), db, actor)
        assert plain.id != job.id
        with pytest.raises(HTTPException, match="pending processing"):
            approve_decision(
                UUID(target["id"]),
                DecisionInput.model_validate(decision_body(target_extraction.json(), rubric)),
                db,
                actor,
            )
        with pytest.raises(HTTPException, match="other papers"):
            queue_job(UUID(paper["id"]), selected, db, actor)
        db.rollback()  # The dispatcher must never see these deterministic fixture jobs.


def test_calibration_examples_reach_local_prompt_without_identity(monkeypatch):
    import json

    from chalkmate import ollama_provider

    captured = {}
    example = {
        "example_id": "snapshot-v1",
        "band": "middle",
        "reviewed_answers": [],
        "reference_marks": [],
    }
    monkeypatch.setattr(ollama_provider, "model_info", lambda *a, **kw: "test-digest")

    def fake_chat(model, messages, schema):
        captured["messages"] = messages
        return {
            "message": {"content": json.dumps({"criteria": [], "feedback": "Fixture feedback"})}
        }

    monkeypatch.setattr(ollama_provider, "chat", fake_chat)
    ollama_provider.grade("synthetic", [], [], calibration_examples=[example])
    payload = json.loads(captured["messages"][1]["content"])
    assert payload["teacher_reference_examples"] == [example]
    assert "student_name" not in payload and "email" not in payload
