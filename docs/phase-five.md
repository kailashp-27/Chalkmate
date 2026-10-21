# Phase 5 — Teaching intelligence

The Intelligence classroom tab connects approved assessment work to question/topic summaries, cited teaching findings, remedial assignments, and revision packs. It keeps the existing black/blue styling and Light/Dark/System settings.

## Use the workflow

1. Open a classroom → **Intelligence** → choose an active assessment. The topic overview shows reviewed question marks, averages, full/partial/zero-credit counts, and readable/blank/unreadable evidence. Missing, unapproved, withdrawn, and different-rubric work remain separate; missing work is not scored as zero. Averages use the current approved rubric, so incompatible historical rubric versions are not mixed.
2. Choose a question and teaching topic. Use all eligible sources or explicitly select a subset. **Inspect source answers** shows pinned reviewed text, decision/extraction IDs, marks and mapped pages. Analysis supports at most 30 sources within a bounded local context; it refuses oversized inputs rather than silently sampling or truncating them.
3. Choose an installed local analysis model, then **Analyze with local Ollama** to queue a durable run. Smaller installed models are useful when memory is limited; this choice does not change assessment grading. Findings must cite exact answer substrings, source IDs, and a mapped page. Unknown IDs, invented quotes, invalid pages, duplicate citations, unsupported fields, and oversized results are rejected. Empty findings are a valid insufficient-evidence result. A strength or practice need can be more appropriate than a misconception label.
4. Inspect each citation and **Review finding**. Accept or dismiss it with a reason; prior reviews remain visible. Findings are suggestions, not diagnoses. An accepted interpretation does not change marks or notify students.
5. Select accepted findings and choose **Remedial assignment** or **Revision pack**. Choose the local material model and generate a draft, or write practice manually. Revise the student introduction, goals, notes, questions and hints separately from private teacher answers/rationale. Each save preserves a new material version.
6. **Review & approve material** requires confirmation and a reason. Approval creates an unpublished Phase 4 assignment containing student practice only. Open the draft, review its audience, and publish separately through Assignments. Repeated approval creates no duplicate draft. Nothing is emailed automatically.

A manual evidence-backed finding path remains available after inspecting sources. Revision packs support separate authenticated Markdown downloads for student practice and the private teacher answer key. Draft exports are visibly marked. The student export and assignment conversion exclude teacher answer/rationale fields and do not append source records or individual scores. Teacher review remains responsible for factual correctness and suitability of all student-visible generated prose.

## Local model and recovery

Generation stays in the existing FastAPI/Python package and local Ollama adapter; no cloud SDK, API key, paid service, or duplicate web-side orchestration was added. Model tag/digest, prompt version, usage, input digest and source versions are retained. Structured JSON uses Ollama's schema-constrained API and server-side Pydantic/citation validation. Teaching calls use an 8K context, four CPU threads, a 128-token processing batch, bounded output, and an eight-minute provider timeout; existing grading settings are unchanged. Authenticated reads no longer upsert unchanged user records. Auth verification uses a pooled stateless HTTP transport with request-specific bearer headers and no shared user cookies. This avoids serializing classroom reads and reduces connection churn during polling. See [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) and [chat API](https://docs.ollama.com/api/chat).

Ollama must be running on the host (`ollama serve`). Docker workers use `host.docker.internal:11434`; the web never calls the model directly. An unavailable local model leaves a reviewable failed run with explicit retry/manual authoring. The model tag is checked to be installed and local, not cloud-backed. Model quality has not been benchmarked by these workflow tests.

PostgreSQL stores queued/running/succeeded/failed/canceled states. Restricted worker functions claim jobs with leases and bounded attempts. Expired leases become failed and require explicit retry. Cancellation is checked before saving output. Before and after inference, the worker verifies reviewed answer/decision/rubric/enrollment/finding-review snapshots. Changed sources cancel or mark saved results stale; stale findings/materials cannot be accepted or approved. Existing assignment and assessment history is preserved.

## Privacy and permissions

Migration 0010 adds scoped foreign keys, indexes and RLS for runs, finding reviews, teaching-material versions and approvals. API requests use the restricted application role; queue claims use the restricted worker role. Students and unrelated teachers cannot read teaching evidence, runs, findings or private answer keys. Assigned reviewers may inspect but cannot generate, review, edit or approve. Archived classes block mutations. Creation, review, edits, approvals, exports and successful worker completion are audited. Migration 0011 provides a narrowly scoped export-audit function for read-only reviewers; it grants no general audit or material mutation access.

Structured student identifiers are omitted from model analysis input. Reviewed answer text can itself contain identifying words; source inspection is not an automatic document-anonymization guarantee. Material generation uses the teaching concepts and accepted interpretations, not the structured student records or citation list. All supplied/model text remains untrusted plain text; the UI does not execute generated HTML.

## Verification and scope

The contract is `contracts/phase-five.md`. Backend tests live in `services/api/tests/test_intelligence.py`; the browser journey is `apps/web/tests/intelligence.spec.ts`. The optional real-worker test is enabled with `RUN_LIVE_INTELLIGENCE=1` and uses synthetic, disposable accounts. Standard checks do not establish educational or grading accuracy.

The browser journey inspects a citation, accepts a finding, authors a revision pack, preserves an edited version, checks student export/key separation, approves an unpublished assignment, explicitly publishes it, and verifies the student's protected mobile page excludes teacher answers.

Phase 6 planning/administration and Phase 7 pilot/benchmarking remain future work. Hosted deployment, production data, and real external communication are unchanged.


## Synthetic walkthrough

The existing generated demo classroom contains **Demo · Stack ordering** and an unapproved **Demo · Stack revision pack**. These are clearly labeled, teacher-authored synthetic examples, not claimed model conclusions. Open Intelligence, choose **Demo · Reliable review**, and inspect the preserved finding or material. The seed does not alter grades or publish/send anything; `scripts/seed_intelligence_demo.py` reuses the existing local demo and preserves existing work.


## Local verification — 17 October 2026

- Complete backend regression: **58 passed, 2 optional model checks skipped**. Includes exact citations, cohort summary bounds, private access, version/approval guards, worker recovery, and the read-lock regression.
- Separate real Docker-worker check with the installed **llama3.2:1b**: analysis and revision-pack generation both succeeded with validated output, model digest and usage. Neither step created or published an assignment. The existing grading default remains gemma3:4b; each teaching run may explicitly choose an installed local model.
- The new Chrome journey passed through finding inspection/review, revision editing/export, approval to a draft, separate publication, and the protected student page. Student content excluded the private teacher key; mobile overflow passed. Desktop/mobile output was visually inspected.
- Production build, TypeScript/generated API types, Ruff, formatting, dependency checks and Alembic comparison passed. A synthetic manual walkthrough remains in the existing demo account.
- A concurrent inference/browser regression run exposed local resource pressure and legacy browser timeouts. Teaching inference now uses a smaller context/batch and bounded CPU threads; ordinary authenticated reads avoid unnecessary user UPDATE locks. Local CPU inference can still take minutes. Workflow checks do not establish educational accuracy or hardware throughput.

## Final handoff checks

After the final authentication pooling and narrowly scoped reviewer-export fix, **25 authentication/permission/teaching checks passed, with one optional live-model check skipped**. This includes assigned reviewer exports, denied reviewer mutations, student/workspace isolation, and all standard Phase 5 checks. The broader regression run passed **58 tests with two optional model checks skipped** before that narrowly scoped follow-up.

All four browser journeys were verified on the Phase 5 interface: signup/confirmation/themes, assessment review/revision/replacement release, score-based follow-up/private response, and teaching findings/revision-pack approval/publication. The legacy assessment journey was rechecked successfully after the transport/cache fixes; earlier loaded runs had timed out. The real local `llama3.2:1b` worker analysis and revision-generation check passed separately.

API 0.5.0 and the production web build remain running. Docker worker, scheduler, Redis and local Supabase remain available; local Ollama is running with short idle model retention. No production deployment, credential migration, real student data or external message delivery was performed.
