from __future__ import annotations

from pathlib import Path

import pytest
from harness_agent.backends import resolve_backend
from harness_agent.backends.workspace import BackendWorkspace

from artemis.infra.agents.business_workspace import build_business_workspace_binding


def test_business_workspace_uses_backend_root_and_private_system_mount(tmp_path: Path) -> None:
    backend = {
        "type": "local_shell",
        "root_dir": str(tmp_path / "business"),
        "virtual_mode": True,
    }

    binding = build_business_workspace_binding(backend, tmp_path / "agent-system", ".artemis")

    assert binding.workspace_dir == Path("/")
    assert binding.system_files_path == ".artemis"
    assert binding.backend["type"] == "composite"
    assert binding.backend["default"] == backend
    assert binding.backend["routes"]["/.artemis/"]["root_dir"] == str(
        tmp_path / "agent-system" / ".artemis"
    )


def test_business_workspace_preserves_existing_composite_routes(tmp_path: Path) -> None:
    backend = {
        "type": "composite",
        "default": {"type": "local_shell", "root_dir": "backend", "virtual_mode": True},
        "routes": {"/web/": {"type": "local_shell", "root_dir": "web", "virtual_mode": True}},
    }

    binding = build_business_workspace_binding(backend, tmp_path / "agent-system", ".artemis")

    assert binding.workspace_dir == Path("/")
    assert binding.backend["default"] == backend["default"]
    assert binding.backend["routes"]["/web/"] == backend["routes"]["/web/"]
    assert binding.backend["routes"]["/.artemis/"]["root_dir"] == str(
        tmp_path / "agent-system" / ".artemis"
    )


@pytest.mark.asyncio
async def test_business_workspace_routes_business_and_private_system_files(tmp_path: Path) -> None:
    business_root = tmp_path / "business"
    business_root.mkdir()
    (business_root / "BusinessRule.java").write_text("business rule", encoding="utf-8")
    system_root = tmp_path / "agent-system"
    (system_root / ".artemis").mkdir(parents=True)
    (system_root / ".artemis" / "MEMORY.md").write_text("private memory", encoding="utf-8")
    binding = build_business_workspace_binding(
        {"type": "local_shell", "root_dir": str(business_root), "virtual_mode": True},
        system_root,
        ".artemis",
    )
    workspace = BackendWorkspace(
        resolve_backend(
            binding.backend,
            workspace_dir=binding.workspace_dir,
            system_files_path=binding.system_files_path,
        ),
        binding.workspace_dir,
        system_files_path=binding.system_files_path,
    )

    assert await workspace.aread_text("/BusinessRule.java") == "business rule"
    assert await workspace.aread_text("/.artemis/MEMORY.md") == "private memory"
