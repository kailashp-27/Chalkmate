# Phase 4: classroom follow-up contract

## Assignments and student portal
- Teachers save immutable assignment versions with title, instructions, and an optional timezone-aware due date. Publishing explicitly pins a version and snapshots an audience of active students. New instructions require a new publication; earlier content/responses remain preserved.
- Linked, active students see only published versions assigned to them and their own response history. Responses accept text and/or a private PDF/JPEG/PNG up to 10 MB. Concurrent edits use an expected response version; late responses are visibly flagged. Archived/closed classrooms/assignments block new responses.
- Private assignment links require sign-in and audience membership. Students cannot enumerate classmates' submissions, contacts, score filters, campaigns, previews, or delivery records.

## Score rules and communication approval
- Rules explicitly choose assessment, operator, threshold, and expected maximum. Decimal arithmetic is authoritative. `<25` includes 24.5, excludes 25/25.5; missing, unreadable/unapproved, withdrawn, and different maxima are separate exclusions. Only the latest currently approved/released decision is eligible; in-progress re-evaluations are held.
- Preview stores an expiring immutable snapshot: rule, published assignment version, selected/excluded students, linked account, active enrollment, score/decision version, email, subject/body, and approval digest. Unresolved contact or portal access blocks approval until explicitly excluded or corrected. No automatic recipient additions.
- Personalization is shown one student at a time. Plain-text templates allow only documented placeholders. Scores in email are opt-in and require a released matching decision. Each message contains a sign-in-protected assignment link and exactly one recipient, never CC/BCC or other students' data.
- Approval consumes a preview once and atomically creates a campaign and durable recipient outbox rows. A timezone-aware future send time schedules a one-time reminder. Reminders may explicitly skip students who already responded to the chosen assignment version. New reminders require a new preview/approval.

## Delivery and recovery
- Worker claims due IDs through restricted security-definer queue functions, rechecks current teaching access, enrollment, contact, score/decision, maximum, assignment publication/audience, and response state immediately before sending. Changed versions/contacts are held; no-longer-eligible or already-submitted students are skipped. Newly eligible students are never added.
- Per-recipient immutable payload and stable idempotency key, bounded attempts, leases, attempt history, provider IDs, and signed webhook event IDs form the ledger. Captured development mail is distinguished from external acceptance/delivery. Duplicate approvals, queue messages, and webhook events are idempotent.
- Mailpit captures development emails locally only. Optional Resend transport uses server-side credentials, stable idempotency keys, and verified signed webhooks. No external delivery is configured or exercised by this implementation task.
- Definite failures allow explicit scoped retries after revalidation. Lost/uncertain responses are held for reconciliation; expired idempotency windows are never blindly retried. Local reconciliation searches the captured message identifier; Resend reconciliation retrieves a known provider ID or reuses the original immutable request within a conservative 23-hour window. Outside that window, unresolved items remain held.
- Teachers can cancel pending recipients, inspect delivery history, and reconcile uncertain outcomes. Every mutation is class-scoped and audited.

## Completion checks
Boundary tests, assignment/student privacy and file ownership, immutable publication and stale response guards, preview drift/expiry, exclusion handling, delivery idempotency, changed-data holds, scheduled reminders/submission skips, uncertain recovery, signed webhook replay/order, and browser teacher-to-student submission plus captured-email workflow.
