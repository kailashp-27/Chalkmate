# Using Chalkmate

## Start and sign in

Open Docker Desktop, then run `./scripts/Start-Chalkmate.ps1` from this folder in PowerShell. Open the address it prints (normally port 3000; port 3001 when another project occupies 3000). Settings changes between dark, light and system appearance.

Create an account, then open **local email inbox** on the sign-in page. Local Supabase captures verification and password-reset messages there; they do not arrive in Gmail. Follow the verification link and sign in. Use **Forgot your password?** for account recovery. Invitations must be accepted by the intended verified account.

For the existing synthetic demonstration account, run `.venv/Scripts/python.exe scripts/create_demo_account.py` and open the private `.tmp/demo-credentials.json` file on your computer. Credentials are not part of the source handover.

## Teacher walkthrough

1. Create a workspace and classroom. In **Students**, download the roster template, import CSV/XLSX and check the preview before confirming. Invite students or reviewers from **People**.
2. In **Assessments**, create an assessment and rubric. Criteria must add up to each question's maximum. Activate the rubric, upload individual answer sheets and confirm student identity.
3. Review extraction and page/question mapping against the original scan. Typed PDFs can use embedded text. Scans can use your installed local Ollama vision model, or you can enter/correct text manually. Unreadable work is flagged for review.
4. Ask local Ollama for suggestions if desired. Review every criterion, provide reasons for changes, approve the result, then explicitly release it. Approval and release are separate. Rubric changes create new versions; re-evaluation preserves the previous release until you release its replacement.
5. **Overview** collects review tasks, approved results awaiting release, overdue assignment responses, scheduled/held messages and student review requests. Read a student's question request, use Assessments if a mark needs re-evaluation, then save a response explaining what you did. Saving a response alone never changes marks.
6. Use **Intelligence** to inspect evidence and topic patterns, review findings and draft remedial work or revision packs. Approving a pack creates an unpublished assignment; publication is separate.
7. In **Assignments**, publish to a reviewed audience and collect private responses. In **Follow-up**, preview the exact score rule, recipients, message and schedule before approval. Below 25 means strictly less than 25. Local messages appear in the local email inbox. Inspect uncertain delivery before retrying.
8. In **Planning**, approve syllabus sources before creating blueprints, banks or papers. Review solutions and citations. Marks templates define reusable CSV/Excel columns; prepare a snapshot before downloading. Bank/paper previews let you explicitly link questions to reviewed assessment performance.
9. Use **Readiness** to check local dependencies and worker health. Info icons explain controls on hover, focus or tap. Ctrl/Cmd K finds tools without changing records.

## Student walkthrough

Accept your invitation while signed in with the intended verified email. Open your classroom. **Assignments** shows work published to you and accepts your private response. **Results** shows only released feedback. Choose **Request a review**, select the question and explain your concern. Your teacher's response appears under **Your review requests**; the released result stays visible until a replacement is explicitly released.

## Stop and recover

`./scripts/Stop-Chalkmate.ps1` stops only the app processes created by the launcher. Add `-Services` to stop this project's worker/Redis and Supabase too; database/file volumes are preserved. `./scripts/Status-Chalkmate.ps1` reports app addresses.

For backup and a verified isolated restore, follow [local recovery](phase-nine.md). Backups contain private records and files; keep the signing key securely and separately. Source-code ZIPs do not contain your local database or credentials.

If Docker fails before startup, inspect Docker Desktop's own status. This machine previously had inaccessible stale Docker IPC sockets. No factory reset or volume removal is needed for the app; those actions can destroy data. If a port is occupied, the launcher does not stop the other project. If startup fails, check the private `.tmp/local/` logs, stop launcher-owned processes and retry.
