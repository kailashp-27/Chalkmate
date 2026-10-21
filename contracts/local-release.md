# Local release completion

Finish the current local teacher workspace; optional institutional integrations, hosted deployment and claims requiring real teacher evidence remain outside this release.

## Review requests

Students may request a review of a specific question in their own latest released result while actively enrolled in an active classroom. Input pins the visible release timestamp. Unknown/unreleased/peer records are unavailable; stale releases conflict. One request per student/question/released decision, with a 10–2000 character explanation. Store the released decision and question label, preserving the original request. Teachers can respond once with a 10–2000 character explanation. Reviewers can inspect only. No request or response changes marks, triggers model calls, releases results or sends email. Response explains the teacher's action; actual re-evaluation uses the existing versioned workflow.

GET /v1/classrooms/{id}/review-requests lists staff-visible requests, or only the requesting student's own requests. POST /v1/classrooms/{id}/review-requests creates one. POST /v1/review-requests/{id}/resolve records a teacher response. Database clients have SELECT only; narrow identity-aware functions enforce creation/resolution, uniqueness and audit records.

## Overview

GET /v1/classrooms/{id}/overview is staff-only, returning aggregate review, unreleased approval, failed processing, open student request, overdue missing assignment response and scheduled/held message counts. Read only; no student contact or answer content. Assignment missing counts refer to active audience members of the latest published version of open assignments after their deadline. Missing means no response, never zero marks. UI cards navigate to existing tools; navigation does not mutate data.

## Local handover

Provide repeatable Windows start/stop/status scripts, preserving existing records, environment secrets and compatible running services. Stop only processes created/tracked by the launcher after verifying process identity. Capture Supabase startup output without printing credentials. Clear setup, teacher/student walkthrough, recovery instructions and release status separate implemented features from real pilot/provider prerequisites. Verify migrations, authorization, regression/browser flows and build; use synthetic accounts only.
