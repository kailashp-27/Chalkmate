"""Seed a clearly labeled, manual Phase 5 walkthrough in the generated local demo only."""

import json
from pathlib import Path
from urllib.parse import urlparse

import httpx

from chalkmate.config import get_settings

settings = get_settings()
if settings.app_env != "development" or urlparse(settings.supabase_url).hostname not in {
    "127.0.0.1",
    "localhost",
}:
    raise RuntimeError("Local synthetic demo only")
credentials = json.loads(Path(".tmp/demo-credentials.json").read_text(encoding="utf-8"))
if not credentials["email"].startswith("teacher.demo.") or not credentials["email"].endswith(
    "@example.com"
):
    raise RuntimeError("Only the generated demo account may be seeded")
previous = json.loads(Path(".tmp/review-demo.json").read_text(encoding="utf-8"))
login = httpx.post(
    settings.supabase_url + "/auth/v1/token?grant_type=password",
    headers={"apikey": settings.supabase_anon_key},
    json=credentials,
    timeout=30,
)
login.raise_for_status()
with httpx.Client(
    base_url="http://127.0.0.1:8100",
    headers={"Authorization": "Bearer " + login.json()["access_token"]},
    timeout=30,
) as client:

    def call(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    aid = previous["assessment_id"]
    if any(
        r["request"].get("topic") == "Demo · Stack ordering"
        for r in call("GET", f"/v1/assessments/{aid}/intelligence-runs")
    ):
        print("Teaching demo already exists; preserved existing work.")
        raise SystemExit(0)
    summary = call("GET", f"/v1/assessments/{aid}/topic-summary")
    topic = next((q for q in summary["topics"] if q["analyzable"]), None)
    if not topic:
        print("Demo has no currently approved readable sources; existing work was preserved.")
        raise SystemExit(0)
    request = {"question_id": topic["question_id"], "topic": "Demo · Stack ordering"}
    sources = call("POST", f"/v1/assessments/{aid}/evidence-preview", json=request)
    source = sources[0]
    result = {
        "findings": [
            {
                "title": "Demo · Connect ordering to a concrete trace",
                "kind": "needs_practice",
                "explanation": "Synthetic example: plan a concrete stack exercise.",
                "citations": [
                    {
                        "source_id": source["source_id"],
                        "quote": source["text"][:180],
                        "page": source["page_from"],
                    }
                ],
                "suggested_action": "Trace two pushes and two pops, explaining the ordering.",
            }
        ],
        "limitations": "Manually authored synthetic demo, not an AI conclusion or diagnosis.",
    }
    run = call(
        "POST",
        f"/v1/assessments/{aid}/intelligence-runs",
        json={**request, "manual_result": result},
    )
    reviewed = call(
        "POST",
        f"/v1/intelligence-runs/{run['id']}/findings/0/reviews",
        json={
            "base_version": 0,
            "disposition": "accepted",
            "reason": "Synthetic demo: checked pinned source and rubric.",
        },
    )
    content = {
        "title": "Demo · Stack revision pack",
        "introduction": "Review LIFO, then explain each operation in your own words.",
        "objectives": [
            "Trace push and pop operations.",
            "Explain why the newest item leaves first.",
        ],
        "revision_notes": [
            "A stack uses last in, first out (LIFO).",
            "Push adds an item to the top; pop removes the top item.",
        ],
        "items": [
            {
                "question": "Push A then B. What does the next pop return? Explain why.",
                "hint": "Which item was added most recently?",
                "answer": "B is returned because it is on top. A remains in the stack.",
                "rationale": "Connect the acronym to an explicit sequence of operations.",
            },
            {
                "question": "After pushing A, B and C, pop twice. What remains?",
                "hint": "Trace the top item after each operation.",
                "answer": "The first pop removes C and the second removes B. A remains.",
                "rationale": "Practice maintaining stack state across several operations.",
            },
        ],
    }
    material = call(
        "POST",
        f"/v1/assessments/{aid}/teaching-material",
        json={
            "source_run_id": run["id"],
            "review_ids": [reviewed["id"]],
            "material_type": "revision",
            "manual_content": content,
        },
    )
    Path(".tmp/intelligence-demo.json").write_text(
        json.dumps(
            {
                "classroom_id": previous["classroom_id"],
                "assessment_id": aid,
                "analysis_run_id": run["id"],
                "material_run_id": material["id"],
            }
        ),
        encoding="utf-8",
    )
print("Synthetic teaching walkthrough ready. Material remains unapproved and unpublished.")
