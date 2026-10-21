# Phase 2 contract

Teacher workflow: create an assessment, save a criterion-based rubric, activate
its immutable version, upload separate papers and confirm student matching,
extract text, review/correct question-to-page mapping, request local Ollama
suggestions or mark manually, approve a criterion-level decision, explicitly
release it, and export released marks as CSV/XLSX. Students see only their own
released feedback. Every total is computed with Decimal in Python.

This implementation targets all-required English descriptive questions. Optional
question groups, rubric changes after uploads, re-evaluation of released results,
and calibration are later phases. No paper is silently assigned using OCR.
Unmapped/unreadable work blocks approval rather than becoming a zero.

Rubrics, extraction revisions, model proposals, decisions, and releases are
separate records with immutable inputs. Corrections invalidate previous approvals;
released results cannot be changed through the Phase 2 editing endpoints. Proposal
responses must contain exactly the known criterion IDs, valid bounded marks,
question IDs, and evidence quotations/pages that exist in reviewed extraction.
Preserve original proposals when a teacher overrides them and require a reason.

PDF embedded text extraction runs locally. Scans can use a local vision-capable
Ollama model; manual transcription remains available. Local Ollama is explicitly
requested by the user. No cloud model, cloud OCR account, or key is required.
Provider output is untrusted data and receives no application tools. Record model
name/digest, prompt version, and extraction/rubric IDs with proposals. Do not claim
handwriting accuracy without held-out evaluation.

PostgreSQL job rows are the durable outbox/checkpoint. A dispatcher republishes
queued jobs, workers claim them atomically with bounded attempts/leases, and
stale outputs cannot replace newer reviewed work. Queue messages carry job IDs.
Only the worker role may enumerate/claim work; it sets transaction-local actor
context from the stored authorization and rechecks class access. Poll for progress.

Access: owners/editing teachers mutate; assigned reviewers read; other classes
and workspaces are denied. Drafts, raw extractions, model proposals, and unreleased
marks remain invisible to students at both API and database layers. Downloads
remain private and short-lived. Exports include only released decisions and keep
missing work distinct from zero.

Appearance: navy/blue theme with light, dark, and system preferences; preference
is changed in Settings and persisted on this browser. Apply before first paint
to avoid a light flash. Both modes must keep inputs, dialogs, tables, and the
review workspace readable and responsive.
