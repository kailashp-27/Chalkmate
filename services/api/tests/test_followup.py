"""Phase 4: real local API/RLS/outbox integration and isolated transport recovery."""

import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import psycopg
import pytest
from conftest import auth
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from test_assessments import decision_body, pdf, review

from chalkmate import followup_worker
from chalkmate.followup_rules import compare_score, validate_template
from chalkmate.followup_schemas import ScoreRule
from chalkmate.mail_provider import (
    ProviderFailure,
    captured_message,
    message_id,
    send,
    verify_webhook,
)
from chalkmate.processing import engine

pytest_plugins = ["test_assessments"]


def checked(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def admin(environment):
    return psycopg.connect(
        environment.migration_database_url.replace("postgresql+psycopg://", "postgresql://")
    )


@pytest.fixture
def followup_case(assessment_case, api_client):
    account, classroom, assessment, rubric, paper, pupil = assessment_case
    h = auth(account)
    extraction = checked(review(api_client, account, paper, rubric), 201)
    decision = checked(
        api_client.post(
            f"/v1/submissions/{paper['id']}/decisions",
            headers=h,
            json=decision_body(extraction, rubric),
        ),
        201,
    )
    checked(
        api_client.post(
            f"/v1/submissions/{paper['id']}/release",
            headers=h,
            json={"decision_id": decision["id"]},
        )
    )
    assignment = checked(
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/assignments",
            headers=h,
            json={
                "title": "Stack practice",
                "instructions": "Explain a stack with an example.",
                "due_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            },
        ),
        201,
    )
    vid = assignment["version"]["id"]
    checked(api_client.post(f"/v1/assignment-versions/{vid}/publish", headers=h, json={}))
    request = {
        "assignment_version_id": vid,
        "rule": {
            "assessment_id": assessment["id"],
            "operator": "lt",
            "threshold": "5",
            "maximum": "5",
        },
        "subject": "{assignment_title}",
        "body": "Hello {student_name}",
        "include_score": True,
        "skip_submitted": True,
    }
    return account, classroom, assignment, paper, pupil, request


def preview_campaign(client, case, **changes):
    account, classroom, assignment, paper, pupil, request = case
    request = {**request, **changes}
    preview = checked(
        client.post(
            f"/v1/classrooms/{classroom['id']}/campaign-previews",
            headers=auth(account),
            json=request,
        ),
        201,
    )
    body = {
        "preview_id": preview["id"],
        "digest": preview["digest"],
        "scheduled_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    campaign = checked(
        client.post(
            f"/v1/classrooms/{classroom['id']}/campaigns", headers=auth(account), json=body
        ),
        201,
    )
    delivery = checked(
        client.get(f"/v1/campaigns/{campaign['id']}/deliveries", headers=auth(account))
    )[0]
    return preview, campaign, delivery, body


def due(environment, campaign):
    with admin(environment) as db:
        db.execute(
            "UPDATE chalkmate.campaigns SET scheduled_at=now()-interval '1 minute' WHERE id=%s",
            (campaign["id"],),
        )


def outcome(client, case, campaign):
    return checked(client.get(f"/v1/campaigns/{campaign['id']}/deliveries", headers=auth(case[0])))[
        0
    ]


@pytest.mark.parametrize(
    ("score", "operator", "expected"),
    [
        ("24.99", "lt", True),
        ("25", "lt", False),
        ("25.01", "lt", False),
        ("25", "lte", True),
        ("25", "eq", True),
        ("25.01", "gt", True),
        ("25", "gte", True),
    ],
)
def test_score_boundary(score, operator, expected):
    assert compare_score(Decimal(score), operator, Decimal("25")) is expected


@pytest.mark.parametrize(
    "subject,body",
    [
        ("bad\nsubject", "Hello"),
        ("Hello", "{student_name.__class__}"),
        ("Hello", "{score}"),
        ("Hello", "{student_name!r}"),
        ("Hello", "{student_name:>20}"),
    ],
)
def test_template_blocks_leaks(subject, body):
    with pytest.raises(HTTPException):
        validate_template(subject, body, False)


def test_rule_rejects_impossible_threshold():
    with pytest.raises(ValidationError):
        ScoreRule(assessment_id=uuid4(), threshold="51", maximum="50")


def test_assignment_publication_private_versions_and_files(
    followup_case, api_client, environment, accounts
):
    case = followup_case
    account, classroom, assignment, paper, pupil, req = case
    vid = req["assignment_version_id"]
    h = auth(account)
    sh = auth(pupil)
    student_view = checked(api_client.get(f"/v1/assignment-versions/{vid}", headers=sh))
    assert student_view["can_submit"] and not student_view["is_staff"]
    stranger = accounts()
    assert (
        api_client.get(f"/v1/assignment-versions/{vid}", headers=auth(stranger)).status_code == 404
    )
    result = checked(
        api_client.post(
            f"/v1/assignment-versions/{vid}/responses",
            headers=sh,
            data={"base_version": "0", "text": "LIFO means last in first out."},
            files={"file": ("answer.pdf", pdf(), "application/pdf")},
        ),
        201,
    )
    assert result["late"] and result["version"] == 1
    signed = checked(
        api_client.get(f"/v1/assignment-responses/{result['id']}/download", headers=sh)
    )
    assert httpx.get(signed["url"]).status_code == 200
    assert (
        api_client.get(
            f"/v1/assignment-responses/{result['id']}/download", headers=auth(stranger)
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            f"/v1/assignment-versions/{vid}/responses",
            headers=sh,
            data={"base_version": "0", "text": "stale"},
        ).status_code
        == 409
    )
    checked(
        api_client.post(
            f"/v1/assignment-versions/{vid}/responses",
            headers=sh,
            data={"base_version": "1", "text": "Improved example."},
        ),
        201,
    )
    assert len(checked(api_client.get(f"/v1/assignment-versions/{vid}/responses", headers=h))) == 2
    revised = checked(
        api_client.post(
            f"/v1/assignments/{assignment['id']}/versions",
            headers=h,
            json={
                "base_version": 1,
                "title": "Stack practice revised",
                "instructions": "Add a diagram.",
                "reason": "Clarify expectations",
            },
        ),
        201,
    )
    newvid = revised["draft"]["id"]
    assert api_client.get(f"/v1/assignment-versions/{newvid}", headers=sh).status_code == 404
    checked(api_client.post(f"/v1/assignment-versions/{newvid}/publish", headers=h, json={}))
    assert not checked(api_client.get(f"/v1/assignment-versions/{vid}", headers=sh))["can_submit"]
    assert (
        api_client.post(
            f"/v1/assignment-versions/{vid}/responses",
            headers=sh,
            data={"base_version": "2", "text": "old instructions"},
        ).status_code
        == 409
    )
    checked(
        api_client.patch(f"/v1/assignments/{assignment['id']}", headers=h, json={"closed": True})
    )
    assert (
        api_client.post(
            f"/v1/assignment-versions/{newvid}/responses",
            headers=sh,
            data={"base_version": "0", "text": "closed"},
        ).status_code
        == 409
    )
    with psycopg.connect(
        environment.database_url.replace("postgresql+psycopg://", "postgresql://")
    ) as db:
        db.execute("SELECT set_config('app.user_id',%s,true)", (pupil["id"],))
        for table in ["campaigns", "campaign_previews", "deliveries", "delivery_attempts"]:
            assert db.execute(f"SELECT id FROM chalkmate.{table}").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT chalkmate.pending_deliveries()")


def test_preview_approval_drift_idempotency_and_scope(followup_case, api_client, environment):
    case = followup_case
    account, classroom, assignment, paper, pupil, req = case
    h = auth(account)
    preview, campaign, delivery, body = preview_campaign(api_client, case)
    assert preview["snapshot"]["selected_count"] == 1
    assert preview["snapshot"]["rows"][1]["reason"] == "Missing assessment submission"
    personal = checked(
        api_client.get(
            f"/v1/campaign-previews/{preview['id']}/recipients/{delivery['student_id']}", headers=h
        )
    )
    assert "4.50 / 5.00" in personal["text"] and pupil["email"] == personal["to"]
    assert "/assignments/" in personal["assignment_link"]
    again = checked(
        api_client.post(f"/v1/classrooms/{classroom['id']}/campaigns", headers=h, json=body), 201
    )
    assert (
        again["id"] == campaign["id"]
        and len(checked(api_client.get(f"/v1/campaigns/{campaign['id']}/deliveries", headers=h)))
        == 1
    )
    assert (
        api_client.get(
            f"/v1/campaigns/{campaign['id']}/deliveries", headers=auth(pupil)
        ).status_code
        == 404
    )
    with engine().begin() as db:
        assert delivery["id"] not in [
            str(i) for i in db.scalars(text("SELECT chalkmate.pending_deliveries()"))
        ]
    fresh = checked(
        api_client.post(f"/v1/classrooms/{classroom['id']}/campaign-previews", headers=h, json=req),
        201,
    )
    checked(
        api_client.patch(
            f"/v1/classrooms/{classroom['id']}/students/{delivery['student_id']}/contact",
            headers=h,
            json={"email": "different@example.com"},
        )
    )
    assert (
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/campaigns",
            headers=h,
            json={"preview_id": fresh["id"], "digest": fresh["digest"]},
        ).status_code
        == 409
    )
    blocked = checked(
        api_client.post(f"/v1/classrooms/{classroom['id']}/campaign-previews", headers=h, json=req),
        201,
    )
    assert blocked["snapshot"]["blocked_count"] == 1
    assert (
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/campaigns",
            headers=h,
            json={"preview_id": blocked["id"], "digest": blocked["digest"]},
        ).status_code
        == 409
    )
    excluded = checked(
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/campaign-previews",
            headers=h,
            json={**req, "exclude_student_ids": [delivery["student_id"]]},
        ),
        201,
    )
    assert (
        excluded["snapshot"]["blocked_count"] == 0 and excluded["snapshot"]["selected_count"] == 0
    )


def test_outbox_capture_once_and_uncertain_reconciliation(
    followup_case, api_client, environment, monkeypatch
):
    case = followup_case
    preview, campaign, delivery, body = preview_campaign(api_client, case)
    due(environment, campaign)

    def lost(provider, delivery_id, payload):
        send(provider, delivery_id, payload)
        raise ProviderFailure("Synthetic lost receipt")

    with monkeypatch.context() as patch:
        patch.setattr(followup_worker, "send", lost)
        followup_worker.process_delivery.run(delivery["id"])
    item = outcome(api_client, case, campaign)
    assert item["status"] == "uncertain", item
    assert captured_message(delivery["id"])
    followup_worker.process_delivery.run(delivery["id"])
    assert outcome(api_client, case, campaign)["attempts"] == 1
    assert (
        api_client.post(f"/v1/deliveries/{delivery['id']}/retry", headers=auth(case[0])).status_code
        == 409
    )
    recovered = checked(
        api_client.post(f"/v1/deliveries/{delivery['id']}/reconcile", headers=auth(case[0]))
    )
    assert recovered["status"] == "captured" and recovered["provider_id"]
    results = httpx.get(
        "http://127.0.0.1:54324/api/v1/search", params={"query": f"tag:chalkmate-{delivery['id']}"}
    ).json()
    assert (
        len(
            [
                i
                for i in results["messages"]
                if i["MessageID"].strip("<>") == message_id(delivery["id"])
            ]
        )
        == 1
    )
    assert (
        len(
            checked(
                api_client.get(f"/v1/deliveries/{delivery['id']}/attempts", headers=auth(case[0]))
            )
        )
        == 2
    )


def test_reminder_skips_new_response_and_contact_changes_hold(
    followup_case, api_client, environment
):
    case = followup_case
    preview, campaign, delivery, body = preview_campaign(api_client, case)
    checked(
        api_client.post(
            f"/v1/assignment-versions/{case[5]['assignment_version_id']}/responses",
            headers=auth(case[4]),
            data={"base_version": "0", "text": "Done."},
        ),
        201,
    )
    due(environment, campaign)
    followup_worker.process_delivery.run(delivery["id"])
    assert outcome(api_client, case, campaign)["status"] == "skipped"
    preview, campaign, delivery, body = preview_campaign(api_client, case, skip_submitted=False)
    checked(
        api_client.patch(
            f"/v1/classrooms/{case[1]['id']}/students/{delivery['student_id']}/contact",
            headers=auth(case[0]),
            json={"email": "changed@example.com"},
        )
    )
    due(environment, campaign)
    followup_worker.process_delivery.run(delivery["id"])
    assert outcome(api_client, case, campaign)["status"] == "held"
    assert captured_message(delivery["id"]) is None


def test_failure_retry_and_expired_lease_never_blind_resends(
    followup_case, api_client, environment, monkeypatch
):
    case = followup_case
    preview, campaign, delivery, body = preview_campaign(api_client, case)
    due(environment, campaign)

    def rejected(*args):
        raise ProviderFailure("Synthetic definite rejection", True)

    with monkeypatch.context() as patch:
        patch.setattr(followup_worker, "send", rejected)
        followup_worker.process_delivery.run(delivery["id"])
    assert outcome(api_client, case, campaign)["status"] == "failed"
    checked(api_client.post(f"/v1/deliveries/{delivery['id']}/retry", headers=auth(case[0])))
    with engine().begin() as db:
        assert db.execute(
            text("SELECT * FROM chalkmate.claim_delivery(:id)"), {"id": delivery["id"]}
        ).first()
    with admin(environment) as db:
        db.execute(
            "UPDATE chalkmate.deliveries SET lease_until=now()-interval '1 second' WHERE id=%s",
            (delivery["id"],),
        )
    with engine().begin() as db:
        assert delivery["id"] not in [
            str(i) for i in db.scalars(text("SELECT chalkmate.pending_deliveries()"))
        ]
    assert outcome(api_client, case, campaign)["status"] == "uncertain"
    assert captured_message(delivery["id"]) is None


def test_signed_webhooks_reject_tampering_and_replay_window():
    key = b"local-test-secret-at-least-32-bytes"
    secret = "whsec_" + base64.b64encode(key).decode()
    body = b'{"type":"email.delivered"}'
    now = int(time.time())
    eid = "msg_test"
    signed = f"{eid}.{now}.".encode() + body
    sig = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    headers = {"svix-id": eid, "svix-timestamp": str(now), "svix-signature": "v1," + sig}
    assert verify_webhook(body, headers, secret, now) == eid
    for changed, clock in [(body + b" ", now), (body, now + 301)]:
        with pytest.raises(ValueError):
            verify_webhook(changed, headers, secret, clock)


def test_verified_events_are_idempotent_and_bounce_suppresses(
    followup_case, api_client, environment
):
    case = followup_case
    preview, campaign, delivery, body = preview_campaign(api_client, case)
    pid = "synthetic-" + uuid4().hex
    now = datetime.now(UTC)
    with admin(environment) as db:
        db.execute(
            "UPDATE chalkmate.campaigns SET provider='resend' WHERE id=%s", (campaign["id"],)
        )
        db.execute(
            "UPDATE chalkmate.deliveries SET status='accepted',provider_id=%s WHERE id=%s",
            (pid, delivery["id"]),
        )

    def event(eid, kind, when):
        with engine().begin() as db:
            return db.scalar(
                text("SELECT chalkmate.record_delivery_event(:eid,:pid,:kind,:when)"),
                {"eid": eid, "pid": pid, "kind": kind, "when": when},
            )

    eid = "test-" + uuid4().hex
    assert event(eid, "email.delivered", now)
    assert event(eid, "email.delivered", now)
    assert not event(eid, "email.bounced", now)
    assert outcome(api_client, case, campaign)["status"] == "delivered"
    event("test-" + uuid4().hex, "email.sent", now - timedelta(minutes=1))
    assert outcome(api_client, case, campaign)["status"] == "delivered"
    event("test-" + uuid4().hex, "email.bounced", now - timedelta(minutes=2))
    assert outcome(api_client, case, campaign)["status"] == "bounced"
    blocked = checked(
        api_client.post(
            f"/v1/classrooms/{case[1]['id']}/campaign-previews", headers=auth(case[0]), json=case[5]
        ),
        201,
    )
    assert blocked["snapshot"]["blocked_count"] == 1


def test_live_filter_below_25_all_dispositions(followup_case, api_client):
    case = followup_case
    account, classroom, assignment, paper, pupil, req = case
    h = auth(account)
    roster_text = "registration_number,name,email\n" + "\n".join(
        f"B{i:02},Boundary {i},boundary{i}@example.com" for i in range(7)
    )
    imported = checked(
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/imports/preview",
            headers=h,
            files={"file": ("boundary.csv", roster_text)},
        )
    )
    checked(
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/imports/{imported['id']}/confirm", headers=h
        )
    )
    roster = checked(api_client.get(f"/v1/classrooms/{classroom['id']}/students", headers=h))
    ids = [
        s["id"]
        for s in sorted(roster, key=lambda s: s["registration_number"])
        if s["registration_number"].startswith("B")
    ]
    assessment = checked(
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/assessments",
            headers=h,
            json={"title": "Boundary assessment"},
        ),
        201,
    )
    rubric = checked(
        api_client.post(
            f"/v1/assessments/{assessment['id']}/rubrics",
            headers=h,
            json={
                "questions": [
                    {
                        "label": "Q1",
                        "prompt": "Explain",
                        "maximum": "50",
                        "model_answer": "An explanation",
                        "criteria": [{"label": "Explanation", "maximum": "50"}],
                    }
                ]
            },
        ),
        201,
    )
    checked(api_client.post(f"/v1/assessments/{assessment['id']}/activate", headers=h))
    for i, mark in enumerate(["24.5", "25", "25.5", "10", "10", "10"]):
        file = checked(
            api_client.post(
                f"/v1/classrooms/{classroom['id']}/files",
                headers=h,
                files={
                    "file": (
                        f"boundary-{i}.pdf",
                        pdf() + f"\n%boundary-{i}".encode(),
                        "application/pdf",
                    )
                },
            ),
            201,
        )
        p = checked(
            api_client.post(
                f"/v1/assessments/{assessment['id']}/submissions",
                headers=h,
                json={
                    "student_id": ids[i],
                    "file_id": file["id"],
                    "identity_confirmed": True,
                },
            ),
            201,
        )
        ex = checked(review(api_client, account, p, rubric), 201)
        if i != 4:
            body = {
                "extraction_id": ex["id"],
                "feedback": "Reviewed",
                "reason": "Teacher reviewed all criteria.",
                "marks": [
                    {"criterion_id": rubric["questions"][0]["criteria"][0]["id"], "mark": mark}
                ],
            }
            checked(
                api_client.post(f"/v1/submissions/{p['id']}/decisions", headers=h, json=body), 201
            )
        if i == 3:
            enrollment = next(s["enrollment_id"] for s in roster if s["id"] == ids[i])
            checked(
                api_client.patch(
                    f"/v1/classrooms/{classroom['id']}/enrollments/{enrollment}",
                    headers=h,
                    json={"status": "withdrawn"},
                )
            )
    # New publication pins the expanded roster. Old instructions/audience remain preserved.
    revised = checked(
        api_client.post(
            f"/v1/assignments/{assignment['id']}/versions",
            headers=h,
            json={
                "base_version": 1,
                "title": "Boundary practice",
                "instructions": "Practice",
                "reason": "Include expanded roster",
            },
        ),
        201,
    )
    vid = revised["draft"]["id"]
    checked(api_client.post(f"/v1/assignment-versions/{vid}/publish", headers=h, json={}))
    request = {
        **req,
        "assignment_version_id": vid,
        "include_score": False,
        "rule": {
            "assessment_id": assessment["id"],
            "operator": "lt",
            "threshold": "25",
            "maximum": "50",
        },
    }
    snapshot = checked(
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/campaign-previews", headers=h, json=request
        ),
        201,
    )["snapshot"]
    rows = {r["student_id"]: r for r in snapshot["rows"]}
    assert rows[ids[0]]["eligible"] and rows[ids[0]]["blocked"]
    assert not rows[ids[1]]["eligible"] and not rows[ids[2]]["eligible"]
    assert rows[ids[3]]["reason"] == "Withdrawn student"
    assert rows[ids[4]]["reason"] == "Unapproved or re-evaluation in progress"
    assert rows[ids[6]]["reason"] == "Missing assessment submission"
    mismatch = checked(
        api_client.post(
            f"/v1/classrooms/{classroom['id']}/campaign-previews",
            headers=h,
            json={**request, "rule": {**request["rule"], "maximum": "100"}},
        ),
        201,
    )
    assert any(r["reason"] == "Different assessment maximum" for r in mismatch["snapshot"]["rows"])


def test_resend_idempotency_and_uncertainty_window(monkeypatch, environment):
    from types import SimpleNamespace

    from pydantic import SecretStr

    from chalkmate import mail_provider

    settings = environment.model_copy(
        update={
            "mail_provider": "resend",
            "enable_external_email": True,
            "resend_api_key": SecretStr("synthetic-test-key"),
        }
    )
    monkeypatch.setattr(mail_provider, "get_settings", lambda: settings)
    calls = []

    def accepted(url, **kwargs):
        assert url == "https://api.resend.com/emails"
        calls.append(kwargs)
        return httpx.Response(200, json={"id": "synthetic-receipt"})

    monkeypatch.setattr(mail_provider.httpx, "post", accepted)
    did = uuid4()
    payload = {
        "from": "Teacher <teacher@example.com>",
        "to": "test@example.com",
        "subject": "Practice",
        "text": "Private assignment link",
    }
    assert send("resend", did, payload) == ("accepted", "synthetic-receipt")
    delivery = SimpleNamespace(
        id=did, payload=payload, provider_id=None, first_attempt_at=datetime.now(UTC)
    )
    assert mail_provider.reconcile("resend", delivery) == ("accepted", "synthetic-receipt")
    assert calls[0]["headers"]["Idempotency-Key"] == calls[1]["headers"]["Idempotency-Key"]
    assert calls[0]["json"] == calls[1]["json"] and calls[0]["json"]["to"] == ["test@example.com"]
    delivery.first_attempt_at = datetime.now(UTC) - timedelta(hours=24)
    with pytest.raises(ProviderFailure, match="expired"):
        mail_provider.reconcile("resend", delivery)
    assert len(calls) == 2

    def lost(*args, **kwargs):
        raise httpx.ReadTimeout("Synthetic lost response")

    monkeypatch.setattr(mail_provider.httpx, "post", lost)
    with pytest.raises(ProviderFailure) as failure:
        send("resend", did, payload)
    assert not failure.value.definite


def test_preview_expiry_and_recipient_cancellation(followup_case, api_client, environment):
    case = followup_case
    h = auth(case[0])
    cid = case[1]["id"]
    pre = checked(
        api_client.post(f"/v1/classrooms/{cid}/campaign-previews", headers=h, json=case[5]), 201
    )
    with admin(environment) as db:
        db.execute(
            "UPDATE chalkmate.campaign_previews SET expires_at=now()-interval '1 minute' "
            "WHERE id=%s",
            (pre["id"],),
        )
    assert (
        api_client.post(
            f"/v1/classrooms/{cid}/campaigns",
            headers=h,
            json={"preview_id": pre["id"], "digest": pre["digest"]},
        ).status_code
        == 409
    )
    pre, campaign, delivery, body = preview_campaign(api_client, case)
    checked(api_client.post(f"/v1/deliveries/{delivery['id']}/cancel", headers=h))
    due(environment, campaign)
    followup_worker.process_delivery.run(delivery["id"])
    assert outcome(api_client, case, campaign)["status"] == "canceled"
    assert captured_message(delivery["id"]) is None
