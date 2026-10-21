# Phase 1: product foundation

Implemented locally on 16 October 2026. The original setup-only instruction was
superseded by the user's explicit authorization to implement Phase 1 and use
local Supabase through Docker.

## What is implemented

- Supabase email/password sign-up, sign-in, verification, and password recovery.
  Local verification mail goes to Mailpit, not to external recipients.
- Personal workspaces and classrooms with subject/academic-term metadata,
  edit, archive, and restore actions.
- CSV/XLSX roster preview, required fields, duplicate and identity-conflict checks,
  email warnings, bounded uploads, expiring previews, atomic one-use confirmation,
  registration-based student identities, and independent enrollment status.
- Scoped teacher and read-only reviewer invitations. Verified-email student
  invitations link an account to a record without enabling email-only claiming.
- Private PDF/JPEG/PNG resources, checksums and metadata, authenticated file
  access, and 60-second downloads. Files are stored without rendering or processing.
- Server-side authorization plus PostgreSQL row-level security. The application
  role is neither a superuser nor an RLS-bypass role. The migration owner is kept
  separate. The `chalkmate` schema is not exposed through the Supabase Data API.
- Audit entries written in the same transaction as business changes; commit
  completes before a successful API response is sent.
- Responsive classroom screens, shared design tokens, labeled forms, native
  modal keyboard handling, visible loading/errors, and a generated API type contract.
- GitHub Actions checks for build/types, lint, contract drift, real PostgreSQL
  isolation tests, and the browser journey. The workflow is authored locally;
  a remote GitHub run is not claimed.

## Boundaries and operational notes

There is no grading, assessment, AI provider, real mail delivery, or job scheduling.
The Celery worker is prepared but has no business tasks. Local Supabase manages
its own internal auth/storage schemas; Alembic is the sole authority for application
schema, policies, and grants. Do not put application migrations in Supabase's
migrations directory.

One subject and term are metadata on a classroom in this phase. A full reusable
course/term catalog, broader student profile editing, teacher-access removal,
institution provisioning, and production security/retention review remain later
work. Existing student identities with conflicting details are never overwritten
by a roster. A non-owner cannot reuse an identity visible only in an unassigned
class; the owner must resolve that import. Invitations create a copyable link;
they do not send messages. Existing class roles are not upgraded by a second link.

Private resources are limited to trusted development files. File signatures are
checked, but full format validation and malware scanning are not yet implemented.
Database and storage cannot share a transaction: a failure after object upload
can leave a private orphan that needs cleanup. Never treat these stored resources
as approved or processed answer sheets. Production logging, backups/restore,
quotas, account lifecycle, deployment hardening, and retention remain release work.

## Verification

The recorded local tests cover API authentication, two-owner API/database isolation,
read-only reviewers, import validation/replay/concurrency, verified student linking,
student record isolation, XLSX formulas, and private file downloads. The browser
journey covers sign-in, workspace/class creation, roster preview/import, file
upload, invitation links, activity, mobile overflow, and sign-out.

Screenshots are disposable synthetic fixtures under `.tmp/`; tests clean up their
synthetic accounts and records. The production build uses webpack because this
Windows environment failed to launch Turbopack's CSS build subprocess. Development
continues to use Next.js's default bundler.
