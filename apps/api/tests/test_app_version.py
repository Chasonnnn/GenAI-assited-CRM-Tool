"""Tests for app version loading."""

import json

from app.core.config import Settings


def test_settings_version_reads_release_please_manifest(monkeypatch, tmp_path):
    manifest_path = tmp_path / ".release-please-manifest.json"
    manifest_path.write_text(json.dumps({".": "9.9.9"}), encoding="utf-8")

    monkeypatch.setenv("RELEASE_PLEASE_MANIFEST_PATH", str(manifest_path))
    monkeypatch.delenv("VERSION", raising=False)

    settings = Settings(
        ENV="test",
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
    )

    assert settings.VERSION == "9.9.9"


def test_settings_version_reads_release_please_version_key(monkeypatch, tmp_path):
    manifest_path = tmp_path / ".release-please-version.json"
    manifest_path.write_text(json.dumps({"version": "8.8.8"}), encoding="utf-8")

    monkeypatch.setenv("RELEASE_PLEASE_MANIFEST_PATH", str(manifest_path))
    monkeypatch.delenv("VERSION", raising=False)

    settings = Settings(
        ENV="test",
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
    )

    assert settings.VERSION == "8.8.8"
