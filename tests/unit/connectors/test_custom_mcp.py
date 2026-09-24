"""Unit tests for the custom-MCP-only connector runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from artemis.config import ArtemisConfig
from artemis.infra.connectors.builder import build_mcp_server_configs_for_user
from artemis.infra.connectors.custom_mcp import CUSTOM_MCP_KIND, harness_spec_for_server
from artemis.infra.connectors.service import ConnectorService
from artemis.infra.db.migrate import run_migrations
from artemis.infra.db.pool import SqlitePool
from artemis.infra.db.repos.connectors import ConnectorRepo
from artemis.infra.db.repos.secrets import SecretRepo
from artemis.infra.db.repos.settings import SettingsRepo


@pytest.fixture
def db(tmp_path: Path) -> SqlitePool:
    pool = SqlitePool(tmp_path / "artemis.db")
    run_migrations(pool)
    return pool


@pytest.fixture
def svc(db: SqlitePool) -> ConnectorService:
    return ConnectorService(
        repo=ConnectorRepo(db),
        secret_repo=SecretRepo(db),
        settings_repo=SettingsRepo(db),
        config=ArtemisConfig(),
    )


def _user(db: SqlitePool) -> int:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES ('u', 'x', 'user', 1)"
        )
        row = conn.execute("SELECT id FROM users WHERE username = 'u'").fetchone()
    assert row is not None
    return int(row["id"])


def test_custom_mcp_runtime_config_deferred_until_chat(
    svc: ConnectorService, db: SqlitePool
) -> None:
    user_id = _user(db)
    svc.put_custom_servers(
        user_id,
        {"personal": {"transport": "streamable_http", "url": "https://mcp.example.com/mcp"}},
    )

    configs = build_mcp_server_configs_for_user(
        svc=svc,
        connector_repo=svc._repo,
        user_id=user_id,
        agent_id="A1",
        agent_user_id=user_id,
        config=ArtemisConfig(),
        log=False,
    )

    assert configs == {"personal": {}}
    assert svc.list_active_mcp_server_names(user_id) == ["personal"]
    assert svc.list_instances_for_api(user_id)[0]["kind"] == CUSTOM_MCP_KIND


def test_custom_mcp_harness_spec_keeps_user_connection_details() -> None:
    spec = harness_spec_for_server(
        {
            "transport": "streamable_http",
            "url": "https://mcp.example.com/mcp",
            "headers": {"X-Key": "secret"},
        }
    )
    assert spec["transport"] == "streamable_http"
    assert spec["headers"]["X-Key"] == "secret"
    assert spec["headers"]["Accept"] == "application/json, text/event-stream"
