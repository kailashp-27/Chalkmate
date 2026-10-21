"""Start local Supabase without emitting generated development credentials."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = ROOT / (
        "node_modules/.bin/supabase.cmd" if os.name == "nt" else "node_modules/.bin/supabase"
    )
    try:
        result = subprocess.run(
            [
                str(cli),
                "start",
                "--exclude",
                "realtime,studio,edge-runtime,logflare,vector,supavisor",
            ],
            cwd=ROOT,
            capture_output=True,
            timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SystemExit("Local Supabase startup did not finish; check Docker Desktop") from None
    if result.returncode:
        raise SystemExit("Local Supabase startup failed; check local Docker service health")
    print("Local Supabase started; development credentials were not logged")


if __name__ == "__main__":
    main()
