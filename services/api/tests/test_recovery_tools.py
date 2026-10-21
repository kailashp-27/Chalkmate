"""Offline bundle integrity checks require no live database or Docker."""

import hashlib
import hmac
import json

import pytest

from scripts import full_stack_recovery as recovery


def test_signed_bundle_rejects_tampering_and_missing_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    monkeypatch.setattr(recovery, "signing_key", lambda create=False: b"x" * 32)
    folder = tmp_path / ".tmp/backups/sample"
    folder.mkdir(parents=True)
    (folder / "application.dump").write_bytes(b"synthetic archive")
    manifest = {"version": 1, "artifacts": recovery.artifacts(folder)}
    raw = recovery.canonical(manifest)
    (folder / "manifest.json").write_bytes(raw)
    (folder / "manifest.signature").write_text(hmac.new(b"x" * 32, raw, hashlib.sha256).hexdigest())
    assert recovery.load_bundle(folder)[1] == manifest
    (folder / "application.dump").write_bytes(b"changed archive")
    with pytest.raises(ValueError, match="missing or changed"):
        recovery.load_bundle(folder)
    (folder / "manifest.json").write_text(json.dumps({**manifest, "version": 2}))
    with pytest.raises(ValueError, match="signature"):
        recovery.load_bundle(folder)


@pytest.mark.parametrize(
    "path", ["../outside", "/absolute", "C:/file", "nested/../../outside", "bad\\path"]
)
def test_backup_paths_cannot_escape(tmp_path, path):
    with pytest.raises(ValueError):
        recovery.safe_path(tmp_path, path)


def test_missing_key_never_generates_a_replacement_on_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="signing key is missing"):
        recovery.signing_key()
    assert not (tmp_path / ".tmp/recovery-secrets/signing.key").exists()
