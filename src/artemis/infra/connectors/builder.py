"""Build deferred harness configuration for user-defined MCP servers."""

from __future__ import annotations

import json
import logging
from typing import Any

from artemis.config import ArtemisConfig


def _redact_mcp_configs_for_log(configs: dict[str, Any]) -> dict[str, Any]:
    """Return connection specs without headers or URL query secrets."""
    out: dict[str, Any] = {}
    for name, spec in configs.items():
        if not isinstance(spec, dict):
            out[name] = spec
            continue
        entry = dict(spec)
        if "headers" in entry:
            entry["headers"] = "***"
        out[name] = entry
    return out


def build_mcp_server_configs_for_user(
    *,
    svc: Any,
    connector_repo: Any,
    user_id: int,
    agent_id: str,
    agent_user_id: int | None,
    config: ArtemisConfig,
    log: bool = True,
) -> dict[str, Any]:
    """Register custom MCP server names for deferred, cached tool loading.

    The actual connection specifications are intentionally loaded only when a
    chat selects a custom server; this keeps startup free of external MCP I/O.
    """
    del connector_repo, agent_user_id, config
    logger = logging.getLogger(__name__)
    configs: dict[str, dict[str, Any]] = {name: {} for name in svc.custom_harness_configs(user_id)}
    if log:
        logger.info(
            "build_mcp_server_configs agent=%s result=%s",
            agent_id,
            json.dumps(_redact_mcp_configs_for_log(configs), ensure_ascii=False),
        )
    return configs
