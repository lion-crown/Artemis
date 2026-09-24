"""tests/unit/test_cli_state.py"""

from __future__ import annotations

from pathlib import Path

from artemis.cli.support.state import CLIState, load, save


def test_load_missing_returns_default(tmp_path: Path) -> None:
    state = load(tmp_path / "nope.json")
    assert state.default_user is None
    assert state.default_agent is None


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    save(p, CLIState(default_user="alice", default_agent="a1"))
    out = load(p)
    assert out.default_user == "alice"
    assert out.default_agent == "a1"


def test_load_ignores_legacy_token_and_base_url(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text(
        '{"base_url": "http://h:9", "token": "legacy", "default_user": "u", "default_agent": "a"}'
    )
    out = load(p)
    assert out.default_user == "u"
    assert out.default_agent == "a"
