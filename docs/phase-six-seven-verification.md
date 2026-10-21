# Planning and polish verification

Verified locally on 18 October 2026 against Supabase/PostgreSQL, FastAPI, the production Next.js build, Docker Celery/Redis and local Ollama. Only synthetic test accounts/work were used.

- Full backend regression run: **69 passed, 2 optional skipped** before the final version-order correction.
- Assessment/reliable-review checks after that correction: **12 passed, 1 optional skipped**, including a new regression that moves an older extraction timestamp into the future and still selects the highest version.
- Final planning/intelligence checks: **21 passed, 2 optional skipped**. Covers immutable versions, approval blockers, stale sources, source quotes, blueprint totals, variants/duplicate wording, report provenance, command non-execution, cross-workspace/student/reviewer isolation, exports, durable worker failure/retry limits, cancellation and expired leases.
- Optional real local generation: **passed** through the Docker scheduler/worker and `llama3.2:1b`, producing a meeting draft with model digest/token usage, original notes preserved and no automatic approval. The first universal output schema failed safely; prompt v2 uses small per-tool schemas. This is integration evidence, not a quality benchmark.
- Pilot metric unit tests and synthetic CLI rehearsal passed. No real teacher pilot or OCR/grading accuracy claim is made.
- Application database restore drill passed: **38 tables**, matching row counts/checksums from one exported snapshot, anonymous reads denied using the real restricted application login. Generated drill databases/archives were cleaned up. Auth/Storage/full-stack recovery remains unverified.
- Migration drift, Python formatting/lint, dependency consistency and production TypeScript/build checks passed. Worker images were rebuilt; dependencies now use a reusable Docker layer.

Browser findings were fixed instead of hidden: explicit source-picker labeling, a compact AI switch, viewport-aware help, mobile heading/search width, and removal of retained entrance transforms. The older re-evaluation journey exposed timestamp-based extraction selection; it now uses authoritative versions. See final browser results below.

Final Chrome verification: **foundation and planning both passed** in one run (39.6 seconds). The foundation journey completes rubric revision, re-evaluation, replacement release and a 390-pixel roster check. Planning creates/approves a syllabus, drafts/checks/approves a paper, verifies student-export key exclusion, checks navigation-only commands, keyboard/Escape help, tap-help bounds, reduced motion, mobile overflow and the light theme. Auth, follow-up and intelligence journeys also passed in the preceding run; that run exposed the now-fixed foundation issue. All five journeys were verified across these runs, rather than claiming one five-test green run.

Visual inspection: `.tmp/phase-six-planning-dark.png`, `.tmp/phase-six-planning-light.png`, `.tmp/phase-six-planning-mobile.png`. Final API/web processes and updated Docker worker/scheduler remain running locally. No hosted deployment or external sending was enabled.

Remaining gates: participating teachers, consented real samples and measured review times; subject/scan-specific quality and severe-error investigation; complete Auth/Storage disaster recovery; advanced institution-specific export mappings and measured variant equivalence. The Phase 7 pilot gate is not complete.
