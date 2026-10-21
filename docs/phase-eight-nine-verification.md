# Phases 8 and 9 verification

Scope accepted by the user on 19 October 2026: explicit question-performance links, reusable marks-export templates, current-local full backup/restore and service readiness. Contract: `contracts/phase-eight-nine.md`.

- Backend regression: **84 passed, 3 optional tests skipped**. New coverage exercises CSV/XLSX headings/order, decimal marks, formula protection, immutable snapshots, missing scores, approval rules, link history/staleness, authorization/RLS, worker heartbeat privileges and signed-bundle tamper/path rejection.
- Production web build and TypeScript passed. Ruff lint/format, dependency consistency and Alembic metadata drift checks passed. OpenAPI and generated TypeScript contracts were refreshed.
- Chrome reporting journey passed: create/approve/reorder a marks template, preview and download released marks, link/revoke a bank question, check reviewed averages, switch light theme and inspect mobile Readiness. Dark preview, light export panel and mobile screenshots were visually inspected.
- Final full Chrome regression: **6 passed**, covering signup/themes, classroom/grading/replacement release, follow-up/student submission, teaching intelligence, planning/help/navigation and the new reporting journey. Updated Docker worker/scheduler started; a genuine recent heartbeat was verified. Web/API health returned HTTP 200.
- Actual isolated full-stack recovery passed: 76 table checksums, 4 private-object hashes, restored synthetic email/password sign-in and private file download; anonymous and unrelated-user access denied. Approximately 89 seconds; generated stack cleaned up. Source synthetic probe removed. See `phase-nine.md` for recovery scope and private artifact handling.

These checks use synthetic accounts and marks. They do not prove real classroom accuracy, handwriting reliability, teacher time savings or production disaster-recovery targets. Hosted CI has not been observed; no deployment was requested.
