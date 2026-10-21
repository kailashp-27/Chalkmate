"""Authoritative score eligibility, snapshot comparison, and private personalization."""

import hashlib
import json
from decimal import Decimal
from string import Formatter
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text

from chalkmate import assessment_models as grades
from chalkmate import followup_models as m
from chalkmate import models as core
from chalkmate.assessment_rules import latest
from chalkmate.config import get_settings


def compare_score(total, operator, threshold):
    a, b = Decimal(str(total)), Decimal(str(threshold))
    return {"lt": a < b, "lte": a <= b, "eq": a == b, "gte": a >= b, "gt": a > b}[operator]


def latest_published(db, assignment_id):
    return db.scalar(
        select(m.AssignmentVersion)
        .where(
            m.AssignmentVersion.assignment_id == assignment_id,
            m.AssignmentVersion.published_at.is_not(None),
        )
        .order_by(m.AssignmentVersion.version.desc())
        .limit(1)
    )


def active_student(db, classroom_id, actor_id):
    return db.scalar(
        select(core.Student)
        .join(core.Enrollment, core.Enrollment.student_id == core.Student.id)
        .where(
            core.Enrollment.classroom_id == classroom_id,
            core.Enrollment.status == "active",
            core.Student.user_id == actor_id,
        )
    )


def staff(db, classroom_id, edit=False):
    return bool(
        db.scalar(text("SELECT chalkmate.staff(:id,:edit)"), {"id": classroom_id, "edit": edit})
    )


def in_audience(db, version_id, student_id):
    return bool(
        db.scalar(
            select(m.AssignmentAudience.id).where(
                m.AssignmentAudience.assignment_version_id == version_id,
                m.AssignmentAudience.student_id == student_id,
            )
        )
    )


def response_for(db, version_id, student_id):
    return db.scalar(
        select(m.AssignmentResponse)
        .where(
            m.AssignmentResponse.assignment_version_id == version_id,
            m.AssignmentResponse.student_id == student_id,
        )
        .order_by(m.AssignmentResponse.version.desc())
        .limit(1)
    )


def snapshot_digest(snapshot):
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_template(subject, body, include_score):
    allowed = {"student_name", "assignment_title", "assignment_link"}
    if include_score:
        allowed |= {"score", "maximum"}
    if any(c in subject for c in "\r\n"):
        raise HTTPException(422, "Use a single-line subject")
    try:
        for value in [subject, body]:
            for _, field, spec, conversion in Formatter().parse(value):
                if field is not None and (field not in allowed or spec or conversion):
                    raise ValueError("Unsupported placeholder")
    except ValueError as exc:
        raise HTTPException(
            422,
            "Use only student_name, assignment_title, assignment_link, and "
            "opt-in score/maximum placeholders",
        ) from exc


def build_snapshot(db, classroom_id, request):
    version = db.get(m.AssignmentVersion, request.assignment_version_id)
    if not version or version.classroom_id != classroom_id or not version.published_at:
        raise HTTPException(409, "Choose a published assignment from this classroom")
    assignment = db.get(m.Assignment, version.assignment_id)
    published = latest_published(db, assignment.id)
    if assignment.closed or not published or published.id != version.id:
        raise HTTPException(409, "Choose the current open assignment publication")
    assessment = db.get(grades.Assessment, request.rule.assessment_id)
    if not assessment or assessment.classroom_id != classroom_id:
        raise HTTPException(404, "Assessment not found")
    validate_template(request.subject, request.body, request.include_score)
    excluded = set(request.exclude_student_ids)
    rows = []
    for student, enrollment in db.execute(
        select(core.Student, core.Enrollment)
        .join(core.Enrollment, core.Enrollment.student_id == core.Student.id)
        .where(core.Enrollment.classroom_id == classroom_id)
        .order_by(core.Student.registration_number)
    ):
        paper = db.scalar(
            select(grades.Submission).where(
                grades.Submission.assessment_id == assessment.id,
                grades.Submission.student_id == student.id,
            )
        )
        decision = latest(db, grades.Decision, paper.id) if paper else None
        row = {
            "student_id": str(student.id),
            "student_name": student.name,
            "registration_number": student.registration_number,
            "email": student.email,
            "user_id": str(student.user_id) if student.user_id else None,
            "decision_id": str(decision.id) if decision else None,
            "total": str(decision.total) if decision else None,
            "maximum": str(decision.maximum) if decision else None,
            "rubric_id": str(decision.rubric_id) if decision else None,
            "extraction_id": str(decision.extraction_id) if decision else None,
            "eligible": False,
            "excluded": student.id in excluded,
            "blocked": False,
            "reason": "",
        }
        if enrollment.status != "active":
            row["reason"] = "Withdrawn student"
        elif not paper:
            row["reason"] = "Missing assessment submission"
        elif (
            paper.status not in ("approved", "released")
            or not decision
            or decision.rubric_id != paper.rubric_id
        ):
            row["reason"] = "Unapproved or re-evaluation in progress"
        elif decision.maximum != request.rule.maximum:
            row["reason"] = "Different assessment maximum"
        elif not compare_score(decision.total, request.rule.operator, request.rule.threshold):
            row["reason"] = "Score does not match the rule"
        elif request.skip_submitted and response_for(db, version.id, student.id):
            row["reason"] = "Assignment already submitted"
        else:
            row["eligible"] = True
            if not student.email:
                row["blocked"], row["reason"] = True, "Missing email address"
            elif not student.user_id:
                row["blocked"], row["reason"] = (
                    True,
                    "Link the student's verified portal account first",
                )
            elif db.scalar(text("SELECT chalkmate.contact_suppressed(:id)"), {"id": student.id}):
                row["blocked"], row["reason"] = True, "Address has a confirmed bounce or complaint"
            elif not db.scalar(text("SELECT chalkmate.contact_ready(:id)"), {"id": student.id}):
                row["blocked"], row["reason"] = True, "Contact must match the linked portal account"
            elif not in_audience(db, version.id, student.id):
                row["blocked"], row["reason"] = (
                    True,
                    "Student is outside the published assignment audience",
                )
            elif request.include_score and not db.scalar(
                select(grades.Release.id).where(
                    grades.Release.submission_id == paper.id,
                    grades.Release.decision_id == decision.id,
                )
            ):
                row["blocked"], row["reason"] = (
                    True,
                    "Release this score before including it in email",
                )
            elif row["excluded"]:
                row["reason"] = "Explicitly excluded from this preview"
            else:
                row["reason"] = "Eligible"
        rows.append(row)
    known = {UUID(row["student_id"]) for row in rows}
    if not excluded <= known or len(excluded) != len(request.exclude_student_ids):
        raise HTTPException(422, "Exclude each student from this classroom at most once")
    return {
        "sender": get_settings().mail_from,
        "web_origin": get_settings().web_origin,
        "provider": get_settings().mail_provider,
        "assignment_title": version.title,
        "assignment_version": version.version,
        "rows": rows,
        "eligible_count": sum(row["eligible"] for row in rows),
        "selected_count": sum(row["eligible"] and not row["excluded"] for row in rows),
        "blocked_count": sum(
            row["eligible"] and row["blocked"] and not row["excluded"] for row in rows
        ),
    }


def personal_message(version_id, request, snapshot, row):
    link = f"{snapshot['web_origin'].rstrip('/')}/assignments/{version_id}"
    values = {
        "student_name": row["student_name"],
        "assignment_title": snapshot["assignment_title"],
        "assignment_link": link,
    }
    if request.include_score:
        values.update(score=row["total"], maximum=row["maximum"])
    subject, body = request.subject.format_map(values), request.body.format_map(values)
    if request.include_score and "{score}" not in request.body:
        body += f"\n\nYour approved score: {row['total']} / {row['maximum']}"
    # Always supply the protected link, even if the teacher omitted its placeholder.
    if link not in body:
        body += f"\n\nOpen your assignment (sign in required): {link}"
    return {
        "from": snapshot["sender"],
        "to": row["email"],
        "subject": subject.replace("\r", " ").replace("\n", " "),
        "text": body,
    }


def revalidate_delivery(db, campaign, delivery):
    from chalkmate.followup_schemas import PreviewInput

    request = PreviewInput.model_validate(campaign.request)
    if campaign.canceled:
        return "canceled", "Campaign canceled"
    classroom = db.get(core.Classroom, campaign.classroom_id)
    if not classroom or classroom.archived or not staff(db, campaign.classroom_id, edit=True):
        return "held", "Teaching access changed or classroom archived"
    try:
        current = build_snapshot(db, campaign.classroom_id, request)
    except HTTPException:
        return "held", "Assignment publication or assessment access changed"
    row = next((r for r in current["rows"] if r["student_id"] == str(delivery.student_id)), None)
    if not row:
        return "held", "Enrollment changed"
    if not row["eligible"]:
        return (
            "skipped"
            if row["reason"]
            in (
                "Withdrawn student",
                "Assignment already submitted",
                "Score does not match the rule",
            )
            else "held"
        ), row["reason"]
    for key in [
        "email",
        "user_id",
        "student_name",
        "decision_id",
        "total",
        "maximum",
        "rubric_id",
        "extraction_id",
    ]:
        if row[key] != delivery.snapshot[key]:
            return "held", "Contact, identity, or score version changed; create a fresh preview"
    if row["blocked"]:
        return "held", row["reason"]
    return None, ""
