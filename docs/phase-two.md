# Phase 2: assessment review and release

The user authorized Phase 2 and requested a blue/navy theme with light and dark
modes. They explicitly chose **local Ollama**, replacing the original cloud
Gemini/Azure candidates. No cloud key or separate OCR account is required.

## Workflow

1. Create an assessment in a classroom's Assessments tab.
2. Define questions, model answers, accepted alternatives, and criterion marks.
   Save an immutable rubric version, then explicitly approve and activate it.
3. Upload up to 20 separate papers and confirm the student for each file. No OCR
   identity matching occurs. Duplicate papers/submissions are rejected. Original
   bytes remain private. PDFs support 1–30 pages and images up to 25 megapixels;
   the file limit is 10 MB per paper.
4. Extract PDF text locally, choose a vision model for scans, or transcribe
   manually. Review/correct text and question page ranges beside the original.
   Confirm identity and page completeness/order. Unreadable work blocks approval.
5. Request optional local suggestions or grade manually with a recorded reason.
   Check criterion evidence and marks. Overrides preserve proposals and require
   a reason. Python Decimal computes totals; model totals are never accepted.
6. Approve marks and feedback, then separately confirm release. Students see only
   their own released feedback. Export CSV/XLSX marks with missing/unreleased
   work clearly separate from a scored zero.

This phase supports **all questions required**. Calibration, optional-question
groups, question-by-question marking, rubric changes after activation, and
re-evaluation of released work remain later phases. Activated rubrics and released
results cannot be rewritten in this workflow. Rubrics, extractions, proposals,
decisions, and releases retain separate immutable records.

## Local processing

Ollama was already installed on this machine; `gemma3:4b` was installed for local
vision and grading. To reproduce:

```powershell
ollama pull gemma3:4b
```

Configure `OLLAMA_URL`, `OLLAMA_MODEL`, and `OLLAMA_VISION_MODEL` in root `.env`.
Select an installed model for each run. Empty vision selection means PDF embedded
text only. Cloud-backed endpoints/models and embedding-only grading models are
rejected. No key is needed. On the initial machine the model runs on CPU, so allow
time for processing. Model responses have no application tools. Criterion IDs,
score bounds, question IDs, exact evidence quotations, and page ranges are checked
before a proposal is stored; invalid outputs become failed reviewable jobs.
Local calls have bounded context/output budgets; oversized inputs remain in
manual review rather than silently approving a truncated response.

PostgreSQL job rows are the durable outbox. Celery Beat polls every five seconds
and republishes pending IDs. A restricted worker role claims jobs atomically,
sets stored actor context, and rechecks class access. Leases recover abandoned
jobs; attempts are bounded at three. Cancellation, extraction changes, and release
invalidate late outputs. The API role cannot enumerate/claim the queue. Queue
messages contain IDs rather than student work.

Use `WORKER_DATABASE_URL` on the host and `WORKER_CONTAINER_DATABASE_URL` in
Compose. Containers reach local Ollama/Supabase via `host.docker.internal`.
The configured worker and dispatcher were verified locally.

## Appearance

Settings offers light, dark, and system modes. The preference is saved on this
browser and applied before first paint. Both modes share a blue/navy palette and
cover the existing classroom screens, forms, dialogs, PDF review, and result views.

## Verification and limits

Tests cover review/approval/release, student/workspace privacy, immutable release,
unreadable/stale extraction guards, criterion bounds, exact evidence, override
history, exports, and idempotent PDF jobs. The browser journey covers rubric
construction, matching, original-paper review, manual marking, approval/release,
CSV export, theme persistence, and mobile overflow. CI uses the manual path and
deterministic validation fixtures; no model download is needed for CI.

Local Ollama passed synthetic structured-grading and printed-image transcription
smoke checks, plus a complete queued grading job that stored a validated proposal.
These verify integration and validation, **not handwriting or grading
accuracy**. Build the plan's consented/anonymized held-out benchmark before making
reliability claims. Teacher review remains mandatory.

Evidence currently has page-level provenance, not geometric OCR regions or
calibrated confidence. Vision extraction is capped at 10 pages; PDF/manual review
supports 30. File signatures/structure are checked; malware scanning and stronger
parser isolation remain production work. Storage and database writes cannot share
a transaction, so private-orphan cleanup remains an operational limitation.
No real email delivery, hosted deployment, or paid service was added.

Phase 3 subsequently adds reasoned rubric revisions, calibration snapshots, question review, review queues, feedback cards, and explicit re-evaluation with preserved release history. See [Phase 3](phase-three.md); its versioning workflow supersedes the Phase 2 immutability limitation above.
