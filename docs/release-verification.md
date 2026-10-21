# Local release verification — 21 October 2026

Scope and behavior contract: `contracts/local-release.md`. This records local synthetic verification, not a production or educational-quality certification.

- **Backend:** 90 passed, 3 optional tests skipped (353.51 seconds). Includes new release-pinned student requests, duplicate/stale/unreleased/unknown-question guards, reviewer read-only access, database write restrictions, unchanged marks after responses, overview counts, archive guards and actual PDF/image validation.
- **Web:** production build and TypeScript passed. **All 6 Chrome journeys passed** across two runs: signup/themes/password recovery; classroom/grading/rubric revision/replacement release; assignment/follow-up/private student response; intelligence findings/material approval; planning/help/navigation; and reporting/student-review-request/teacher-response. The new journey verified mobile overflow and the teacher response appearing in the student's portal. The mobile overview was visually inspected.
- **Static/data:** Ruff lint/format and dependency checks passed; Alembic reported no schema drift. Generated OpenAPI and TypeScript contracts refreshed.
- **Startup/shutdown:** new launcher started local Supabase, migrated the application, rebuilt workers and started web/API. Stop verified process identity and stopped both the Windows venv parent/child and web process. Both Chalkmate ports then stopped responding while the unrelated app on port 3000 remained HTTP 200. Restart succeeded at port 3001. Cached worker rebuild requires an exact match to the image's dependency lock.
- **Local account:** the existing confirmed synthetic demo account signed in successfully. Credentials remain only in ignored `.tmp/demo-credentials.json`.
- **Local model:** Ollama responded and the configured grading and vision model tags were installed. No model selection changed and no new accuracy claim was made.
- **Fallback:** unknown page returned HTTP 404 with the app's recovery view; web/API health returned HTTP 200.
- **Packaging:** ZIP integrity and every source checksum matched. Dependencies, `.env` files other than the safe example, backups, runtime state and local data were absent. Final documentation is included in the regenerated source archive.
- **Final services:** API/web health returned HTTP 200, the resumed Docker worker had a fresh genuine heartbeat, configured local Ollama models were installed, and no temporary recovery containers remained. Chalkmate runs on port 3001 while the unrelated port-3000 application remains running.
- **Repeat setup:** rerunning local configuration preserved the existing worker credential and selected web origin, avoiding unnecessary credential changes on a routine restart.

The fresh full-stack recovery rehearsal on 21 October passed in **87.55 seconds**: **77 tables and 4 private objects** matched their hashes; restored email/password sign-in and private download worked, anonymous/unrelated-user access was denied, and the generated stack was cleaned up. Readiness dates show the most recent successful local drill, not a scheduled-backup guarantee.

No hosted services were provisioned or external messages sent. Real teacher pilot quality/review-time targets, public production configuration and the broader options in RELEASE-STATUS.md remain outside the verification claims.
