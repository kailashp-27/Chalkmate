"""Package source and documentation, excluding local dependencies, data and secrets."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = (
    "apps",
    "contracts",
    "docs",
    "evaluation",
    "infra",
    "scripts",
    "services",
    "supabase",
    ".github",
)
FILES = (
    "README.md",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    ".editorconfig",
    "alembic.ini",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "requirements.lock.txt",
)
SKIP = {
    "node_modules",
    ".next",
    ".venv",
    ".tmp",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "test-results",
    "playwright-report",
    ".git",
    ".temp",
    ".branches",
}


def source_files():
    for name in FILES:
        yield ROOT / name
    for name in FOLDERS:
        for path in (ROOT / name).rglob("*"):
            relative = path.relative_to(ROOT)
            if (
                set(relative.parts) & SKIP
                or path.is_symlink()
                or any(
                    getattr(parent, "is_junction", lambda: False)()
                    for parent in [path, *path.parents]
                )
            ):
                continue
            if (
                path.is_file()
                and not (
                    path.name.startswith(".env")
                    or path.suffix in {".pyc", ".log", ".tsbuildinfo"}
                    or path.name.endswith(".egg-info")
                )
                and not any(part.endswith(".egg-info") for part in relative.parts)
            ):
                yield path


def main():
    target = ROOT / ".tmp/releases"
    target.mkdir(parents=True, exist_ok=True)
    archive = target / "Chalkmate-local-source.zip"
    manifest = {}
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        for path in sorted(set(source_files())):
            relative = path.relative_to(ROOT).as_posix()
            content = path.read_bytes()
            bundle.writestr("Chalkmate/" + relative, content)
            manifest[relative] = hashlib.sha256(content).hexdigest()
        bundle.writestr("Chalkmate/SOURCE-MANIFEST.json", json.dumps(manifest, indent=2))
    with ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError("Source archive verification failed")
    print(
        f"Verified source archive: {archive} ({len(manifest)} files; no local data or credentials)"
    )


if __name__ == "__main__":
    main()
