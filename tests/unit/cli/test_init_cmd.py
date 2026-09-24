"""Unit tests for `artemis init`."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from artemis.cli.main import cli


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    artemis_home = tmp_path / ".artemis"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARTEMIS_HOME", str(artemis_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    for key in list(os.environ):
        if key.startswith("ARTEMIS_DATABASE_"):
            monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_init_non_interactive_creates_admin(fake_home: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "init",
            "--admin-username",
            "alice",
            "--admin-password",
            "Wonderland1",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (fake_home / ".artemis").is_dir()
    assert (fake_home / ".artemis" / "artemis.db").is_file()
    weather = fake_home / ".artemis" / "plugins" / "weather" / "plugin.yaml"
    assert weather.is_file()
    cfg = json.loads((fake_home / ".artemis" / "config.json").read_text(encoding="utf-8"))
    assert cfg["plugins"]["weather"]["enabled"] is False

    from artemis.infra.db.pool import SqlitePool
    from artemis.infra.db.repos.users import UserRepo
    from artemis.infra.utils.paths import PathLayout

    paths = PathLayout(fake_home / ".artemis")
    db = SqlitePool(paths.db)
    row = UserRepo(db).get_by_username("alice")
    assert row is not None
    assert row.role == "admin"


def test_init_refuses_to_overwrite_without_force(fake_home: Path) -> None:
    runner = CliRunner()
    args = [
        "init",
        "--admin-username",
        "alice",
        "--admin-password",
        "TestPass12",
        "--yes",
    ]
    r1 = runner.invoke(cli, args)
    assert r1.exit_code == 0
    r2 = runner.invoke(cli, args)
    assert r2.exit_code != 0
    out = (r2.output + (r2.stderr if hasattr(r2, "stderr") else "")).lower()
    assert "already" in out or "exists" in out


def test_init_force_resets(fake_home: Path) -> None:
    if os.name == "nt":
        pytest.skip("Windows may lock SQLite during init force reset")
    runner = CliRunner()
    args_a = [
        "init",
        "--admin-username",
        "alice",
        "--admin-password",
        "TestPass12",
        "--yes",
    ]
    args_b = [
        "init",
        "--force",
        "--admin-username",
        "bob",
        "--admin-password",
        "TestPass34",
        "--yes",
    ]
    r1 = runner.invoke(cli, args_a)
    assert r1.exit_code == 0, r1.output or str(r1.exception)
    r2 = runner.invoke(cli, args_b)
    assert r2.exit_code == 0, r2.output or str(r2.exception)

    from artemis.infra.db.pool import SqlitePool
    from artemis.infra.db.repos.users import UserRepo
    from artemis.infra.utils.paths import PathLayout

    paths = PathLayout(fake_home / ".artemis")
    repo = UserRepo(SqlitePool(paths.db))
    assert repo.get_by_username("bob") is not None


def test_init_password_too_short_rejects(fake_home: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["init", "--admin-username", "a", "--admin-password", "abc", "--yes"],
    )
    assert result.exit_code != 0
    assert "password" in result.output.lower()


def test_init_env_vars_supply_credentials(fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTEMIS_ADMIN_USERNAME", "fromenv")
    monkeypatch.setenv("ARTEMIS_ADMIN_PASSWORD", "EnvPass12")
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--yes"])
    assert result.exit_code == 0, result.output

    from artemis.infra.db.pool import SqlitePool
    from artemis.infra.db.repos.users import UserRepo
    from artemis.infra.utils.paths import PathLayout

    paths = PathLayout(fake_home / ".artemis")
    repo = UserRepo(SqlitePool(paths.db))
    assert repo.get_by_username("fromenv") is not None
