# Local recovery and service readiness

The **Readiness** classroom tab now checks database access, sign-in, private files, Redis, optional local Ollama and a recent background-worker heartbeat. Dependency checks are bounded; explanations live behind info buttons. The recovery date shows the last successful local drill, not a continuous backup guarantee.

## Back up and rehearse

With Docker, local Supabase and the API running, use the installed Python environment from the repository root:

```powershell
.venv/Scripts/python.exe scripts/full_stack_recovery.py backup
.venv/Scripts/python.exe scripts/full_stack_recovery.py rehearse --cleanup
```

`backup` creates an owner-private signed bundle under `.tmp/backups/`. `rehearse` adds a synthetic confirmed account and private test document, captures the bundle, removes the synthetic source records, then restores into a separately named Supabase stack on different loopback ports. It verifies database table checksums and private-file hashes, signs in as the restored synthetic user, downloads the private file through the isolated application, and checks anonymous/unrelated-user denial. `--cleanup` removes only the generated recovery stack; the bundle and report remain. It never restores over the source stack.

To recheck a rehearsal bundle, substitute its actual directory:

```powershell
.venv/Scripts/python.exe scripts/full_stack_recovery.py drill .tmp/backups/BUNDLE_ID --cleanup
```

A plain `backup` bundle can verify table/file restoration, but has no synthetic password probe; use `rehearse` for the complete sign-in/download evidence.

Bundles contain private database records, Auth data and file bytes. They are access-restricted, **not encrypted**. Keep them off Git and protect any off-device copies. Retain `.tmp/recovery-secrets/signing.key` separately and securely alongside your backup process; verification never silently replaces a missing key. Tampered/missing/extra artifacts and unsafe linked paths are rejected. Losing this key prevents signed-bundle verification. For off-device recovery, preserve the project source/lockfiles, bundle, signing key and compatible local Docker images/tools; place the key back at that private path before a drill.

The bundle captures application schema/data, Auth/Storage data, the application migration marker, local Supabase configuration and the file-backed Storage volume. Supabase-managed migration ledgers are retained from the isolated compatible stack; exact source image identities/layout are checked. Database snapshots alone do not include uploaded file bytes; see the [Supabase backup documentation](https://supabase.com/docs/guides/platform/backups).

## Verified boundary

On 19 October 2026, the full rehearsal verified **76 tables and 4 private objects**, including restored email/password sign-in and private download, in approximately **89 seconds**. The isolated stack was cleaned up. Evidence is kept in ignored `.tmp/recovery-last-report.json`; Readiness exposes only its success/date.

This procedure targets the current default-port, local file-backed Supabase setup (tested with installed CLI 2.121). It regenerates target development keys and restricted-role passwords. It does not copy `.env` provider secrets, configure external OAuth/email providers, prove old-session continuity, or establish a production recovery SLA. Reconfigure local Ollama/provider settings separately when moving machines. Real teacher pilot quality/time measurements remain pending.

The 21 October local release repeated the full rehearsal with its new student-support schema: **77 tables and 4 private objects**, restored sign-in/download and access-denial checks all passed in approximately **88 seconds**. The generated stack was cleaned up. This supersedes the earlier rehearsal date in Readiness.
