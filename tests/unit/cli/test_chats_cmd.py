"""Tests for the `artemis chats` group."""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from artemis.cli.main import cli


def test_chats_group_help_lists_all_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["chats", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "get", "create", "update", "delete", "send", "repl"):
        assert sub in result.output


def test_chats_list_requires_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    import artemis.cli.support.ctx as ctx_mod

    def _missing(_agent: str | None) -> str:
        click.echo("error: --agent is required", err=True)
        raise SystemExit(2)

    monkeypatch.setattr(ctx_mod, "require_agent", _missing)
    runner = CliRunner()
    result = runner.invoke(cli, ["chats", "list"])
    assert result.exit_code == 2


def test_chats_list_uses_offline_db(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_list_threads_offline(**kwargs):
        captured.update(kwargs)
        return [{"thread_id": "t1", "title": "hi", "is_active": True}]

    from artemis.cli.support import db as db_mod

    monkeypatch.setattr(db_mod, "list_threads_offline", fake_list_threads_offline)
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "chats", "list", "--agent", "agent-1"])
    assert result.exit_code == 0, result.output
    assert captured["agent_id"] == "agent-1"


def test_chats_update_sends_title(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_update_thread_offline(agent_id, thread_id, *, title=None, pinned=None):
        captured["agent_id"] = agent_id
        captured["thread_id"] = thread_id
        captured["title"] = title
        return {"thread_id": thread_id, "title": title}

    from artemis.cli.support import offline_ops as offline_mod

    monkeypatch.setattr(offline_mod, "resolve_cron_user_id", lambda *_a, **_k: 1)
    monkeypatch.setattr(offline_mod, "update_thread_offline", fake_update_thread_offline)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["chats", "update", "abc", "--agent", "agent-1", "--title", "renamed"]
    )
    assert result.exit_code == 0
    assert captured["title"] == "renamed"
