# Pilot readiness and polish

## Interface

Planning uses a compact tool shelf, searchable document cards and one focused editor at a time. Black/blue and light themes share the same surfaces and accent tokens. Across classroom screens, short headings replace introductory paragraphs; Info buttons expose explanations on hover, keyboard focus or tap. Escape dismisses help. Native dialogs provide keyboard focus containment and restoration; each has a unique accessible title. Required confirmation and permission details remain visible at the point of action.

Motion is finite: a short content entrance, button press feedback and a gentle icon wobble on pointer hover. No continuous background animation. Device reduced-motion settings disable animations, transitions and smooth scrolling. The browser journey checks this preference and mobile horizontal overflow.

## Evaluate a teacher pilot

Use `evaluation/pilot-example.json` only as a synthetic rehearsal. Run:

```powershell
.venv/Scripts/python.exe scripts/evaluate_pilot.py evaluation/pilot-example.json --output .tmp/pilot-report.json
```

For a real pilot, collect consented/anonymized work for the intended subject, separate calibration and held-out sheets, record reference transcription and reviewed marks, and double-mark a subset. Do not put names/emails in sample IDs. Keep private manifests outside Git (for example under ignored `.tmp/`). The validator rejects duplicate IDs, overlapping sheets, nonconsented records, nonfinite/out-of-bounds marks and incomplete transcription pairs.

The report excludes calibration answers and groups results by answer type and scan quality. It measures absolute/normalized grading errors, agreement within 10% of question maximum, errors over 20% with direction/sample IDs, identity/question mismatches, review rate, paired baseline/review time, latency percentiles, human disagreement and transcription CER/WER when supplied. Targets are provisional and require teacher interpretation; group sizes and severe errors must be inspected. It does not authorize publication.

**Real pilot gate remains open:** no claim of educational accuracy, OCR reliability, 90% agreement or 30% teacher-time savings is established by synthetic tests. The participating teachers, consented samples and real baseline/review timings are still required. Local CPU model latency and generated-content quality vary with hardware and model; a smaller installed model is an explicit per-run choice, never a silent grading change.

## Recovery drill

Update: [Phase 9](phase-nine.md) now adds and verifies the isolated full local Auth/Storage/application recovery procedure. The older schema-only drill below remains useful for narrower checks.

```powershell
.venv/Scripts/python.exe scripts/restore_drill.py --cleanup
```

This local-only drill exports a consistent PostgreSQL snapshot of the application schema, restores it into a newly named isolated database, compares all table row checksums/counts and checks that the restricted application role cannot read planning records without an identity. `--cleanup` drops only that generated database and its archive after verification. The original application database is never restored over. A summary goes to `.tmp/restore-drill.json`; row content and secrets are not printed.

Scope is deliberately explicit: this checks the `chalkmate` PostgreSQL schema, policies and functions. A full disaster-recovery procedure must also back up Supabase Auth identities and private Storage objects/configuration, verify object hashes, and exercise sign-in and document download on an isolated full stack. The application-schema drill alone does not establish full-stack RPO/RTO. Without `--cleanup`, the isolated database/archive remain private local copies to inspect; remove them using their exact generated names after inspection.

## Failure and usage controls

Readiness shows planning queue attention and local generation usage. Queue leases, explicit retries, attempt limits, cancellation, scoped worker claims and source rechecks preserve reviewability. The existing assessment/intelligence and delivery screens retain their own detailed job/delivery recovery controls. Planning never sends mail or changes marks. No local token-to-currency estimate is invented; local Ollama records usage and duration, while source/output/concurrency/day limits bound work.

Verification evidence for this delivery is recorded in `docs/phase-six-seven-verification.md`. Human quality and full-stack restore gates must remain pending until actually exercised.
