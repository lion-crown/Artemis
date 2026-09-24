"""Integration coverage for the custom-MCP-only connector surface."""

from __future__ import annotations

import pytest

from artemis.infra.connectors.custom_mcp import CUSTOM_MCP_KIND


@pytest.fixture
async def env(env_with_agent):
    yield env_with_agent


async def test_builtin_catalog_and_instance_creation_are_not_exposed(env) -> None:
    """Artemis must not ship a built-in connector catalog or its create API."""
    client, _server, auth, _agent_id = env

    catalog = await client.get("/api/connectors/catalog", headers=auth)
    create = await client.post(
        "/api/connector-instances",
        headers=auth,
        json={
            "kind": "tencent-docs",
            "display_name": "upstream connector",
            "credentials": {"token": "secret"},
        },
    )

    assert catalog.status_code == 404
    assert create.status_code == 405


async def test_custom_mcp_servers_can_be_saved_listed_and_selected(env) -> None:
    """Removing built-ins must not affect user-defined MCP configuration."""
    client, _server, auth, _agent_id = env
    server_spec = {
        "transport": "streamable_http",
        "url": "https://mcp.example.com/mcp",
        "display_name": "Personal MCP",
        "default_open": True,
    }

    saved = await client.put(
        "/api/connectors/custom-mcp",
        headers=auth,
        json={"servers": {"personal": server_spec}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["servers"]["personal"]["url"] == server_spec["url"]

    listed = await client.get("/api/connector-instances", headers=auth)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["kind"] == CUSTOM_MCP_KIND
    assert rows[0]["mcp_server_name"] == "personal"
    assert rows[0]["default_open"] is True

    patched = await client.patch(
        "/api/connectors/custom-mcp/servers/personal",
        headers=auth,
        json={"enabled": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["servers"]["personal"]["enabled"] is False
