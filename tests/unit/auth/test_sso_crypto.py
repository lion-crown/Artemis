"""Tests for SSO secret encryption."""

from __future__ import annotations

from pathlib import Path

from artemis.infra.auth.sso.crypto import decrypt_secret, encrypt_secret
from artemis.infra.db.migrate import run_migrations
from artemis.infra.db.pool import SqlitePool
from artemis.infra.db.repos.secrets import SecretRepo


def test_sso_secret_round_trip_uses_its_own_fernet_key(tmp_path: Path) -> None:
    db = SqlitePool(tmp_path / "artemis.db")
    run_migrations(db)
    secret_repo = SecretRepo(db)

    encrypted = encrypt_secret(secret_repo, "sensitive value")

    assert decrypt_secret(secret_repo, encrypted) == "sensitive value"
    assert secret_repo.get("sso_fernet") is not None
    assert secret_repo.get("connector_fernet") is None
