# Teacher Assistant: Product and Technical Plan

Prepared: 16 October 2026

Working name: Teachora. The name is provisional; availability has not been checked.

## 1. Product goal and agreed scope

Build a polished personal product for teachers and professors that connects classroom records, assessment creation, AI-assisted evaluation, learning support, and everyday administration. This is intended for real use and iterative improvement, rather than a college-project demonstration.

The central workflow is: create a classroom, import students, prepare an assessment and rubric, upload answers, review AI suggestions, release approved results, identify learning gaps, assign remedial work, and communicate with the relevant students.

Email is the initial communication channel. WhatsApp is optional and does not block the product. Teachers retain control over marks, content publication, recipient selection, and outgoing communications.

Assumptions: start with English typed and handwritten short/medium descriptive answers; support PDF/JPEG/PNG uploads; use one subject and assessment format for initial validation; build a responsive website before native mobile apps. Mathematical derivations, diagrams, regional languages, and code-heavy answers require separate benchmarks before being advertised as supported.

## 2. Users, workspaces, and ownership

| Role | Main capabilities |
| --- | --- |
| Workspace owner | Manage workspace, teachers, policies, usage limits, and exports. A personal teacher workspace is the initial default. |
| Teacher | Manage assigned classes, students, assessments, rubrics, grading, published results, and communications. |
| Co-teacher/reviewer | Access explicitly assigned classes and review work according to permissions. |
| Student | View their own released feedback, receive assignments, submit work, and request re-evaluation. |

A student record can exist before a student creates an account. It contains a stable internal ID, institutional registration number, name, email, and class enrollment. Use verified invitation acceptance to link an account to that record; never let a student claim someone else's record merely by entering its email address.

Classrooms contain courses/subjects, academic terms, teachers, enrollments, assessments, assignments, and announcements. Distinguish a reusable student identity from its enrollment in a particular class and term. Teacher access follows membership and assignment, not just possession of a classroom URL.

## 3. Product modules

### A. Classroom and student records

- Create and archive classrooms; manage terms and subjects.
- Import CSV/XLSX rosters with a preview, required-column checks, duplicate detection, and invalid-email warnings.
- Maintain student profiles, enrollment status, contact changes, assessment history, feedback, and remedial assignment history.
- Track assignments as pending, submitted, late, excused, or missing; distinguish missing work from work scored zero.
- Invite students and co-teachers with scoped permissions.
- Keep drafts and unreleased grades invisible to students.

### B. Assessment and rubric studio

- Upload a syllabus, question paper, answer key, model solutions, and optional teaching material.
- Build a question-paper blueprint: total marks, question types, topic weights, intended difficulty, and learning outcomes.
- Generate questions within approved syllabus coverage; show source references where source material is used.
- Generate teacher solutions, student copies, rubrics, and marking checklists together.
- Check ambiguous wording, repeated questions, missing information, mark-total mismatches, and questions outside the chosen syllabus.
- Produce A/B paper variants for teacher review; do not claim measured equivalence until validated.
- Maintain a question bank with topic tags, usage history, and observed performance.
- Model question choices explicitly, such as "answer any three," and preserve subquestion marks and partial-credit rules.

### C. AI-assisted evaluation workspace

- Batch upload separate answer sheets; later support combined scanned bundles with teacher-confirmed splitting.
- Match sheets to students using teacher-confirmed registration numbers or QR identifiers; never silently trust OCR identity matching.
- Detect missing pages, duplicate uploads, wrong order, unreadable scans, and uncertain question boundaries.
- Display the original scan next to extracted text, rubric criteria, suggested marks, and feedback.
- Highlight uncertain text and let teachers correct extraction before grading.
- Produce marks criterion by criterion, including partial credit, missing points, and exact page/region evidence.
- Support calibration using a few teacher-marked examples per question, including full, partial, and low-credit responses.
- Provide both student-by-student and question-by-question review.
- Support anonymous review by hiding student identity in the marking view and excluding it from grading prompts where practical.
- Prioritize unreadable, ambiguous, inconsistent, and otherwise flagged answers in a review queue.
- Permit teacher overrides with a reason and preserve the original AI proposal.
- Calculate totals and validate score bounds in application code.
- Require explicit approval before results are released.

### D. Rubric changes and calibration

- Store immutable rubric versions, including criteria, weights, acceptable alternatives, rounding, and partial-credit rules.
- Store calibration examples as versioned question-specific inputs, separate from evaluation holdout samples.
- Save the rubric, prompt, model, calibration, and extraction versions used by each grading run.
- Editing an approved rubric creates a new version. Show which questions and answers may be affected.
- Generate a before/after comparison and teacher review tasks; do not overwrite released marks silently.
- Invalidate derived feedback and analytics for changed answers, then rebuild them from approved results.
- Require approval for revised released results and notify students only under a teacher-approved workflow.
- Do not automatically learn from every override. Let teachers promote suitable corrections into approved examples to avoid propagating mistakes.

### E. After-evaluation teaching support

- Produce individual feedback cards: strengths, rubric-specific omissions, topic gaps, and suggested next steps.
- Find common misconceptions with counts, representative anonymized evidence, and the number of assessed students as denominator.
- Separate topic difficulty from low performance caused by missing or unreadable submissions.
- Create class-level topic summaries with drill-down to the answers supporting a finding.
- Generate targeted remedial assignments grouped by diagnosed learning gaps, not just total score.
- Generate next-class revision packs: teaching outline, worked example, short activity, and exit quiz.
- Track remedial submission and compare later performance without presenting improvement as proof of causation.
- Allow students to request re-evaluation of a specific answer; show the full evidence and decision history to the teacher.

### F. Assignment and submission management

- Draft, review, publish, schedule, collect, and archive assignments.
- Support class-wide, selected-student, and topic-group assignments.
- Attach approved resources, rubrics, due dates, and allowed submission types.
- Match uploaded work against the roster and flag unidentified files.
- Show submission status, late work, pending review, and reminders already sent.
- Stop pending missing-submission reminders once the student submits or is excused.
- Support accessible printable versions and reusable templates.

### G. Communication and automation

- Import contact information from classroom records; select recipients by explicit rules.
- Prepare personalized email drafts for results, reminders, remedial work, and announcements.
- Preview the audience, mark condition, assessment, message, attachments/links, and planned send time.
- Send one private message per student and maintain a delivery ledger.
- Track provider acceptance, delivery, bounces, complaints, failures, and retries separately. Delivery is not proof of reading.
- Support scheduled sends with score/enrollment/submission rechecks before dispatch.
- Add a natural-language command box after structured workflows are reliable.
- Add recurring rules only when teachers explicitly enable them, with scopes, limits, expiry, and a pause control.
- Later support teacher mailbox sending through Gmail/Microsoft OAuth. The initial sender is the app's verified domain with an appropriate teacher reply-to address.

### H. Everyday teaching administration

- Export approved marks as CSV/XLSX using saved department-specific column templates.
- Export feedback and printable assignment/report documents.
- Draft teaching logs and course reports from actual recorded activities and approved results.
- Convert supplied meeting notes/transcripts into decisions, actions, and deadlines.
- Draft and translate announcements for teacher review.
- Offer a dashboard of grading tasks, unreadable sheets, missing submissions, scheduled messages, and pending re-evaluations.
- Later add course-outcome reports when outcome mappings and institution-specific formulas are defined and reviewed.

## 4. Exact design for "send remedial work to students below 25"

Example command: "For Class A, CAT 1, send the approved recursion remedial assignment to students who scored below 25 out of 50."

1. Resolve Class A, CAT 1, the assessment maximum, and the approved assignment. Ask for clarification only if the actual selection is ambiguous.
2. Convert the command into a validated rule: classroom ID, assessment ID, approved score version, operator `<`, threshold `25`, maximum `50`, enrollment status, and assignment version.
3. Query authoritative classroom and grade records. The AI does not calculate eligibility or invent email addresses.
4. Include approved totals below 25. Exclude exactly 25, missing/unapproved scores, withdrawn students, and records outside the selected classroom. Show absent/ungraded students separately.
5. Preview matching students and unresolved email records. Example: 12 eligible students; 11 contactable; 1 missing email. The teacher can correct or exclude the unresolved record.
6. Create or select an approved remedial assignment. Preview the message using one student's private data at a time.
7. Obtain the teacher's send action. Save an immutable campaign snapshot containing recipients, rule, score versions, assignment version, message content, and approval.
8. Write an outbox event in the same database transaction as campaign creation. A dispatcher queues delivery jobs from this durable record.
9. Before a scheduled message is sent, recheck access, membership, eligibility, and data versions. If a relevant mark/content/contact change invalidates approval, hold or skip that item and request renewed review. Do not silently add newly eligible students.
10. Send individual emails. Prefer a sign-in-protected assignment link; optional PDF attachments and marks in the body are teacher-selected. Never expose other students' scores or addresses.
11. Store campaign/student/content-version uniqueness, delivery attempts, provider message IDs, and signed webhook events. Use provider idempotency keys for retries within its supported window.
12. If the provider may have accepted a message but the worker lost the response, reconcile it before retrying. Do not blindly resend uncertain requests after the provider's idempotency window expires.
13. Show delivered, failed, bounced, held, and skipped counts; enable scoped retries for confirmed failures.

Use strict numeric operators. "Below 25" means `<25`; "25 and below" means `<=25`. Percentages must be explicit. Do not mix scores from different assessment maxima without a teacher-selected normalization rule.

## 5. Recommended technology stack

| Layer | Initial choice | Purpose and reason |
| --- | --- | --- |
| Web application | Next.js, React, TypeScript | Responsive teacher and student portals; typed interfaces and routing. |
| UI system | Tailwind CSS, shadcn/ui | Consistent forms, tables, dialogs, navigation, and accessible interaction patterns. Verify accessibility in the assembled UI. |
| Client data/forms | TanStack Query, React Hook Form, Zod | Server state, validated forms, mutations, and reusable filter controls. |
| Scan viewer | PDF.js/react-pdf | Page navigation, zoom, text/region overlays, and side-by-side review. |
| Charts | Recharts | Class performance and topic summaries, with tabular alternatives. |
| Backend | Python FastAPI, Pydantic | Central business rules, document processing orchestration, validation, and APIs. |
| Database | Managed PostgreSQL through Supabase | Relational student/class/assessment data, transactions, version history, and structured JSON metadata. |
| Database access | SQLAlchemy, Alembic | Explicit relational models and one version-controlled migration history. |
| Authentication | Supabase Auth | Managed login, invitation flows, and account recovery. Authorization remains an application responsibility. |
| File storage | Private Supabase Storage buckets | Scans, source documents, and generated exports; short-lived authorized downloads. |
| Background jobs | Celery with Redis-compatible broker | OCR, evaluation, exports, reminders, and retryable email jobs outside request lifetimes. PostgreSQL remains the durable job/business record. |
| Initial OCR candidate | Azure AI Document Intelligence Read | Handwritten and printed extraction with locations and confidence signals; benchmark on actual answer sheets. |
| Initial multimodal model candidate | Gemini through its official Python SDK | Image-aware evaluation and structured suggestions; compare against another current provider on the same held-out data before choosing the production model. |
| AI abstraction | Small Python provider interface with Pydantic outputs | Switch model providers without changing classroom/grading business logic. Pin tested model and prompt versions. |
| Retrieval, when needed | PostgreSQL full-text search; pgvector for semantic retrieval | Find relevant teacher-approved syllabus/lecture material for grounded generation. No separate vector database initially. |
| Email | Resend API | Transactional email, delivery webhooks, and idempotency support. Use a verified sending domain. |
| Exports | openpyxl, python-docx, ReportLab | XLSX marks, editable Word documents, and PDF reports. |
| Deployment | Vercel for web; Render for API, workers, scheduler, and Redis-compatible service | Separate responsive UI from persistent background processing. Use managed Supabase for database/auth/storage. |
| Monitoring | Sentry, structured logs, usage records; OpenTelemetry as needed | Trace failures and spending without logging raw student work by default. |
| Development and delivery | GitHub, Docker Compose, GitHub Actions, pytest, Playwright | Reproducible local setup, checks, integration tests, and browser workflow verification. |

Use a modular monolith: one backend codebase with clear domain modules, deployed as API and worker processes. Next.js handles the web experience; FastAPI owns business operations. Avoid implementing grading or messaging rules twice in Python and TypeScript.

The Vercel AI SDK is a good option for TypeScript-owned AI features, but is not required for this Python-owned processing pipeline. Do not add it solely to duplicate model calls across services.

PostgreSQL is preferred over MongoDB here because enrollments, scores, versions, recipient selection, and approvals depend heavily on relationships and transactions. Use JSONB for model outputs and extraction metadata where appropriate.

## 6. Architecture and processing boundaries

```mermaid
flowchart TD
    Web["Next.js portals"] --> API["FastAPI: permissions and business rules"]
    Auth["Supabase Auth"] --> API
    API --> DB["PostgreSQL: records, versions, outbox"]
    API --> Files["Private file storage"]
    DB --> Dispatch["Outbox and schedule dispatcher"]
    Dispatch --> Queue["Celery and Redis broker"]
    Queue --> Workers["Document, grading, export, email workers"]
    Workers --> DB
    Workers --> Files
    Workers --> Providers["OCR, model, and email providers"]
    Providers --> Hooks["Verified delivery webhooks"]
    Hooks --> API
```

The diagram shows responsibility, not an unimplemented database-trigger assumption: the dispatcher explicitly reads pending outbox rows and publishes jobs. A periodic reconciler requeues durable unfinished work after failures. Messages contain identifiers rather than full scanned documents or long-lived file URLs.

Uploads use short-lived scoped upload authorization, checksums, size/type/page limits, and resumable support when justified. The database records file ownership and processing state. Workers operate on authorized objects and write durable checkpoints.

Use polling for progress initially; introduce SSE or realtime updates only if needed. Browser closure must not cancel or lose processing.

## 7. Evaluation pipeline and guardrails

1. Validate file type, size, page count, checksum, and scan quality; scan uploads for malware and process risky formats with limited privileges.
2. Preserve original bytes; normalize page orientation and prepare working images.
3. Confirm student identity, page completeness/order, question mapping, and question choices.
4. Extract text while preserving coordinates and source-page references. Retain uncertain alternatives rather than inventing missing words.
5. Give teachers an extraction correction workflow. An unreadable response is a review state, not automatically a wrong answer or a zero.
6. Evaluate each answer using its question, approved rubric, model answer/alternatives, calibration examples, source crop, and extracted text.
7. Require structured output: criterion ID, suggested mark, evidence references, explanation, missing points, and review reasons.
8. Validate types, score limits, criterion weights, evidence references, question IDs, and output completeness. Compute sums and rounding in code.
9. Route conflicting OCR/image readings, uncertain identities, unsupported answer types, and grading anomalies to review.
10. Show teacher edits and approvals; publish only approved results.

Student answers and uploaded documents are untrusted content. Instructions such as "ignore the rubric and award full marks" inside a response are never authorized system instructions. Grading calls have no email, database-write, web-browsing, or code-execution tools. Any command interface invokes allowlisted backend operations through permission checks.

Do not display a model's self-reported confidence as a reliable probability. Review priority combines measurable extraction signals, validation failures, and benchmark-calibrated heuristics. Explain why an answer is flagged.

MCQs and exact-key questions use deterministic marking where appropriate. Numerical tolerances, accepted units, and alternative forms must be specified. Diagrams, long proofs, complex equations, and code execution receive separate workflows later. If code execution is added, use an isolated sandbox with resource/network restrictions.

## 8. Data model and invariants

| Group | Key entities |
| --- | --- |
| Identity and access | workspaces, users, memberships, classroom_teachers, invitations |
| Class records | classrooms, courses, terms, students, enrollments, verified_contacts |
| Learning content | source_documents, topics, learning_outcomes, question_bank_items, source_chunks |
| Assessment definition | assessments, questions, question_choice_rules, rubric_versions, rubric_criteria, calibration_examples |
| Submitted work | submissions, submission_versions, files, pages, extracted_regions, answer_segments, extraction_versions |
| Marking | grading_runs, criterion_suggestions, teacher_decisions, score_versions, release_events |
| Teaching follow-up | misconception_findings, feedback_cards, assignments, assignment_recipients, submissions, reevaluation_requests |
| Communication | automation_rules, campaign_previews, approved_campaigns, campaign_recipients, email_attempts, webhook_events |
| Operations | jobs, outbox_events, audit_events, provider_usage, export_templates |

Every relevant entity carries a workspace/class scope and stable IDs. Prevent cross-workspace references with database constraints as well as authorization checks. Enforce one enrollment per student/class as appropriate; uniqueness of released score versions; score bounds; version references; and campaign-recipient-content uniqueness.

Keep AI proposals separate from teacher decisions and released marks. Editing text creates a new extraction version and invalidates dependent grading proposals. A rubric/model/prompt change creates new results rather than rewriting old history.

Store marks with fixed-precision numeric types, not binary floating point. Record a policy for rounding, question choices, absent/excused status, and changed totals.

## 9. States and failure recovery

Submission processing: uploaded -> validating -> identity/question review when needed -> extracting -> extraction review when needed -> grading -> teacher review -> approved -> released. Jobs may be retryable-failed, permanently-failed, or canceled without losing the last valid checkpoint.

Campaign processing: draft -> previewed -> approved -> scheduled/queued -> sending -> completed/partially-failed. Relevant data changes may move individual recipients to held/skipped. Cancellation stops unsent jobs; it cannot retract emails already accepted by the provider.

Re-evaluation: requested -> assigned -> under review -> decision recorded -> revised result released when applicable.

Use idempotent jobs, bounded retries with backoff, provider rate limits, timeouts, unique keys, reconciliation, and a failed-job review screen. Celery delivery alone is not an exactly-once guarantee. Redis is not the sole record of unfinished work.

## 10. Security, privacy, and operational quality

- Verify session tokens on the backend and enforce role/class/student access on every operation.
- Add database row-level security and private storage policies as defense in depth. Supabase service-role keys and privileged database roles bypass normal protections; never expose them to browsers or use them as the default for user-scoped operations.
- SQLAlchemy connections do not automatically inherit a Supabase user's JWT context. Configure a non-bypass application role and transaction-scoped validated identity context for RLS, and test it. A privileged worker path needs explicit scoped authorization.
- Students see only their own released work and assigned content. Co-teachers see only assigned classes.
- Use short-lived storage URLs; assignment access in emails uses an authenticated application route. Avoid emailing reusable raw storage URLs.
- Encrypt transport, manage secrets server-side, and redact logs. Restrict production access.
- Define retention and deletion policies for scans, extracted text, exports, model inputs, and backups; document delayed backup expiry rather than promising immediate erasure everywhere.
- Review provider data handling, retention, training settings, regional processing, and institutional requirements before using real student work. Use consented/anonymized test data during development.
- Verify email webhook signatures; handle duplicate and out-of-order events.
- Set spending caps, per-teacher quotas, upload limits, and provider concurrency limits.
- Back up data and test restoring it. Use separate development, staging, and production environments.
- Include keyboard support, readable contrast, text alternatives to charts, and responsive layouts.

## 11. Validation and release gates

Before building the entire AI experience, collect approximately 30-50 consented/anonymized answer sheets from the first intended subject, with varied handwriting and scan conditions. Aim for a few hundred labeled answers. These are planning sample sizes, not evidence of universal reliability. Keep calibration samples separate from a held-out test set; double-mark a subset to understand human disagreement.

Measure extraction character/word error on transcribed samples, wrong student/question matches, mean absolute grading error, error normalized by question maximum, agreement within teacher-defined tolerance, severe over/under-marking, review rate, review time, latency, and cost. Report by supported answer type and scan quality, not only one average.

Provisional pilot targets, to agree with participating teachers: no silent identity mismatches; every mark traceable to a rubric version; at least 90% of held-out supported descriptive answers within 10% of question maximum; every error beyond 20% separately investigated; and at least 30% reduction in total teacher review time at acceptable quality. These are targets, not current results or an automatic publication guarantee. Compare model agreement against human inter-marker agreement.

| Test area | Meaningful checks |
| --- | --- |
| Score rules | Partial marks, bounds, rounding, optional questions, absence, and changed maxima. |
| Eligibility | 24.5 included, 25 excluded, 25.5 excluded for `<25`; unapproved/missing/withdrawn records excluded. |
| Access isolation | Teacher in another workspace and student requesting a peer's records are denied at API and database layers. |
| Versioning | Rubric/extraction changes generate new proposals, preserve old approvals, and invalidate stale campaigns. |
| Recovery | Worker crash after OCR/grading/email acceptance; no lost jobs or blind duplicate sends. |
| Communication | Personalized private content, missing contacts, invalid emails, verified duplicate/out-of-order webhooks. |
| AI robustness | Unreadable text, blank answers, alternative valid solutions, injection attempts, invented evidence, malformed outputs. |
| Full browser journey | Roster -> upload -> review -> approve -> release -> filter -> email -> student submission -> re-evaluation. |
| Realistic batch | A 60-paper batch with progress, cancellation, rate limits, partial failures, and cost tracking. |

Use pytest for backend rules/integrations, Playwright for complete user journeys, and a versioned offline evaluation suite for OCR/model/rubric changes. Do not rely on ordinary unit tests to establish grading quality.

## 12. Phased implementation roadmap

| Phase | Work and deliverable | Completion gate | Estimated focused effort |
| --- | --- | --- | --- |
| 0. Discovery and feasibility | Confirm one subject, collect samples, benchmark OCR + image-aware grading, prototype the review screen. | Evidence supports a useful workflow and exposes unsupported cases. | 20-30 hours |
| 1. Product foundation | Design system, auth, workspace/classrooms, roster import, student identity, storage, CI, audit/permission foundations. | Two teachers/classes are isolated; roster import is reliable. | 35-50 hours |
| 2. Evaluation foundation | Assessments, manual rubric editor, uploads, mapping, extraction review, structured proposals, criterion review, release, marks export. | One class can complete a supported assessment with traceable marks. | 55-80 hours |
| 3. Reliable review | Rubric builder, calibration, question review, versioned rubric changes, review queue, feedback cards, re-evaluation. | Changed rubric produces a reviewable diff and preserved history. | 35-55 hours |
| 4. Classroom follow-up | Student portal, assignment publishing/submission, score filters, email preview/send, delivery ledger, scheduled reminders. | The below-25 workflow works end to end with boundary and recovery tests. | 35-55 hours |
| 5. Teaching intelligence | Evidence-based misconception findings, topic summaries, remedial assignment generation, revision packs. | Teacher can inspect findings and approve the generated follow-up work. | 40-60 hours |
| 6. Planning and administration | Syllabus-grounded generation, blueprints, question bank/variants/checker, report templates, meeting notes, translations, command box. | Generated material and commands remain reviewable and permission-scoped. | 30-50 hours |
| 7. Pilot and polish | Real teacher pilot, benchmarks, accessibility, failure recovery, performance, cost controls, restore drill, documentation. | Pilot quality/time targets and security/recovery checks are met. | 35-60 hours |

These sum to about 285-440 focused hours before contingency. Reserve approximately 300-500 hours overall; at 20 hours/week that is roughly 15-25 weeks. The first useful narrow pilot may be possible in 7-10 weeks, depending on sample availability and OCR quality. These are planning estimates for a solo builder assisted by AI, not deadlines or reliability promises.

The phase boundaries organize delivery; all accepted capabilities remain in the product scope. Advanced answer types and optional integrations follow their own evidence and permission requirements.

## 13. Initial repository and development approach

Use one Git repository with directories for `apps/web`, `services/api`, `services/worker`, `contracts`, `evaluation`, `infra`, and `docs`. The API and worker share the same Python domain package and dependency versions. Generate the TypeScript API client from the backend OpenAPI schema to reduce contract drift.

Use one database migration authority (Alembic); keep schema, access policies, and grants in reviewable migrations. Use Docker Compose locally for services that need containers, with Redis/Celery running in Linux containers on Windows. Keep a `.env.example` containing variable names and safe placeholders only.

First implementation sequence: write domain/state/permission contracts; create the representative sample set; build a vertical workflow from roster to one released assessment; validate the hard AI assumptions; then expand modules. Commit working increments and retain a demo dataset containing no real student personal data.

## 14. Costs and spending controls

Do not promise that this product will remain free. A paid API/worker/database/email setup and variable OCR/model usage may be required. Check current provider prices and terms before provisioning. No subscription, deployment, or purchase is authorized merely by this plan.

For each class batch calculate:

`batch cost = OCR pages x OCR page rate + model input/output/image charges + export/storage/egress charges + email charges + retry/regrading overhead`.

Illustration of volume, not price: 60 papers x 10 pages means 600 OCR pages; 60 papers x 10 answers means 600 answer evaluations before retries, calibration, and regrading. Shared source/rubric preparation should be cached, not repeated unnecessarily.

Track fixed monthly hosting separately from per-batch processing. Measure cost per answer, per paper, per class, and per teacher. Show estimated batch cost before a large run; set per-run and monthly caps; cache by content/rubric/model version; reprocess only changed or failed work; and benchmark a cheaper model only when its quality is acceptable. Do not silently switch grading models during an assessment without recording and evaluating the change.

## 15. Scope boundaries and future options

Initial supported scope prioritizes reliable English assessment review, classroom records, email follow-up, and teacher-approved generation. Native mobile apps, personal WhatsApp/group automation, unattended final grading, high-stakes exam certification, and universal handwriting accuracy are not initial release claims.

Future options include institution SSO, Google Classroom/Microsoft Teams/LMS integrations, mailbox OAuth, optional WhatsApp business integration, advanced math/diagram/code assessment, multilingual benchmarks, and institution reporting. Similarity analysis may support human review, but do not label students as cheating or claim reliable AI-writing detection.

Success means teachers can finish the complete assessment-to-support workflow faster, inspect the evidence behind AI suggestions, and correct the system without losing history.

## 16. Official technical references

The architecture choices above are recommendations; provider capabilities below were checked against official documentation on 16 October 2026. Model availability, supported formats/languages, pricing, and service terms must be checked again during implementation.

- Supabase PostgreSQL row-level security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase private storage and signed URLs: https://supabase.com/docs/guides/storage/buckets/fundamentals
- Azure Document Intelligence Read: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/read?view=doc-intel-4.0.0
- Gemini image understanding: https://ai.google.dev/gemini-api/docs/image-understanding
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Celery task reliability: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- FastAPI background tasks and heavier processing: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Render background workers: https://render.com/docs/background-workers
- Render Redis-compatible Key Value: https://render.com/docs/key-value
- Resend idempotency keys: https://resend.com/docs/dashboard/emails/idempotency-keys
- Resend domain verification: https://resend.com/docs/add-a-domain
