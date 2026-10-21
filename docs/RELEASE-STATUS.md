# Local release status — 21 October 2026

This is the current local implementation and handover, not a hosted production deployment. The original proposal is preserved as reference in `product-and-technical-plan.md`; later user decisions selected local Docker Supabase and local Ollama.

| Area | Current local release |
| --- | --- |
| Accounts and classrooms | Verified sign-in/recovery, workspaces, classroom archive/restore, CSV/XLSX roster preview, scoped student/reviewer invitations, private resources and audit records |
| Assessment | Rubric versions/criteria, individual answer-sheet upload and identity confirmation, extraction correction, local suggestions/manual grading, review queues/calibration, approval/release and replacement history |
| Student support | Private released feedback, question-specific review requests, preserved teacher replies and separate re-evaluation workflow |
| Follow-up | Versioned assignment publication, private/late responses, score-bound recipient previews, explicit communication approval, durable local email capture, schedules and delivery recovery |
| Teaching intelligence | Evidence-backed findings, topic summaries, reviewed remedial/revision drafts and unpublished assignment conversion |
| Planning | Approved syllabus text, blueprint/paper/bank/variant drafts, checks/citations, meeting notes, translation, recorded-data reports and navigation commands |
| Reporting | Reusable approved CSV/Excel marks templates, immutable previews, explicit bank-question performance links/history |
| Operations | Classroom task overview, service/worker readiness, bounded durable jobs, current-local Auth/database/private-file recovery, CI definition, start/stop/status scripts and source packaging |
| Interface | Black/blue and light/system appearance, mobile layout, concise labels, accessible help/dialogs, finite animation and reduced motion |

## What still requires evidence or configuration

- **Real teacher pilot:** choose the subject, collect consented held-out work and teacher reference marks, measure correction/review time, investigate severe errors, and run the supplied evaluation tooling. Synthetic tests do not prove handwriting/grading accuracy or time savings. The original Phase 0 feasibility and Phase 7 real-pilot gates are not satisfied by code alone.
- **Public production use:** choose hosting/domain/accounts, configure managed Auth/private storage and verified external sender, install malware scanning and isolated document processing, agree retention/account deletion/quotas, configure production monitoring, and run a production-specific security/recovery review. Current file validation parses supported formats but is not malware scanning. External email is disabled locally; no paid resources have been provisioned.
- **Broader optional capabilities:** combined-bundle splitting, geometric OCR confidence/region overlays, advanced optional/subquestion paper structures, individual assignment excusal and timed publication, recurring teacher rules, mailbox OAuth, LMS/SSO, outcome formulas, native mobile apps, WhatsApp and advanced subject/language support are not advertised as implemented. Some are later options in the original proposal; they need explicit product choices and/or provider access.
- **Remote CI:** the workflow is included; a successful hosted run is not claimed before the repository is pushed and CI actually runs.

Read [the user guide](USER-GUIDE.md) for normal operation and [verification](release-verification.md) for checks actually run on this release. Source archive creation omits dependencies, private data, `.env`, backups and credentials. Local data needs its own backup.
