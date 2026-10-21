"""Deterministic cohort summaries, immutable evidence and strict citation validation."""

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select

from chalkmate import assessment_models as grades
from chalkmate import intelligence_models as m
from chalkmate import models as core
from chalkmate.assessment_routes import rubric_for
from chalkmate.assessment_rules import latest
from chalkmate.intelligence_schemas import (
    AnalysisInput,
    AnalysisResult,
    GenerateInput,
    MaterialContent,
)

PROMPT_VERSION = "teaching-evidence-v1"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def cohort(db, assessment):
    rubric = rubric_for(db, assessment)
    rows = []
    for student, enrollment in db.execute(
        select(core.Student, core.Enrollment)
        .join(core.Enrollment, core.Enrollment.student_id == core.Student.id)
        .where(core.Enrollment.classroom_id == assessment.classroom_id)
        .order_by(core.Student.registration_number)
    ):
        row = {
            "student": student,
            "disposition": "reviewed",
            "paper": None,
            "decision": None,
            "extraction": None,
        }
        paper = db.scalar(
            select(grades.Submission).where(
                grades.Submission.assessment_id == assessment.id,
                grades.Submission.student_id == student.id,
            )
        )
        decision = latest(db, grades.Decision, paper.id) if paper else None
        extraction = latest(db, grades.Extraction, paper.id) if paper else None
        row.update(paper=paper, decision=decision, extraction=extraction)
        if enrollment.status != "active":
            row["disposition"] = "withdrawn"
        elif not paper:
            row["disposition"] = "missing"
        elif not rubric or paper.rubric_id != rubric.id:
            row["disposition"] = "rubric_mismatch"
        elif (
            paper.status not in ("approved", "released")
            or not decision
            or not extraction
            or not extraction.reviewed_by
            or decision.extraction_id != extraction.id
            or decision.rubric_id != rubric.id
        ):
            row["disposition"] = "unapproved"
        rows.append(row)
    return rubric, rows


def question_data(row, question):
    answer = next(
        (a for a in row["extraction"].answers if a["question_id"] == question["id"]), None
    )
    criteria = {c["id"] for c in question["criteria"]}
    mark = sum(
        (Decimal(str(c["mark"])) for c in row["decision"].marks if c["criterion_id"] in criteria),
        Decimal(0),
    )
    return answer, mark


def summary(db, assessment):
    rubric, rows = cohort(db, assessment)
    counts = {
        key: sum(r["disposition"] == key for r in rows)
        for key in ["missing", "withdrawn", "unapproved", "rubric_mismatch"]
    }
    topics = []
    for q in rubric.questions if rubric else []:
        reviewed = [question_data(r, q) for r in rows if r["disposition"] == "reviewed"]
        maximum = Decimal(str(q["maximum"]))
        marks = [mark for _, mark in reviewed]
        topics.append(
            {
                "question_id": q["id"],
                "label": q["label"],
                "prompt": q["prompt"],
                "maximum": maximum,
                "reviewed": len(reviewed),
                "analyzable": sum(
                    bool(a and a["readable"] and a["text"].strip()) for a, _ in reviewed
                ),
                "unreadable": sum(not a or not a["readable"] for a, _ in reviewed),
                "blank": sum(
                    bool(a and a["readable"] and not a["text"].strip()) for a, _ in reviewed
                ),
                "full_credit": sum(mark == maximum for mark in marks),
                "partial_credit": sum(0 < mark < maximum for mark in marks),
                "zero_credit": sum(mark == 0 for mark in marks),
                "average": (sum(marks) / len(marks)).quantize(
                    Decimal(".01"), rounding=ROUND_HALF_UP
                )
                if marks
                else None,
            }
        )
    return {
        "assessment_id": assessment.id,
        "rubric_id": rubric.id if rubric else None,
        "rubric_version": rubric.version if rubric else None,
        "active_students": sum(r["disposition"] != "withdrawn" for r in rows),
        "topics": topics,
        **counts,
    }


def analysis_snapshot(db, assessment, request):
    rubric, rows = cohort(db, assessment)
    question = (
        next((q for q in rubric.questions if q["id"] == str(request.question_id)), None)
        if rubric
        else None
    )
    if not question:
        raise HTTPException(409, "Choose a question from the current approved rubric")
    ids = set(request.student_ids) if request.student_ids is not None else None
    if ids is not None and (
        not ids
        or len(ids) != len(request.student_ids)
        or not ids <= {r["student"].id for r in rows}
    ):
        raise HTTPException(422, "Choose students from this classroom once each")
    sources = []
    dispositions = []
    for row in rows:
        student = row["student"]
        if ids is not None and student.id not in ids:
            continue
        disposition = row["disposition"]
        if disposition == "reviewed":
            answer, mark = question_data(row, question)
            if not answer or not answer["readable"]:
                disposition = "unreadable"
            elif not answer["text"].strip():
                disposition = "blank"
            else:
                sources.append(
                    {
                        "source_id": f"S{len(sources) + 1}",
                        "student_id": str(student.id),
                        "student_name": student.name,
                        "submission_id": str(row["paper"].id),
                        "decision_id": str(row["decision"].id),
                        "extraction_id": str(row["extraction"].id),
                        "text": answer["text"],
                        "page_from": answer["page_from"],
                        "page_to": answer["page_to"],
                        "mark": str(mark),
                        "maximum": str(question["maximum"]),
                    }
                )
        dispositions.append({"student_id": str(student.id), "disposition": disposition})
    if not sources:
        raise HTTPException(
            409, "No readable, nonblank, currently approved answers for this question"
        )
    if len(sources) > 30:
        raise HTTPException(
            422,
            "Choose at most 30 students for analysis; automatic sampling is disabled",
        )
    value = {
        "topic": request.topic,
        "rubric_id": str(rubric.id),
        "rubric_version": rubric.version,
        "question": question,
        "sources": sources,
        "dispositions": dispositions,
    }
    # Names are for the teacher's evidence panel; do not send identity fields to the model.
    if len(json.dumps(model_evidence(value))) > 16000:
        raise HTTPException(
            422,
            "Answers exceed the local context budget; choose a smaller explicit subset",
        )
    return value


def model_evidence(snapshot):
    return {
        "topic": snapshot["topic"],
        "question": snapshot["question"],
        "answers": [
            {k: s[k] for k in ["source_id", "text", "page_from", "page_to", "mark", "maximum"]}
            for s in snapshot["sources"]
        ],
    }


def validate_analysis(output, snapshot):
    result = AnalysisResult.model_validate(output)
    sources = {s["source_id"]: s for s in snapshot["sources"]}
    titles = set()
    for finding in result.findings:
        if finding.title.casefold() in titles:
            raise ValueError("Duplicate finding title")
        titles.add(finding.title.casefold())
        seen = set()
        for citation in finding.citations:
            source = sources.get(citation.source_id)
            if (
                not source
                or citation.quote not in source["text"]
                or not source["page_from"] <= citation.page <= source["page_to"]
            ):
                raise ValueError("Evidence must cite an exact reviewed substring and mapped page")
            if citation.source_id in seen:
                raise ValueError("Cite each source once per finding")
            seen.add(citation.source_id)
    return result.model_dump(mode="json")


def current_review(db, run_id, index):
    return db.scalar(
        select(m.FindingReview)
        .where(m.FindingReview.run_id == run_id, m.FindingReview.finding_index == index)
        .order_by(m.FindingReview.version.desc())
        .limit(1)
    )


def material_snapshot(db, assessment, request):
    source = db.get(m.IntelligenceRun, request.source_run_id)
    if (
        not source
        or source.assessment_id != assessment.id
        or source.kind != "analysis"
        or source.status != "succeeded"
    ):
        raise HTTPException(409, "Choose completed findings from this assessment")
    stale, reason = staleness(db, source)
    if stale:
        raise HTTPException(409, reason)
    if len(set(request.review_ids)) != len(request.review_ids):
        raise HTTPException(422, "Choose each accepted finding once")
    findings = []
    for review_id in request.review_ids:
        review = db.get(m.FindingReview, review_id)
        if (
            not review
            or review.run_id != source.id
            or review.disposition != "accepted"
            or current_review(db, source.id, review.finding_index).id != review.id
        ):
            raise HTTPException(409, "Choose the current accepted review of each finding")
        finding = source.result["findings"][review.finding_index]
        # Keep source citations, identities and marks in the private evidence view.
        findings.append(
            {
                "review_id": str(review.id),
                "title": finding["title"],
                "explanation": finding["explanation"],
                "suggested_action": finding["suggested_action"],
            }
        )
    return {
        "source_run_id": str(source.id),
        "source_digest": source.input_digest,
        "topic": source.snapshot["topic"],
        "question": source.snapshot["question"],
        "findings": findings,
        "material_type": request.material_type,
        "guidance": request.guidance,
    }


def staleness(db, run):
    assessment = db.get(grades.Assessment, run.assessment_id)
    classroom = db.get(core.Classroom, run.classroom_id)
    if not assessment or not classroom or classroom.archived:
        return True, "Classroom archived or teaching access changed"
    try:
        snapshot = (
            analysis_snapshot(db, assessment, AnalysisInput.model_validate(run.request))
            if run.kind == "analysis"
            else material_snapshot(db, assessment, GenerateInput.model_validate(run.request))
        )
    except HTTPException as exc:
        return True, str(exc.detail)
    return (
        (False, "")
        if digest(snapshot) == run.input_digest
        else (
            True,
            "Reviewed sources or finding review changed; create a fresh run",
        )
    )


def validate_material(output, snapshot):
    content = MaterialContent.model_validate(output)
    if snapshot["material_type"] == "revision" and not content.revision_notes:
        raise ValueError("Revision packs require revision notes")
    value = content.model_dump(mode="json")
    if len(student_material(value)) > 20000:
        raise ValueError("Student material exceeds the assignment size limit; shorten it")
    return value


def student_material(content):
    parts = [content["introduction"], "Learning goals", *[f"- {x}" for x in content["objectives"]]]
    if content["revision_notes"]:
        parts += ["Revision notes", *content["revision_notes"]]
    for i, item in enumerate(content["items"], 1):
        parts += [f"{i}. {item['question']}"]
        if item["hint"]:
            parts += [f"Hint: {item['hint']}"]
    return "\n\n".join(parts)


def export_material(content, teacher=False):
    value = f"# {content['title']}\n\n" + student_material(content)
    if teacher:
        value += "\n\n## Teacher answer key — keep private\n"
        for i, item in enumerate(content["items"], 1):
            value += f"\n### {i}\n{item['answer']}\n\nTeacher rationale: {item['rationale']}\n"
    return value + "\n"
