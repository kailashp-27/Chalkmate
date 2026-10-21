# Phase 4 — Classroom follow-up

Phase 4 connects reviewed marks to versioned assignments, private student responses, and explicitly approved follow-up messages. The existing black/blue palette and Light/Dark/System preference apply to the new pages.

## Try it locally

Open http://localhost:3000 and select a classroom. **Assignments** lets teachers save a draft, review the audience, publish instructions, revise them as a new version, and close or reopen the assignment. Students see published work assigned to their linked verified account, with a private response form and retained submission history. A later publication supersedes the earlier response form without deleting its history. Due dates mark late work; they do not silently reject it. Text and PDF/JPEG/PNG attachments up to 10 MB are supported.

**Follow-up** selects an assessment, current published assignment, exact score rule, and message. Preview every disposition, resolve contacts or explicitly exclude blocked recipients, inspect one private personalized message at a time, then approve the fixed audience. A score is included only on explicit opt-in and only after that decision has been released. Each message includes a protected assignment link. Portal contacts must match the student's verified linked account; use People to invite unlinked students.

The optional send time queues a one-time scheduled reminder. “Skip students who already submitted” is checked both in the preview and immediately before dispatch. This phase does not add recurring campaigns.

## Local AI and email

The user confirmed **D:\Projects\EchoSphere** and local Ollama. Both projects use the local Ollama service on port 11434; Chalkmate retains `gemma3:4b`. Local Ollama requires no API key. EchoSphere's Gemini credentials were not copied.

Default `MAIL_PROVIDER=mailpit` captures synthetic messages at http://127.0.0.1:54324. They do not reach Gmail. The ledger distinguishes captured locally, provider accepted, delivered, bounced, failed, held, skipped, canceled, and uncertain outcomes. The local inbox is linked directly from Follow-up.

An optional Resend adapter is implemented but disabled and unconfigured locally. To deploy it later, configure `MAIL_PROVIDER=resend`, a verified `MAIL_FROM`, server-only `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`, and `ENABLE_EXTERNAL_EMAIL=true` in the API and worker environments. Register `/v1/webhooks/resend` on the deployed API. Never place these secrets in a `NEXT_PUBLIC_` variable. Real external delivery has not been exercised in local verification.

## Integrity and recovery

Approval checks a short-lived immutable preview digest covering recipients, contacts, identity, score decision, rule, message, assignment publication, sender, and provider. It atomically creates the campaign and recipient outbox; repeat approval returns the same campaign. Changed previews require renewed review. Decimal comparisons make “below 25” strictly `<25`; missing/unapproved/withdrawn/different-maximum records remain distinct.

Workers use a restricted database role, atomic claims, leases, and a final eligibility check. Later score/contact/publication/access changes hold or skip recipients. The worker never silently adds recipients to an approved list. Teacher actions and provider attempts retain an audit trail. Failed messages require explicit bounded retries; uncertain messages require reconciliation. Canceling a pending item does not claim to undo a message already accepted by a provider.

Mailpit reconciles by stable message identity and tag. Resend uses a stable per-recipient idempotency key and exact immutable payload. Receiptless reconciliation is limited to a conservative 23-hour window; older uncertainty requires provider investigation. Signed webhook verification checks the raw body, timestamp, and signature; event storage deduplicates events, preserves confirmed delivery from stale acceptance events, and suppresses bounced/complained contacts. Events received before the send receipt commits are replayed by the dispatcher.

Assignments, audiences, responses, campaigns, recipient records, and attempts have RLS and scoped foreign keys. Student file downloads require ownership and issue short-lived private URLs. Teacher contact editing uses a scoped database function so account-link permissions are not broadened. Migrations 0008 and 0009 are additive; Alembic remains the schema authority.

## Verification

`services/api/tests/test_followup.py` exercises publication history, private files, late responses, stale submission checks, eligibility boundaries, preview drift, explicit exclusions, approval idempotency, scheduled dispatch, contact holds, submission skips, capture deduplication, lost receipts, retry bounds, lease expiry, webhook signatures, event order, bounce suppression, and database permissions. `apps/web/tests/followup.spec.ts` covers teacher publication and local capture through a student's protected response page, including mobile overflow.

Run with the local stack and API available:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
docker compose --env-file .env -f infra/compose.yaml --profile workers up -d --build
.venv/Scripts/python.exe -m pytest -q --tb=short
npm.cmd run test:e2e --workspace apps/web
```

These checks establish workflow and permission behavior, not model grading accuracy. Local test accounts use synthetic records and scoped cleanup. Hosted deployment, real student data, and external message delivery remain unverified.

## Local verification result — 17 October 2026

- All **23 Phase 4 backend checks passed together** after fixing the synthetic boundary fixtures. Existing backend regression checks also passed (23 tests; one optional live-model check skipped).
- All **3 Chrome journeys passed**: signup/verification/themes, teacher follow-up to private student response, and the existing assessment/question-review/rubric/re-evaluation/replacement-release journey.
- The Phase 4 browser journey captured one private local message, submitted a student response through its protected link, and passed the mobile overflow check. Desktop and mobile screenshots were inspected.
- Production build, generated API types, TypeScript, Ruff, formatting, dependency consistency, and Alembic schema comparison passed.
- Web, API, Mailpit and Ollama were reachable; the configured gemma3:4b model was installed. Worker and scheduler dispatch logs showed successful processing.
- External email remains disabled. Resend recovery was checked with mocked requests, not real external delivery. Hosted CI has been updated but has not run remotely.
