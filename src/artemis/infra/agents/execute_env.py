"""Inject platform execute defaults into harness backend specs.

Global admin env (``~/.artemis/env``) and workspace ``.env`` are merged at
**execute** time inside harness (``inherit_env`` / ``environment_file`` /
``BackendWorkspace`` reader) — not snapshotted here.

``ARTEMIS_AUTH_DIR`` / ``ARTEMIS_SKILLS_DIR`` use agent-facing paths when the
backend is scoped (bwrap / virtual rootfs), so skill scripts resolve the same
locations inside the jail. Host paths are still mkdir'd for Artemis host ops.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from artemis.infra.agents.workspace_dir import (
    agent_auth_dir,
    agent_facing_workspace_dir_from_config,
    agent_facing_workspace_root,
    host_system_dir,
    join_agent_facing,
    local_backend_root_dir,
    system_files_path_from_config,
    uses_scoped_workspace_default,
)
from artemis.infra.db.repos.agents import AgentRow
from artemis.infra.utils.paths import PathLayout

_EXECUTE_BACKEND_KINDS = frozenset({"local_shell", "docker"})


def _agent_facing_auth_and_skills(
    *,
    workspace_dir: Path,
    cfg: dict[str, Any] | None,
    auth_host: Path,
    skills_host: Path,
) -> tuple[str, str]:
    """Return execute-visible auth/skills paths (agent-facing when scoped)."""
    facing = agent_facing_workspace_dir_from_config(cfg)
    if not facing:
        facing = agent_facing_workspace_root(
            workspace_dir,
            root_dir=local_backend_root_dir(cfg),
            virtual_mode=True,
        )
    scoped = uses_scoped_workspace_default(cfg) or facing.startswith("/.artemis/")
    if not scoped:
        return str(auth_host), str(skills_host)

    prefix = system_files_path_from_config(cfg)
    # Match agent_auth_dir legacy preference when tokens already live at root.
    if auth_host.name == ".artemis-auth":
        auth_env = join_agent_facing(facing, ".artemis-auth")
    elif prefix:
        auth_env = join_agent_facing(facing, prefix, "auth")
    else:
        auth_env = join_agent_facing(facing, ".artemis-auth")

    if prefix:
        skills_env = join_agent_facing(facing, prefix, "skills")
    else:
        skills_env = join_agent_facing(facing, "skills")
    return auth_env, skills_env


def agent_execute_env_defaults(
    *,
    paths: PathLayout,
    agent_id: str,
    workspace_dir: Path,
    cfg: dict[str, Any] | None = None,
) -> dict[str, str]:
    auth_dir = agent_auth_dir(workspace_dir, cfg)
    auth_dir.mkdir(parents=True, exist_ok=True)
    skills_dir = host_system_dir(workspace_dir, cfg) / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    auth_env, skills_env = _agent_facing_auth_and_skills(
        workspace_dir=workspace_dir,
        cfg=cfg,
        auth_host=auth_dir,
        skills_host=skills_dir,
    )
    return {
        "ARTEMIS_AGENT_ID": agent_id,
        "ARTEMIS_AUTH_DIR": auth_env,
        "ARTEMIS_HOME": str(paths.root),
        "ARTEMIS_SKILLS_DIR": skills_env,
    }


def inject_agent_execute_env(
    backend: Any,
    *,
    paths: PathLayout,
    row: AgentRow,
    workspace_dir: Path,
    cfg: dict[str, Any] | None = None,
) -> Any:
    """Fold Artemis platform identity into shell/sandbox backend specs."""
    if not isinstance(backend, dict):
        return backend

    kind = str(backend.get("type") or "").lower()
    if kind == "composite":
        default = backend.get("default")
        if not isinstance(default, dict):
            return backend
        injected = inject_agent_execute_env(
            default,
            paths=paths,
            row=row,
            workspace_dir=workspace_dir,
            cfg=cfg,
        )
        if injected is default:
            return backend
        return {**backend, "default": injected}

    if kind not in _EXECUTE_BACKEND_KINDS:
        return backend

    extra: dict[str, str] = {str(k): str(v) for k, v in dict(backend.get("env") or {}).items()}
    extra.update(
        agent_execute_env_defaults(
            paths=paths,
            agent_id=row.agent_id,
            workspace_dir=workspace_dir,
            cfg=cfg,
        )
    )

    out = dict(backend)
    out["env"] = extra
    if kind == "local_shell":
        out.setdefault("inherit_env", True)
    return out
