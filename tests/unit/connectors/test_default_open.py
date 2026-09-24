"""Unit tests for connector default_open config helpers."""

from __future__ import annotations

from artemis.infra.connectors.default_open import (
    merge_mcp_servers_with_defaults,
    read_default_open,
)


def test_read_default_open_defaults_false():
    assert read_default_open(None) is False
    assert read_default_open({}) is False
    assert read_default_open({"default_open": False}) is False
    assert read_default_open({"default_open": "yes"}) is False


def test_read_default_open_true():
    assert read_default_open({"default_open": True}) is True


def test_merge_mcp_servers_with_defaults_unions_and_dedupes():
    # Default: apply defaults only when explicit is None (IM-style).
    assert merge_mcp_servers_with_defaults(None, ["a", "b"]) == ["a", "b"]
    assert merge_mcp_servers_with_defaults(["b", "c"], ["a", "b"]) == ["b", "c"]
    assert merge_mcp_servers_with_defaults(["x"], []) == ["x"]
    assert merge_mcp_servers_with_defaults(None, []) is None
    assert merge_mcp_servers_with_defaults([], []) is None
    # Cron-style force union.
    assert merge_mcp_servers_with_defaults(["b", "c"], ["a", "b"], apply_defaults=True) == [
        "b",
        "c",
        "a",
    ]


def test_merge_respects_dashboard_opt_out():
    # Explicit list (including empty) must not re-add defaults.
    assert merge_mcp_servers_with_defaults(["b"], ["a"], apply_defaults=False) == ["b"]


def test_merge_turn_mcp_servers_unions_extra_defaults() -> None:
    from artemis.infra.connectors.service import ConnectorService

    class _Svc:
        def list_default_open_mcp_server_names(self, _uid: int) -> list[str]:
            return ["always"]

        def list_active_mcp_server_names(self, _uid: int) -> list[str]:
            return ["always", "expert"]

    svc = _Svc()
    assert ConnectorService.merge_turn_mcp_servers(
        svc,  # type: ignore[arg-type]
        1,
        None,
        extra_defaults=["expert", "always", "gone", ""],
    ) == ["always", "expert"]
    assert (
        ConnectorService.merge_turn_mcp_servers(
            svc,  # type: ignore[arg-type]
            1,
            [],
            apply_defaults=False,
            extra_defaults=["expert"],
        )
        is None
    )
    assert merge_mcp_servers_with_defaults([], ["a"], apply_defaults=False) is None
    # IM / Cron force defaults.
    assert merge_mcp_servers_with_defaults([], ["a"], apply_defaults=True) == ["a"]
    assert merge_mcp_servers_with_defaults(None, ["a"], apply_defaults=True) == ["a"]
