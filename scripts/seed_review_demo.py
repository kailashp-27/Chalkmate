"""Add synthetic Phase 3 examples to the generated local demo account only."""

import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
from create_test_pdf import paper_bytes

from chalkmate.config import get_settings

settings = get_settings()
if settings.app_env != "development" or urlparse(settings.supabase_url).hostname not in {
    "127.0.0.1",
    "localhost",
}:
    raise RuntimeError("Local development only")
credentials = json.loads(Path(".tmp/demo-credentials.json").read_text(encoding="utf-8"))
if not credentials["email"].startswith("teacher.demo.") or not credentials["email"].endswith(
    "@example.com"
):
    raise RuntimeError("Only the generated synthetic demo account may be seeded")
login = httpx.post(
    f"{settings.supabase_url}/auth/v1/token?grant_type=password",
    headers={"apikey": settings.supabase_anon_key},
    json=credentials,
    timeout=30,
)
login.raise_for_status()
with httpx.Client(
    base_url="http://127.0.0.1:8100",
    timeout=30,
    headers={"Authorization": f"Bearer {login.json()['access_token']}"},
) as client:

    def call(method, url, **kwargs):
        result = client.request(method, url, **kwargs)
        result.raise_for_status()
        return result.json()

    workspace = next(
        w
        for w in call("GET", "/v1/session")["workspaces"]
        if w["name"] == "Demo teaching workspace"
    )
    classes = call("GET", f"/v1/workspaces/{workspace['id']}/classrooms")
    classroom = next(c for c in classes if c["name"] == "Computer Science · Section A")
    base = f"/v1/classrooms/{classroom['id']}"
    if any(a["title"] == "Demo · Reliable review" for a in call("GET", f"{base}/assessments")):
        print("Review demo already exists; existing work was preserved.")
        raise SystemExit(0)
    roster = call("GET", f"{base}/students")
    entries = [
        ("DEMO001", "Ada Example"),
        ("DEMO002", "Grace Example"),
        ("DEMO003", "Alan Example"),
    ]
    missing = [
        (registration, name)
        for registration, name in entries
        if not any(s["registration_number"] == registration for s in roster)
    ]
    if missing:
        content = "registration_number,name,email\n" + "\n".join(
            f"{reg},{name}," for reg, name in missing
        )
        preview = call(
            "POST", f"{base}/imports/preview", files={"file": ("synthetic-roster.csv", content)}
        )
        call("POST", f"{base}/imports/{preview['id']}/confirm")
    roster = call("GET", f"{base}/students")
    assessment = call(
        "POST",
        f"{base}/assessments",
        json={
            "title": "Demo · Reliable review",
            "instructions": (
                "Synthetic examples for exploring review queues, rubric versions, "
                "calibration, and re-evaluation."
            ),
        },
    )
    rubric = call(
        "POST",
        f"/v1/assessments/{assessment['id']}/rubrics",
        json={
            "base_version": 0,
            "questions": [
                {
                    "label": "Q1",
                    "prompt": "Explain how a stack orders its elements.",
                    "model_answer": "A stack follows last in, first out (LIFO).",
                    "accepted_alternatives": ["Last item pushed is the first item popped."],
                    "maximum": "10",
                    "criteria": [
                        {
                            "label": "Identifies LIFO ordering",
                            "maximum": "5",
                            "guidance": "Credit correct last-in-first-out terminology.",
                        },
                        {
                            "label": "Explains the ordering",
                            "maximum": "5",
                            "guidance": "Credit an explanation or a correct push/pop example.",
                        },
                    ],
                }
            ],
        },
    )
    call("POST", f"/v1/assessments/{assessment['id']}/activate")
    papers = []
    answers = [
        "A stack uses LIFO: last in, first out.",
        "The last element is removed first.",
        "Elements are kept in a stack.",
    ]
    for index, ((registration, _), answer) in enumerate(zip(entries, answers, strict=True)):
        student = next(s for s in roster if s["registration_number"] == registration)
        file = call(
            "POST",
            f"{base}/files",
            files={
                "file": (
                    f"{registration}-synthetic.pdf",
                    paper_bytes(f"Q1. {answer}"),
                    "application/pdf",
                )
            },
        )
        paper = call(
            "POST",
            f"/v1/assessments/{assessment['id']}/submissions",
            json={"student_id": student["id"], "file_id": file["id"], "identity_confirmed": True},
        )
        papers.append(paper)
        if index == 2:
            continue
        extraction = call(
            "POST",
            f"/v1/submissions/{paper['id']}/extractions",
            json={
                "base_version": 0,
                "pages_complete": True,
                "identity_confirmed": True,
                "answers": [
                    {
                        "question_id": rubric["questions"][0]["id"],
                        "text": answer,
                        "page_from": 1,
                        "page_to": 1,
                        "readable": True,
                    }
                ],
            },
        )
        marks = [
            {"criterion_id": c["id"], "mark": "4" if index == 0 else "2"}
            for c in rubric["questions"][0]["criteria"]
        ]
        feedback = (
            "Correct ordering. Add a concrete push/pop example."
            if index == 0
            else "You describe the order. Name LIFO explicitly and add an example."
        )
        question_review = call(
            "POST",
            f"/v1/submissions/{paper['id']}/questions/{rubric['questions'][0]['id']}/reviews",
            json={
                "rubric_id": rubric["id"],
                "extraction_id": extraction["id"],
                "marks": marks,
                "feedback": feedback,
            },
        )
        call(
            "POST",
            f"/v1/submissions/{paper['id']}/calibrations",
            json={
                "rubric_id": rubric["id"],
                "extraction_id": extraction["id"],
                "band": "high" if index == 0 else "middle",
                "note": "Synthetic teacher reference; demonstrates explicit calibration selection.",
                "marks": marks,
            },
        )
        if index == 0:
            decision = call(
                "POST",
                f"/v1/submissions/{paper['id']}/decisions",
                json={
                    "extraction_id": extraction["id"],
                    "question_review_ids": [question_review["id"]],
                    "marks": marks,
                    "feedback": feedback,
                    "reason": "Synthetic demo marked manually against both criteria.",
                },
            )
            call(
                "POST",
                f"/v1/submissions/{paper['id']}/release",
                json={"decision_id": decision["id"]},
            )
    revised = rubric["questions"]
    revised[0]["criteria"][0]["guidance"] = (
        "Credit a clear description even when the acronym is missing."
    )
    call(
        "POST",
        f"/v1/assessments/{assessment['id']}/rubrics",
        json={
            "base_version": rubric["version"],
            "reason": "Clarify partial credit for correct descriptions without the LIFO acronym.",
            "questions": revised,
        },
    )
    Path(".tmp/review-demo.json").write_text(
        json.dumps(
            {
                "classroom_id": classroom["id"],
                "assessment_id": assessment["id"],
                "papers": [p["id"] for p in papers],
            }
        ),
        encoding="utf-8",
    )
print("Synthetic review demo is ready in the existing demo classroom.")
