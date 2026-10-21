# Phase 1 contract

This phase implements a local teacher workspace with real Supabase Auth and
private Storage. FastAPI owns mutations, authorization, and roster validation.
The browser sends a Supabase bearer token; the API validates it against Auth,
then sets transaction-local identity on a restricted PostgreSQL role. A student
record is linked only by accepting an unexpired invitation with a matching,
verified account email. No grades, AI processing, or outgoing mail are included.

## Access

Workspace owners manage all classes and invitations. Teachers may create classes
in their workspace and edit classes explicitly assigned to them. Reviewers may
read assigned classes, but cannot change them. Students may read their own
enrollment, never the roster. Unknown and inaccessible scoped resources return
404. Database policies independently enforce the same visibility boundary.

## HTTP surface

- `GET /v1/session`: authenticated user and workspace memberships.
- `POST /v1/workspaces`: create a workspace and owner membership atomically.
- `GET|POST /v1/workspaces/{id}/classrooms`: assigned classes / create class.
- `GET|PATCH /v1/classrooms/{id}`: class details / archive or edit metadata.
- `GET /v1/classrooms/{id}/students`: roster for authorized teaching staff.
- `PATCH /v1/classrooms/{id}/enrollments/{id}`: enrollment status.
- `POST /v1/classrooms/{id}/imports/preview`: CSV/XLSX multipart preview.
- `POST /v1/classrooms/{id}/imports/{id}/confirm`: atomic, one-use import.
- `POST /v1/classrooms/{id}/invitations`: scoped teacher/reviewer/student link.
- `POST /v1/invitations/accept`: verified-email, single-use acceptance.
- `POST /v1/classrooms/{id}/files`: bounded PDF/JPEG/PNG upload to private storage.
- `GET /v1/classrooms/{id}/files`: private file metadata.
- `GET /v1/classrooms/{id}/files/{id}/download`: authorized, short-lived link.
- `GET /v1/classrooms/{id}/audit`: chronological authorized event metadata.

Roster headers are `registration_number,name,email`. A preview shows rows,
errors, and email warnings. Required values, duplicates, identity conflicts, and
already-enrolled students block confirmation. Invalid/missing email is a warning
and imports as null only after explicit confirmation. Reject formulas, oversized
archives, unsupported extensions, and more than 1,000 rows. Preserve reusable
student identities separately from enrollment. Preview expires after 30 minutes;
confirmation revalidates current records and is transactional.

All writes produce audit events in the same database transaction. File storage
uses a private bucket, identifier-only object paths, an explicit size/type limit,
and short-lived authorized downloads. Phase 1 files are stored, never executed or
sent to processing providers. Real scan processing/malware scanning comes later.

The generated `openapi.json` and `apps/web/src/lib/api-schema.d.ts` are derived
from the implementation and must match this contract. Automated checks cover
two independent owners, assigned reviewers, student invitations, and concurrent
or replayed imports, using a real PostgreSQL instance rather than SQLite.
