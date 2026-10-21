"""Assignment publication and private student responses."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy import text as sql_text

from chalkmate import followup_models as m
from chalkmate import followup_schemas as s
from chalkmate import models as core
from chalkmate.auth import CurrentUser, Database
from chalkmate.config import get_settings
from chalkmate.followup_rules import (
    active_student,
    in_audience,
    response_for,
    staff,
)
from chalkmate.routes import audit, classroom
from chalkmate.storage import MAX_FILE_BYTES, storage_request, validate_file

router = APIRouter(prefix="/v1")


def assignment(db, assignment_id, edit=False):
    record = db.get(m.Assignment, assignment_id)
    if not record:
        raise HTTPException(404, "Assignment not found")
    classroom(db, record.classroom_id, edit=edit, staff=edit, active=edit)
    if edit:
        db.execute(select(m.Assignment.id).where(m.Assignment.id == record.id).with_for_update())
        db.refresh(record)
    return record


def version_record(db, version_id):
    version = db.get(m.AssignmentVersion, version_id)
    if not version:
        raise HTTPException(404, "Assignment publication not found")
    return version


def assignment_output(db, record, user, version=None):
    is_staff = staff(db, record.classroom_id)
    can_edit = staff(db, record.classroom_id, edit=True)
    pupil = active_student(db, record.classroom_id, user.id) if not is_staff else None
    versions = list(
        db.scalars(
            select(m.AssignmentVersion)
            .where(m.AssignmentVersion.assignment_id == record.id)
            .order_by(m.AssignmentVersion.version.desc())
        )
    )
    published = next(
        (
            v
            for v in versions
            if v.published_at and (is_staff or (pupil and in_audience(db, v.id, pupil.id)))
        ),
        None,
    )
    chosen = version or published or (versions[0] if is_staff and versions else None)
    if not chosen:
        raise HTTPException(404, "Assignment not found")
    current_id = db.scalar(sql_text("SELECT chalkmate.assignment_current(:id)"), {"id": record.id})
    current_response = response_for(db, chosen.id, pupil.id) if pupil else None
    class_record = db.get(core.Classroom, record.classroom_id)
    return {
        "id": record.id,
        "classroom_id": record.classroom_id,
        "closed": record.closed,
        "version": s.AssignmentVersionOutput.model_validate(chosen).model_copy(
            update={"reason": chosen.reason if is_staff else ""}
        ),
        "draft": versions[0] if is_staff and versions and not versions[0].published_at else None,
        "audience_count": db.scalar(
            select(func.count())
            .select_from(m.AssignmentAudience)
            .where(m.AssignmentAudience.assignment_version_id == chosen.id)
        )
        or 0
        if is_staff
        else 0,
        "response_count": db.scalar(
            select(func.count(func.distinct(m.AssignmentResponse.student_id))).where(
                m.AssignmentResponse.assignment_version_id == chosen.id
            )
        )
        or 0
        if is_staff
        else int(current_response is not None),
        "own_response_version": current_response.version if current_response else 0,
        "can_edit": can_edit and not class_record.archived,
        "is_staff": is_staff,
        "can_submit": bool(
            pupil
            and chosen.published_at
            and current_id == chosen.id
            and in_audience(db, chosen.id, pupil.id)
            and not record.closed
            and not class_record.archived
        ),
    }


@router.get("/classrooms/{classroom_id}/assignments", response_model=list[s.AssignmentOutput])
def list_assignments(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id, staff=False)
    return [
        assignment_output(db, record, user)
        for record in db.scalars(
            select(m.Assignment)
            .where(m.Assignment.classroom_id == classroom_id)
            .order_by(m.Assignment.created_at.desc())
        )
    ]


@router.post(
    "/classrooms/{classroom_id}/assignments", response_model=s.AssignmentOutput, status_code=201
)
def create_assignment(classroom_id: UUID, body: s.AssignmentInput, db: Database, user: CurrentUser):
    parent = classroom(db, classroom_id, edit=True, active=True)
    if body.base_version:
        raise HTTPException(409, "A new assignment starts at version zero")
    record = m.Assignment(
        workspace_id=parent.workspace_id, classroom_id=parent.id, created_by=user.id
    )
    db.add(record)
    db.flush()
    version = m.AssignmentVersion(
        workspace_id=parent.workspace_id,
        classroom_id=parent.id,
        assignment_id=record.id,
        version=1,
        **body.model_dump(exclude={"base_version"}),
    )
    db.add(version)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "assignment.created",
        record.classroom_id,
        assignment_id=str(record.id),
    )
    return assignment_output(db, record, user)


@router.post(
    "/assignments/{assignment_id}/versions", response_model=s.AssignmentOutput, status_code=201
)
def revise_assignment(
    assignment_id: UUID, body: s.AssignmentInput, db: Database, user: CurrentUser
):
    record = assignment(db, assignment_id, edit=True)
    previous = db.scalar(
        select(m.AssignmentVersion)
        .where(m.AssignmentVersion.assignment_id == record.id)
        .order_by(m.AssignmentVersion.version.desc())
        .limit(1)
    )
    if body.base_version != previous.version:
        raise HTTPException(409, "Assignment changed. Refresh before revising.")
    if len(body.reason.strip()) < 3:
        raise HTTPException(422, "Explain the assignment revision")
    db.add(
        m.AssignmentVersion(
            workspace_id=record.workspace_id,
            classroom_id=record.classroom_id,
            assignment_id=record.id,
            version=previous.version + 1,
            **body.model_dump(exclude={"base_version"}),
        )
    )
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "assignment.revised",
        record.classroom_id,
        assignment_id=str(record.id),
    )
    return assignment_output(db, record, user)


@router.get("/assignments/{assignment_id}/versions", response_model=list[s.AssignmentVersionOutput])
def assignment_history(assignment_id: UUID, db: Database, user: CurrentUser):
    record = assignment(db, assignment_id)
    classroom(db, record.classroom_id)
    return list(
        db.scalars(
            select(m.AssignmentVersion)
            .where(m.AssignmentVersion.assignment_id == record.id)
            .order_by(m.AssignmentVersion.version.desc())
        )
    )


@router.post("/assignment-versions/{version_id}/publish", response_model=s.AssignmentOutput)
def publish_assignment(
    version_id: UUID, body: s.PublishAssignment, db: Database, user: CurrentUser
):
    version = version_record(db, version_id)
    record = assignment(db, version.assignment_id, edit=True)
    if record.closed:
        raise HTTPException(409, "Reopen this assignment before publishing")
    newest = db.scalar(
        select(m.AssignmentVersion)
        .where(m.AssignmentVersion.assignment_id == record.id)
        .order_by(m.AssignmentVersion.version.desc())
        .limit(1)
    )
    if version.id != newest.id or version.published_at:
        raise HTTPException(409, "Publish the latest unpublished version")
    students = list(
        db.scalars(
            select(core.Enrollment.student_id).where(
                core.Enrollment.classroom_id == record.classroom_id,
                core.Enrollment.status == "active",
            )
        )
    )
    chosen = body.student_ids if body.student_ids is not None else students
    if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(students):
        raise HTTPException(422, "Choose active students from this classroom once each")
    for student_id in chosen:
        db.add(
            m.AssignmentAudience(
                workspace_id=record.workspace_id,
                classroom_id=record.classroom_id,
                assignment_version_id=version.id,
                student_id=student_id,
            )
        )
    version.published_at = datetime.now(UTC)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "assignment.published",
        record.classroom_id,
        assignment_version_id=str(version.id),
        audience=len(chosen),
    )
    return assignment_output(db, record, user)


@router.patch("/assignments/{assignment_id}", response_model=s.AssignmentOutput)
def assignment_state(assignment_id: UUID, body: s.AssignmentState, db: Database, user: CurrentUser):
    record = assignment(db, assignment_id, edit=True)
    record.closed = body.closed
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "assignment.closed" if body.closed else "assignment.reopened",
        record.classroom_id,
        assignment_id=str(record.id),
    )
    return assignment_output(db, record, user)


@router.get("/assignment-versions/{version_id}", response_model=s.AssignmentOutput)
def get_assignment_version(version_id: UUID, db: Database, user: CurrentUser):
    version = version_record(db, version_id)
    return assignment_output(db, assignment(db, version.assignment_id), user, version)


def response_output(db, record):
    student = db.get(core.Student, record.student_id)
    return {
        **{
            key: getattr(record, key)
            for key in [
                "id",
                "assignment_version_id",
                "student_id",
                "version",
                "text",
                "filename",
                "content_type",
                "late",
                "created_at",
            ]
        },
        "student_name": student.name,
    }


@router.get("/assignment-versions/{version_id}/responses", response_model=list[s.ResponseOutput])
def list_responses(version_id: UUID, db: Database, user: CurrentUser):
    version_record(db, version_id)
    return [
        response_output(db, record)
        for record in db.scalars(
            select(m.AssignmentResponse)
            .where(m.AssignmentResponse.assignment_version_id == version_id)
            .order_by(m.AssignmentResponse.created_at.desc())
        )
    ]


@router.post(
    "/assignment-versions/{version_id}/responses", response_model=s.ResponseOutput, status_code=201
)
def submit_response(
    version_id: UUID,
    db: Database,
    user: CurrentUser,
    base_version: int = Form(ge=0),
    text: str = Form(default="", max_length=20000),
    file: UploadFile | None = File(default=None),
):
    version = version_record(db, version_id)
    parent = assignment(db, version.assignment_id)
    pupil = active_student(db, version.classroom_id, user.id)
    class_record = db.get(core.Classroom, parent.classroom_id)
    current_id = db.scalar(sql_text("SELECT chalkmate.assignment_current(:id)"), {"id": parent.id})
    if not pupil or not in_audience(db, version.id, pupil.id):
        raise HTTPException(403, "Only the assigned student can submit a response")
    if parent.closed or class_record.archived or current_id != version.id:
        raise HTTPException(409, "This assignment publication no longer accepts submissions")
    previous = response_for(db, version.id, pupil.id)
    if base_version != (previous.version if previous else 0):
        raise HTTPException(409, "Your response changed. Refresh before submitting again.")
    if not text.strip() and not file:
        raise HTTPException(422, "Write a response or attach a file")
    path, filename, kind = None, None, None
    if file:
        data = file.file.read(MAX_FILE_BYTES + 1)
        filename = Path(file.filename or "").name[:180]
        kind = validate_file(filename, data)
        path = (
            f"assignment-responses/{parent.classroom_id}/{version.id}/"
            f"{pupil.id}/{uuid4()}{Path(filename).suffix.lower()}"
        )
        storage_request(
            "POST",
            f"object/{get_settings().storage_bucket}/{path}",
            content=data,
            headers={"Content-Type": kind, "x-upsert": "false"},
        )
    response = m.AssignmentResponse(
        workspace_id=parent.workspace_id,
        classroom_id=parent.classroom_id,
        assignment_version_id=version.id,
        student_id=pupil.id,
        version=base_version + 1,
        text=text.strip(),
        file_path=path,
        filename=filename,
        content_type=kind,
        late=bool(version.due_at and datetime.now(UTC) > version.due_at),
    )
    db.add(response)
    db.flush()
    # Student audit insertion is restricted to this narrow action by the migration.
    audit(
        db,
        user,
        parent.workspace_id,
        "assignment.responded",
        parent.classroom_id,
        assignment_version_id=str(version.id),
        response_id=str(response.id),
        version=response.version,
    )
    return response_output(db, response)


@router.get("/assignment-responses/{response_id}/download")
def download_response(response_id: UUID, db: Database, user: CurrentUser):
    record = db.get(m.AssignmentResponse, response_id)
    if not record or not record.file_path:
        raise HTTPException(404, "Response file not found")
    result = storage_request(
        "POST",
        f"object/sign/{get_settings().storage_bucket}/{record.file_path}",
        json={"expiresIn": 60},
    ).json()
    return {"url": f"{get_settings().supabase_url}/storage/v1{result['signedURL']}"}


@router.patch("/classrooms/{classroom_id}/students/{student_id}/contact")
def update_contact(
    classroom_id: UUID, student_id: UUID, body: s.ContactInput, db: Database, user: CurrentUser
):
    parent = classroom(db, classroom_id, edit=True, active=True)
    student = db.get(core.Student, student_id)
    enrollment = db.scalar(
        select(core.Enrollment.id).where(
            core.Enrollment.classroom_id == classroom_id, core.Enrollment.student_id == student_id
        )
    )
    if not student or not enrollment:
        raise HTTPException(404, "Student not found")
    if not db.scalar(
        sql_text("SELECT chalkmate.set_student_contact(:cid,:sid,:email)"),
        {
            "cid": classroom_id,
            "sid": student_id,
            "email": str(body.email).lower() if body.email else None,
        },
    ):
        raise HTTPException(403, "Contact change is not allowed")
    audit(
        db,
        user,
        parent.workspace_id,
        "student.contact_changed",
        parent.id,
        student_id=str(student.id),
    )
    return {"updated": True}
