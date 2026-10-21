"""Refresh worker code using cached verified dependencies, or build them normally."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    ".env",
    "-f",
    "infra/compose.yaml",
    "--profile",
    "workers",
]


def main():
    # A code-only rebuild need not download a newer floating Python base image.
    # Use the existing project's image only when its exact dependency lock matches.
    try:
        cached = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "cat",
                "chalkmate-worker:latest",
                "/app/requirements.lock.txt",
            ],
            capture_output=True,
            timeout=30,
            cwd=ROOT,
        )
    except subprocess.TimeoutExpired:
        cached = None
    if (
        cached
        and cached.returncode == 0
        and cached.stdout.replace(b"\r\n", b"\n")
        == (ROOT / "requirements.lock.txt").read_bytes().replace(b"\r\n", b"\n")
    ):
        target = ROOT / ".tmp/local/Dockerfile.worker-cache"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "FROM chalkmate-worker:latest\n"
            "COPY services/api/src /opt/chalkmate-current\n"
            "ENV PYTHONPATH=/opt/chalkmate-current\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                "docker",
                "build",
                "--pull=false",
                "-f",
                str(target),
                "-t",
                "chalkmate-worker:latest",
                "-t",
                "chalkmate-scheduler:latest",
                ".",
            ],
            cwd=ROOT,
            check=True,
        )
        print("Worker source refreshed using matching cached dependency lock")
    else:
        subprocess.run([*COMPOSE, "build", "worker", "scheduler"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
