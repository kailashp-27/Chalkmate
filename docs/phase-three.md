# Phase 3: reliable review

The user authorized the next roadmap phase after Phase 2. This phase adds reliable review to the existing local workspace; it uses the same black/blue Light, Dark, and System themes, local Supabase, and Ollama.

## Try it

Open a classroom → Assessments → an assessment. The review desk has four views:

- **Review queue**: search students; filter awaiting review/release, ready to release, older rubric, or processing failures. Unreadable/unreviewed work and failed jobs receive priority. Every paper shows its pinned rubric and saved question count.
- **Question review**: choose one question and review it across readable, unreleased papers on the current rubric. Each save preserves criterion marks and question feedback. Open the original/full paper for final approval and release.
- **Calibration**: inspect immutable teacher reference snapshots, low/middle/high bands, and per-criterion model differences. Reference-only snapshots have no model error score. Each comparison retains rubric, extraction, model digest, prompt version, expected marks, and actual model marks. Examples are not held-out evaluation data or accuracy claims.
- **Rubric history**: inspect every saved version and a field-level comparison. A new revision needs a reason and matching base version. Activation is explicit. Existing papers remain pinned; new papers use the latest approved version.

The generated local test account includes **Demo · Reliable review** in its Computer Science classroom. It contains synthetic papers at different review stages, teacher references, a released result, and a draft rubric revision. Reproduce with `scripts/create_demo_account.py` followed by `scripts/seed_review_demo.py`; the latter refuses other accounts/hosted environments and preserves existing demo work on repeat runs. All demo names/answers are synthetic.

## Grading with calibration

On a reviewed paper, capture an example by entering teacher reference marks, band, and rationale. Model comparison is opt-in. To grade another paper, expand **Teacher reference examples** and explicitly select up to ten examples from other papers using that exact rubric. The local grading job receives only reference answer text, reference criterion marks, band, and snapshot IDs. It does not receive names or emails as application fields. Uploaded answer text may itself contain identifying information.

Selected snapshot IDs are pinned to the job and proposal. Job identity includes extraction, rubric, selected examples, model digest, and prompt version. Model output still passes exact-evidence, criterion, page, and bounds validation. Examples never approve a grade automatically. Oversized prompts fail reviewably rather than being silently truncated. Local CPU inference can take a few minutes.

## Re-evaluation and feedback

From a paper, choose **Re-evaluate paper**, explain why, and confirm the current approved rubric. This creates a fresh extraction snapshot, cancels pending jobs, and clears current proposal/approval displays. Check mapping/readability again, review marks, approve, then explicitly release a replacement. Older extraction, question review, decision, rubric, and release records remain available under **Review history**.

During re-evaluation the student and marks export continue to use the previous release and its original rubric. A replacement release switches the latest student feedback atomically. Students see only their own latest released feedback cards; model solutions, accepted alternatives, internal criterion guidance, teacher reasons, calibration references, and unreleased versions are excluded.

Feedback cards group approved criterion marks and teacher-written question feedback. They can be previewed before release. The marking screen can hide its identity header; the original document may still contain identifying information, so this is a practical review preference, not a claim of document anonymization.

## Verification

Contracts: `contracts/phase-three.md` and generated OpenAPI/TypeScript schemas. Additive Alembic migrations 0006/0007 introduce append-only review/calibration/re-evaluation records and replacement release history, with RLS and composite rubric scope constraints. API and worker remain restricted database roles.

Integration tests cover version diffs, stale edits, rubric pinning, old-release preservation, explicit replacement, student privacy, exports, question bounds, calibration comparison/provenance, explicit example selection, and prompt composition. The browser journey covers question review, calibration capture, rubric diff/activation, re-evaluation, preserved history, themes, and mobile overflow. Model quality still requires consented/anonymized held-out samples. No notifications, paid services, or hosted deployment were added.

## Local verification result — 16 October 2026

- Backend: **23 passed, 1 optional live-model test skipped** in the standard suite.
- Browser: local signup/email confirmation passed; the complete classroom → question review → calibration reference → rubric revision/diff/activation → re-evaluation → replacement release → preserved history journey passed. Light/dark persistence and mobile overflow checks passed.
- Separate real Ollama worker check: a synthetic paper produced a validated `gemma3:4b` proposal using an explicitly selected teacher reference. The saved proposal retained its calibration ID. It remained unapproved/unreleased.
- Production build and TypeScript passed. Alembic reported no schema changes; dependency checks, generated OpenAPI comparison, Ruff lint, and formatting passed.
- Review actions now refresh only the relevant review queries. Approvals reject pending processing and stale question-review snapshots.

These checks establish integration and permission behavior. They do not establish handwriting or grading accuracy.
