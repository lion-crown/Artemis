"""tests/integration/test_experts_api.py — expert catalog endpoints.

Covers list / detail / one-click create. Uses the bundled library that
ships with the package (``src/artemis/experts/library/``) so the data
shape matches production exactly.
"""

from __future__ import annotations

from typing import Any


async def test_list_experts_returns_bundled_library(env: Any) -> None:
    c, _srv, auth = env
    r = await c.get("/api/experts", headers=auth)
    assert r.status_code == 200
    rows = r.json()
    ids = {row["id"] for row in rows}
    # The bundled library lists ``general-assistant``; ``default`` is hidden from the list API.
    assert "general-assistant" in ids
    assert len(rows) >= 1
    sample = next(r for r in rows if r["id"] == "general-assistant")
    assert "label" in sample and "zh" in sample["label"] and "en" in sample["label"]
    assert sample["task_examples"]["zh"]
    assert len(sample["task_examples"]["zh"]) == 3


async def test_get_expert_includes_prompt_files(env: Any) -> None:
    c, _srv, auth = env
    r = await c.get("/api/experts/default", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "default"
    assert body["files"]
    assert isinstance(body["prompt_files"], list)
    assert body["prompt_files"]


async def test_get_unknown_expert_404(env: Any) -> None:
    c, _srv, auth = env
    r = await c.get("/api/experts/this-id-does-not-exist", headers=auth)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


async def test_expert_market_endpoints_are_not_available(env: Any) -> None:
    """SkillHub market experts are not part of the local expert catalog."""
    c, _srv, auth = env

    response = await c.get("/api/experts/hub", headers=auth)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_create_agent_from_expert(env: Any) -> None:
    """One-click create from /api/agents/from-expert/{id}.

    The new agent should:
      - exist in /api/agents
      - not copy expert markdown into ``system_prompt`` (persona lives in workspace)
      - be in a non-running state (autostart=False; no provider)
    """
    c, _srv, auth = env

    r = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "default-bot"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["expert_id"] == "default"
    assert body.get("user_id") == 1
    assert body["state"] in {"running", "failed", "stopped", "unknown", "starting"}
    new_id = body["agent_id"]

    # Listed under /api/agents
    rows = (await c.get("/api/agents", headers=auth)).json()
    created = next(a for a in rows if a["agent_id"] == new_id and a["name"] == "default-bot")
    assert created["user_id"] == 1
    assert any(a["agent_id"] == new_id and a["name"] == "default-bot" for a in rows)

    detail_row = (await c.get(f"/api/agents/{new_id}", headers=auth)).json()
    assert detail_row["name"] == "default-bot"
    assert detail_row.get("system_prompt") in (None, "")


async def test_create_agent_from_expert_duplicate_name_409(env: Any) -> None:
    c, _srv, auth = env
    first = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "same-name-bot"},
    )
    assert first.status_code == 201, first.text

    second = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "same-name-bot"},
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "AGENT_NAME_TAKEN"


async def test_create_agent_from_unknown_expert_404(env: Any) -> None:
    c, _srv, auth = env
    r = await c.post(
        "/api/agents/from-expert/no-such-thing",
        headers=auth,
        json={"name": "foo"},
    )
    assert r.status_code == 404


async def test_create_agent_from_expert_with_provider_config(env: Any) -> None:
    """Optional providers land in config; default_model is stored on the agent row."""
    c, _srv, auth = env
    r = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={
            "name": "configured-default",
            "providers": ["my-openai"],
            "default_model": "openai:gpt-4o-mini",
        },
    )
    assert r.status_code == 201


async def test_create_agent_from_expert_mounts_skill_packages(env: Any) -> None:
    c, _srv, auth = env
    package_ids = [
        (
            await c.post(
                "/api/skill-packages",
                headers=auth,
                json={"name": name},
            )
        ).json()["id"]
        for name in ("Office", "Engineering")
    ]

    created = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "packaged-expert", "skill_package_ids": package_ids},
    )

    assert created.status_code == 201, created.text
    mounted = await c.get(
        f"/api/agents/{created.json()['agent_id']}/skill-packages",
        headers=auth,
    )
    assert mounted.status_code == 200, mounted.text
    assert mounted.json()["package_ids"] == package_ids
    assert [package["id"] for package in mounted.json()["packages"]] == package_ids


async def test_create_agent_from_expert_rejects_unknown_package_before_creation(env: Any) -> None:
    c, _server, auth = env
    agents_before = (await c.get("/api/agents", headers=auth)).json()

    created = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "missing-package-expert", "skill_package_ids": ["MISSING"]},
    )

    assert created.status_code == 404, created.text
    assert created.json()["error"]["code"] == "SKILL_PACKAGE_NOT_FOUND"
    agents_after = (await c.get("/api/agents", headers=auth)).json()
    assert {agent["agent_id"] for agent in agents_after} == {
        agent["agent_id"] for agent in agents_before
    }


async def test_get_expert_includes_file_contents(env: Any) -> None:
    c, _srv, auth = env
    r = await c.get("/api/experts/default", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "file_contents" in body
    assert isinstance(body["file_contents"], list)
    assert len(body["file_contents"]) > 0
    first = body["file_contents"][0]
    assert "name" in first and "content" in first
    assert isinstance(first["content"], str) and first["content"]


async def test_get_expert_file_contents_limited_to_preview_paths(env: Any) -> None:
    c, _srv, auth = env
    r = await c.get("/api/experts/stock-assistant", headers=auth)
    assert r.status_code == 200
    body = r.json()
    names = {item["name"] for item in body["file_contents"]}
    assert names == set(body["prompt_files"]) | {
        f for f in body["files"] if f.startswith("skills/")
    }
    assert "skills/stock-info/SKILL.md" in names
    assert "manifest.json" not in names


async def test_create_from_expert_stores_icon_color(env: Any) -> None:
    c, _srv, auth = env
    expert = (await c.get("/api/experts/default", headers=auth)).json()
    r = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "icon-color-agent"},
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]
    rows = (await c.get("/api/agents", headers=auth)).json()
    agent = next(a for a in rows if a["id"] == agent_id)
    assert agent["icon_name"] == expert.get("icon_name")
    assert agent["color"] == expert.get("color")


async def test_create_from_expert_stores_default_model(env: Any) -> None:
    c, _srv, auth = env
    r = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "model-agent", "default_model": "openai/gpt-4o"},
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]
    rows = (await c.get("/api/agents", headers=auth)).json()
    agent = next(a for a in rows if a["id"] == agent_id)
    assert agent["default_model"] == "openai/gpt-4o"


async def test_create_from_expert_default_name_uses_expert_label(env: Any) -> None:
    """Omitting ``name`` should use the expert template's localized label."""
    c, _srv, auth = env
    r = await c.post(
        "/api/agents/from-expert/ops-engineer",
        headers={**auth, "Accept-Language": "zh"},
        json={},
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "运维工程师 Ops"


async def test_create_from_expert_stores_backend(env: Any) -> None:
    c, _srv, auth = env
    backend_spec = {"type": "local_shell", "virtual_mode": True, "root_dir": "/"}
    r = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "backend-agent", "backend": backend_spec},
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]
    rows = (await c.get("/api/agents", headers=auth)).json()
    agent = next(a for a in rows if a["id"] == agent_id)
    assert agent["config"].get("backend") == backend_spec


async def test_create_agent_from_expert_stores_composer_defaults(env: Any) -> None:
    c, server, auth = env
    kb = server.services.knowledge_repo.create_base(owner_user_id=1, name="Policies")
    connector = await c.put(
        "/api/connectors/custom-mcp",
        headers=auth,
        json={
            "servers": {
                "docs": {"transport": "streamable_http", "url": "https://mcp.example.com/docs"}
            },
        },
    )
    assert connector.status_code == 200, connector.text
    mcp_name = "docs"

    created = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={
            "name": "composer-defaults-expert",
            "knowledge_base_ids": [kb.id],
            "mcp_servers": [mcp_name],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    detail = (await c.get(f"/api/agents/{body['agent_id']}", headers=auth)).json()
    assert detail["knowledge_base_ids"] == [kb.id]
    assert detail["mcp_servers"] == [mcp_name]
    assert "knowledge_base_ids" not in (detail.get("config") or {})
    assert "mcp_servers" not in (detail.get("config") or {})


async def test_create_agent_from_expert_rejects_unknown_knowledge_base(env: Any) -> None:
    c, _server, auth = env
    agents_before = (await c.get("/api/agents", headers=auth)).json()

    created = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "missing-kb-expert", "knowledge_base_ids": ["MISSING"]},
    )

    assert created.status_code == 404, created.text
    assert created.json()["error"]["code"] == "KNOWLEDGE_NOT_FOUND"
    agents_after = (await c.get("/api/agents", headers=auth)).json()
    assert {agent["agent_id"] for agent in agents_after} == {
        agent["agent_id"] for agent in agents_before
    }


async def test_create_agent_from_expert_rejects_unknown_connector(env: Any) -> None:
    c, _server, auth = env
    agents_before = (await c.get("/api/agents", headers=auth)).json()

    created = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "missing-connector-expert", "mcp_servers": ["unknown__instance"]},
    )

    assert created.status_code == 400, created.text
    assert created.json()["error"]["code"] == "CONNECTOR_NOT_BOUND"
    agents_after = (await c.get("/api/agents", headers=auth)).json()
    assert {agent["agent_id"] for agent in agents_after} == {
        agent["agent_id"] for agent in agents_before
    }


async def test_patch_agent_composer_defaults(env: Any) -> None:
    c, server, auth = env
    kb = server.services.knowledge_repo.create_base(owner_user_id=1, name="Handbook")
    connector = await c.put(
        "/api/connectors/custom-mcp",
        headers=auth,
        json={
            "servers": {
                "wiki": {"transport": "streamable_http", "url": "https://mcp.example.com/wiki"}
            },
        },
    )
    assert connector.status_code == 200, connector.text
    mcp_name = "wiki"

    created = await c.post(
        "/api/agents/from-expert/default",
        headers=auth,
        json={"name": "patch-composer-defaults"},
    )
    assert created.status_code == 201, created.text
    agent_id = created.json()["agent_id"]
    detail = (await c.get(f"/api/agents/{agent_id}", headers=auth)).json()
    assert detail["knowledge_base_ids"] == []
    assert detail["mcp_servers"] == []

    patched = await c.patch(
        f"/api/agents/{agent_id}",
        headers=auth,
        json={"knowledge_base_ids": [kb.id], "mcp_servers": [mcp_name]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["knowledge_base_ids"] == [kb.id]
    assert patched.json()["mcp_servers"] == [mcp_name]

    cleared = await c.patch(
        f"/api/agents/{agent_id}",
        headers=auth,
        json={"knowledge_base_ids": [], "mcp_servers": []},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["knowledge_base_ids"] == []
    assert cleared.json()["mcp_servers"] == []
