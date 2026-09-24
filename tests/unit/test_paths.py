"""tests/unit/test_paths.py"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from artemis.infra.utils.paths import PathLayout


def test_root_paths(tmp_path: Path):
    p = PathLayout(tmp_path / ".artemis")
    assert p.root == tmp_path / ".artemis"
    assert p.db == tmp_path / ".artemis" / "artemis.db"
    assert p.logs_dir == tmp_path / ".artemis" / "logs"
    assert p.log == tmp_path / ".artemis" / "logs" / "artemis.log"
    assert p.config == tmp_path / ".artemis" / "config.json"


def test_log_dir_creation(tmp_path: Path):
    p = PathLayout(tmp_path / ".artemis")
    assert not (tmp_path / ".artemis" / "logs").exists()
    assert p.ensure_log() == tmp_path / ".artemis" / "logs" / "artemis.log"
    assert (tmp_path / ".artemis" / "logs").is_dir()
    assert p.log == tmp_path / ".artemis" / "logs" / "artemis.log"


def test_user_dir_uses_username(tmp_path: Path):
    p = PathLayout(tmp_path / ".artemis")
    assert p.user_dir("alice") == tmp_path / ".artemis" / "users" / "alice"


def test_agent_workspace(tmp_path: Path):
    p = PathLayout(tmp_path / ".artemis")
    ws = p.agent_workspace("agent01")
    assert ws == tmp_path / ".artemis" / "agents" / "agent01"


def test_ensure_root_creates_dir(tmp_path: Path):
    p = PathLayout(tmp_path / ".artemis")
    p.ensure_root()
    assert (tmp_path / ".artemis").is_dir()


def test_ensure_agent_workspace(tmp_path: Path):
    p = PathLayout(tmp_path / ".artemis")
    # New global path
    out = p.ensure_agent_workspace("a1")
    assert out.is_dir()
    assert out == tmp_path / ".artemis" / "agents" / "a1"


def test_backups_dir(tmp_path: Path) -> None:
    p = PathLayout(tmp_path / ".artemis")
    assert p.backups_dir == tmp_path / ".artemis" / "backups"
    assert p.ensure_backups_dir().is_dir()


def test_knowledge_dir(tmp_path: Path) -> None:
    p = PathLayout(tmp_path / ".artemis")
    assert p.knowledge_dir == tmp_path / ".artemis" / "knowledge"


def test_path_layout_from_env_defaults_to_dot_artemis(monkeypatch) -> None:
    monkeypatch.delenv("ARTEMIS_HOME", raising=False)
    assert PathLayout.from_env().root == Path.home() / ".artemis"


def test_path_layout_from_env_honors_artemis_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARTEMIS_HOME", str(tmp_path))
    assert PathLayout.from_env().root == tmp_path


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_runtime_directories_and_log_are_owner_only(tmp_path: Path) -> None:
    paths = PathLayout(tmp_path / ".artemis")

    runtime_dirs = (
        paths.ensure_root(),
        paths.ensure_logs_dir(),
        paths.ensure_agent_workspace("agent-1"),
        paths.ensure_backups_dir(),
        paths.ensure_ssl_dir(),
        paths.ensure_connector_cli_instance_dir("browser", "default"),
    )
    assert all(path.stat().st_mode & 0o777 == 0o700 for path in runtime_dirs)

    paths.ensure_log()
    assert paths.log.exists()
    assert paths.log.stat().st_mode & 0o777 == 0o600
