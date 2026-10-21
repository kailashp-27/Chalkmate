# Worker process

The Celery entry point is `chalkmate.worker:celery_app`, installed from the root
Python project. No separate dependency file or duplicate domain package exists.

Use `docker compose --env-file .env -f infra/compose.yaml --profile workers up -d --build`
from the repository root after starting local Supabase and running local setup
for the Linux worker on Windows. This also starts a separate Celery Beat dispatcher.
PostgreSQL job records provide durable state; Redis messages contain job IDs.
The worker uses a dedicated restricted database role, rechecks scope, and records
versioned extraction/proposal results. See `docs/phase-two.md` for recovery and
local Ollama configuration.
