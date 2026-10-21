import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from chalkmate import models as m
from chalkmate import schemas as s
from chalkmate.auth import CurrentUser, Database
from chalkmate.config import get_settings
from chalkmate.rosters import MAX_ROSTER_BYTES, parse_roster
from chalkmate.storage import MAX_FILE_BYTES, storage_request, validate_file

router = APIRouter(prefix="/v1")


def audit(db, user, workspace, action, classroom=None, **details):
    db.add(
        m.AuditEvent(
            workspace_id=workspace,
            classroom_id=classroom,
            actor_id=user.id,
            action=action,
            details=details,
        )
    )


def workspace_member(db, workspace_id, user, teaching=False):
    membership = db.scalar(
        select(m.Membership).where(
            m.Membership.workspace_id == workspace_id, m.Membership.user_id == user.id
        )
    )
    if not membership:
        raise HTTPException(404, "Workspace not found")
    if teaching and membership.role not in ("owner", "teacher"):
        raise HTTPException(403, "A teaching role is required")
    return membership


def classroom(db, classroom_id, edit=False, staff=True, active=False):
    record = db.get(m.Classroom, classroom_id)
    if not record:
        raise HTTPException(404, "Classroom not found")
    allowed = db.scalar(
        text("SELECT chalkmate.staff(:id, :edit)"), {"id": classroom_id, "edit": edit}
    )
    if staff and not allowed:
        raise HTTPException(404, "Classroom not found")
    if active and record.archived:
        raise HTTPException(409, "Restore this classroom before making changes")
    return record


def class_output(db, record, user):
    membership = workspace_member(db, record.workspace_id, user)
    assignment = db.scalar(
        select(m.ClassroomTeacher).where(
            m.ClassroomTeacher.classroom_id == record.id, m.ClassroomTeacher.user_id == user.id
        )
    )
    role = "owner" if membership.role == "owner" else assignment.role if assignment else "student"
    count = (
        db.scalar(
            select(func.count())
            .select_from(m.Enrollment)
            .where(m.Enrollment.classroom_id == record.id, m.Enrollment.status == "active")
        )
        or 0
    )
    return s.ClassroomOutput.model_validate(
        {
            **{
                key: getattr(record, key)
                for key in ("id", "workspace_id", "name", "subject", "term", "archived")
            },
            "can_edit": role in ("owner", "teacher"),
            "role": role,
            "student_count": count,
        }
    )


@router.get("/session", response_model=s.SessionOutput)
def session(db: Database, user: CurrentUser):
    records = db.execute(
        select(m.Workspace, m.Membership.role)
        .join(m.Membership, m.Membership.workspace_id == m.Workspace.id)
        .where(m.Membership.user_id == user.id)
    ).all()
    return {
        "id": user.id,
        "email": user.email,
        "workspaces": [{"id": item.id, "name": item.name, "role": role} for item, role in records],
    }


@router.post("/workspaces", response_model=s.WorkspaceOutput, status_code=201)
def create_workspace(body: s.WorkspaceInput, db: Database, user: CurrentUser):
    record = m.Workspace(name=body.name, owner_id=user.id)
    db.add(record)
    db.flush()
    db.add(m.Membership(workspace_id=record.id, user_id=user.id, role="owner"))
    audit(db, user, record.id, "workspace.created")
    return {"id": record.id, "name": record.name, "role": "owner"}


@router.get("/workspaces/{workspace_id}/classrooms", response_model=list[s.ClassroomOutput])
def list_classes(workspace_id: UUID, db: Database, user: CurrentUser):
    workspace_member(db, workspace_id, user)
    return [
        class_output(db, record, user)
        for record in db.scalars(
            select(m.Classroom)
            .where(m.Classroom.workspace_id == workspace_id)
            .order_by(m.Classroom.created_at.desc())
        )
    ]


@router.post(
    "/workspaces/{workspace_id}/classrooms", response_model=s.ClassroomOutput, status_code=201
)
def create_class(workspace_id: UUID, body: s.ClassroomInput, db: Database, user: CurrentUser):
    workspace_member(db, workspace_id, user, teaching=True)
    record = m.Classroom(workspace_id=workspace_id, created_by=user.id, **body.model_dump())
    db.add(record)
    db.flush()
    db.add(
        m.ClassroomTeacher(
            workspace_id=workspace_id, classroom_id=record.id, user_id=user.id, role="teacher"
        )
    )
    db.flush()
    audit(db, user, workspace_id, "classroom.created", record.id)
    return class_output(db, record, user)


@router.get("/classrooms/{classroom_id}", response_model=s.ClassroomOutput)
def get_class(classroom_id: UUID, db: Database, user: CurrentUser):
    return class_output(db, classroom(db, classroom_id, staff=False), user)


@router.patch("/classrooms/{classroom_id}", response_model=s.ClassroomOutput)
def update_class(classroom_id: UUID, body: s.ClassroomUpdate, db: Database, user: CurrentUser):
    record = classroom(db, classroom_id, edit=True)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Classroom values cannot be null")
    for key, value in changes.items():
        setattr(record, key, value)
    db.flush()
    audit(db, user, record.workspace_id, "classroom.updated", record.id, fields=list(changes))
    return class_output(db, record, user)


@router.get("/classrooms/{classroom_id}/students", response_model=list[s.StudentOutput])
def students(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id)
    records = db.execute(
        select(m.Student, m.Enrollment)
        .join(m.Enrollment, m.Student.id == m.Enrollment.student_id)
        .where(m.Enrollment.classroom_id == classroom_id)
        .order_by(m.Student.registration_number)
    ).all()
    return [
        {
            "id": student.id,
            "enrollment_id": enrollment.id,
            "registration_number": student.registration_number,
            "name": student.name,
            "email": student.email,
            "status": enrollment.status,
            "linked": student.user_id is not None,
        }
        for student, enrollment in records
    ]


@router.patch(
    "/classrooms/{classroom_id}/enrollments/{enrollment_id}", response_model=s.ImportResult
)
def update_enrollment(
    classroom_id: UUID,
    enrollment_id: UUID,
    body: s.EnrollmentUpdate,
    db: Database,
    user: CurrentUser,
):
    record = classroom(db, classroom_id, edit=True, active=True)
    enrollment = db.get(m.Enrollment, enrollment_id)
    if not enrollment or enrollment.classroom_id != classroom_id:
        raise HTTPException(404, "Enrollment not found")
    enrollment.status = body.status
    audit(
        db,
        user,
        record.workspace_id,
        "enrollment.updated",
        record.id,
        enrollment_id=str(enrollment_id),
        status=body.status,
    )
    return {"imported": 0}


def roster_conflicts(db, record, rows):
    issues = []
    for row in rows:
        existing = db.scalar(
            select(m.Student).where(
                m.Student.workspace_id == record.workspace_id,
                m.Student.registration_number == row["registration_number"],
            )
        )
        if existing:
            enrolled = db.scalar(
                select(m.Enrollment.id).where(
                    m.Enrollment.classroom_id == record.id, m.Enrollment.student_id == existing.id
                )
            )
            message = (
                "Student is already enrolled in this class"
                if enrolled
                else (
                    "Existing student details differ; ask the workspace owner to resolve them"
                    if (existing.name != row["name"] or existing.email != row["email"])
                    else None
                )
            )
            if message:
                issues.append({"row": row["row"], "severity": "error", "message": message})
    return issues


@router.post("/classrooms/{classroom_id}/imports/preview", response_model=s.ImportOutput)
def preview_import(classroom_id: UUID, file: UploadFile, db: Database, user: CurrentUser):
    record = classroom(db, classroom_id, edit=True, active=True)
    content = file.file.read(MAX_ROSTER_BYTES + 1)
    rows, issues = parse_roster(file.filename or "", content)
    issues.extend(roster_conflicts(db, record, rows))
    batch = m.ImportBatch(
        workspace_id=record.workspace_id,
        classroom_id=record.id,
        created_by=user.id,
        rows=rows,
        issues=issues,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    db.add(batch)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "roster.previewed",
        record.id,
        batch_id=str(batch.id),
        row_count=len(rows),
    )
    return batch


@router.post("/classrooms/{classroom_id}/imports/{batch_id}/confirm", response_model=s.ImportResult)
def confirm_import(classroom_id: UUID, batch_id: UUID, db: Database, user: CurrentUser):
    record = classroom(db, classroom_id, edit=True, active=True)
    # Serialize confirmation in this class, including different preview batches.
    db.execute(select(m.Classroom.id).where(m.Classroom.id == classroom_id).with_for_update())
    batch = db.scalar(select(m.ImportBatch).where(m.ImportBatch.id == batch_id).with_for_update())
    if not batch or batch.classroom_id != classroom_id or batch.created_by != user.id:
        raise HTTPException(404, "Import preview not found")
    if batch.confirmed_at or batch.expires_at <= datetime.now(UTC):
        raise HTTPException(409, "This preview was used or expired. Upload the roster again.")
    if any(issue["severity"] == "error" for issue in batch.issues):
        raise HTTPException(409, "Correct the roster errors and upload it again")
    conflicts = roster_conflicts(db, record, batch.rows)
    if conflicts:
        raise HTTPException(409, "Student records changed. Upload the roster for a fresh preview.")
    for row in batch.rows:
        student = db.scalar(
            select(m.Student).where(
                m.Student.workspace_id == record.workspace_id,
                m.Student.registration_number == row["registration_number"],
            )
        )
        if not student:
            student = m.Student(
                workspace_id=record.workspace_id,
                registration_number=row["registration_number"],
                name=row["name"],
                email=row["email"],
            )
            db.add(student)
            db.flush()
        db.add(
            m.Enrollment(
                workspace_id=record.workspace_id, classroom_id=record.id, student_id=student.id
            )
        )
    batch.confirmed_at = datetime.now(UTC)
    audit(
        db,
        user,
        record.workspace_id,
        "roster.imported",
        record.id,
        batch_id=str(batch.id),
        row_count=len(batch.rows),
    )
    db.flush()
    return {"imported": len(batch.rows)}


@router.get("/classrooms/{classroom_id}/invitations", response_model=list[s.InvitationOutput])
def invitations(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id, edit=True)
    return list(
        db.scalars(
            select(m.Invitation)
            .where(m.Invitation.classroom_id == classroom_id)
            .order_by(m.Invitation.expires_at.desc())
        )
    )


@router.post(
    "/classrooms/{classroom_id}/invitations", response_model=s.InvitationCreated, status_code=201
)
def invite(classroom_id: UUID, body: s.InvitationInput, db: Database, user: CurrentUser):
    record = classroom(db, classroom_id, edit=True, active=True)
    email = str(body.email).lower()
    if body.role == "student":
        student = db.get(m.Student, body.student_id) if body.student_id else None
        enrolled = db.scalar(
            select(m.Enrollment).where(
                m.Enrollment.classroom_id == classroom_id,
                m.Enrollment.student_id == body.student_id,
                m.Enrollment.status == "active",
            )
        )
        if not student or not enrolled or student.email != email or student.user_id:
            raise HTTPException(422, "Choose an unlinked active student with this email")
    elif body.student_id:
        raise HTTPException(422, "Student ID is only valid for student invitations")
    token = secrets.token_urlsafe(32)
    invitation = m.Invitation(
        workspace_id=record.workspace_id,
        classroom_id=record.id,
        email=email,
        role=body.role,
        student_id=body.student_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invitation)
    db.flush()
    audit(
        db,
        user,
        record.workspace_id,
        "invitation.created",
        record.id,
        invitation_id=str(invitation.id),
        role=body.role,
    )
    # Fragment avoids sending invitation secrets in HTTP request paths or referrers.
    return {
        **s.InvitationOutput.model_validate(invitation).model_dump(),
        "url": f"{get_settings().web_origin}/invite#token={token}",
    }


@router.delete("/classrooms/{classroom_id}/invitations/{invitation_id}", status_code=204)
def revoke_invitation(classroom_id: UUID, invitation_id: UUID, db: Database, user: CurrentUser):
    record = classroom(db, classroom_id, edit=True)
    invitation = db.get(m.Invitation, invitation_id)
    if not invitation or invitation.classroom_id != classroom_id:
        raise HTTPException(404, "Invitation not found")
    invitation.revoked = True
    audit(
        db,
        user,
        record.workspace_id,
        "invitation.revoked",
        record.id,
        invitation_id=str(invitation_id),
    )


@router.post("/invitations/accept", response_model=s.AcceptedInvitation)
def accept_invitation(body: s.AcceptInvitation, db: Database, user: CurrentUser):
    invitation = db.scalar(
        select(m.Invitation)
        .where(m.Invitation.token_hash == hashlib.sha256(body.token.encode()).hexdigest())
        .with_for_update()
    )
    if not invitation or invitation.email != user.email:
        raise HTTPException(404, "Invitation not found for your verified email")
    if invitation.revoked or invitation.accepted_at or invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(409, "This invitation expired, was revoked, or has already been used")
    db.execute(
        insert(m.Membership)
        .values(
            id=uuid4(), workspace_id=invitation.workspace_id, user_id=user.id, role=invitation.role
        )
        .on_conflict_do_nothing(index_elements=["workspace_id", "user_id"])
    )
    if invitation.role == "student":
        student = db.get(m.Student, invitation.student_id)
        enrollment = db.scalar(
            select(m.Enrollment).where(
                m.Enrollment.classroom_id == invitation.classroom_id,
                m.Enrollment.student_id == invitation.student_id,
                m.Enrollment.status == "active",
            )
        )
        if not student or student.user_id or student.email != user.email or not enrollment:
            raise HTTPException(409, "Student details changed. Ask for a new invitation.")
        student.user_id = user.id
    else:
        db.execute(
            insert(m.ClassroomTeacher)
            .values(
                id=uuid4(),
                workspace_id=invitation.workspace_id,
                classroom_id=invitation.classroom_id,
                user_id=user.id,
                role=invitation.role,
            )
            .on_conflict_do_nothing(index_elements=["classroom_id", "user_id"])
        )
    # Flush linkage while the invitation is still pending; RLS checks the pending invite.
    db.flush()
    invitation.accepted_at = datetime.now(UTC)
    audit(
        db,
        user,
        invitation.workspace_id,
        "invitation.accepted",
        invitation.classroom_id,
        invitation_id=str(invitation.id),
        role=invitation.role,
    )
    return {
        "workspace_id": invitation.workspace_id,
        "classroom_id": invitation.classroom_id,
        "role": invitation.role,
    }


@router.get("/classrooms/{classroom_id}/files", response_model=list[s.FileOutput])
def files(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id)
    return list(
        db.scalars(
            select(m.StoredFile)
            .where(m.StoredFile.classroom_id == classroom_id)
            .order_by(m.StoredFile.created_at.desc())
        )
    )


@router.post("/classrooms/{classroom_id}/files", response_model=s.FileOutput, status_code=201)
def upload_file(classroom_id: UUID, file: UploadFile, db: Database, user: CurrentUser):
    record = classroom(db, classroom_id, edit=True, active=True)
    filename = Path((file.filename or "upload").replace("\\", "/")).name[:180]
    content = file.file.read(MAX_FILE_BYTES + 1)
    content_type = validate_file(filename, content)
    file_id = uuid4()
    object_path = f"{record.workspace_id}/{record.id}/{file_id}"
    settings = get_settings()
    result = m.StoredFile(
        id=file_id,
        workspace_id=record.workspace_id,
        classroom_id=record.id,
        uploaded_by=user.id,
        filename=filename,
        object_path=object_path,
        content_type=content_type,
        size=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
    )
    db.add(result)
    audit(
        db,
        user,
        record.workspace_id,
        "file.uploaded",
        record.id,
        file_id=str(file_id),
        size=len(content),
    )
    db.flush()
    storage_request(
        "POST",
        f"object/{settings.storage_bucket}/{object_path}",
        content=content,
        headers={"Content-Type": content_type, "x-upsert": "false"},
    )
    return result


@router.get("/classrooms/{classroom_id}/files/{file_id}/download", response_model=s.DownloadOutput)
def download_file(classroom_id: UUID, file_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id)
    record = db.get(m.StoredFile, file_id)
    if not record or record.classroom_id != classroom_id:
        raise HTTPException(404, "File not found")
    settings = get_settings()
    response = storage_request(
        "POST",
        f"object/sign/{settings.storage_bucket}/{record.object_path}",
        json={"expiresIn": 60},
    ).json()
    return {"url": f"{settings.supabase_url}/storage/v1{response['signedURL']}", "expires_in": 60}


@router.get("/classrooms/{classroom_id}/audit", response_model=list[s.AuditOutput])
def audit_events(classroom_id: UUID, db: Database, user: CurrentUser):
    classroom(db, classroom_id)
    return list(
        db.scalars(
            select(m.AuditEvent)
            .where(m.AuditEvent.classroom_id == classroom_id)
            .order_by(m.AuditEvent.created_at.desc())
            .limit(100)
        )
    )
