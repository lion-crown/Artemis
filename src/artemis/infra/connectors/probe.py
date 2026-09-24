"""Connectivity probes for user-defined MCP servers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from mcp.shared.exceptions import McpError

from artemis.infra.connectors.oauth.discovery import discover_oauth_from_mcp_url

logger = logging.getLogger(__name__)


def _tools(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    return [
        {"name": str(item.get("name") or ""), "description": str(item.get("description") or "")}
        for item in raw
        if isinstance(item, dict) and str(item.get("name") or "")
    ]


async def probe_streamable_http_mcp(url: str, headers: dict[str, str]) -> dict[str, Any]:
    """Initialize a streamable HTTP MCP server and list its tools."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    try:
        async with (
            streamablehttp_client(url, headers=headers, timeout=20, sse_read_timeout=20) as (
                read,
                write,
                _,
            ),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            tools = [
                {"name": tool.name, "description": tool.description or ""} for tool in listed.tools
            ]
            return {"ok": True, "tool_count": len(tools), "tools": tools}
    except httpx.HTTPStatusError as exc:
        kind = "auth" if exc.response.status_code in {401, 403} else "connection"
        return {
            "ok": False,
            "error_type": kind,
            "status_code": exc.response.status_code,
            "error": str(exc),
        }
    except (McpError, BaseExceptionGroup, Exception) as exc:
        logger.info("custom MCP streamable HTTP probe failed: %s", exc)
        return {"ok": False, "error_type": "connection", "error": str(exc)}


async def _probe_stdio_mcp(connection: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=str(connection.get("command") or ""),
        args=[str(arg) for arg in connection.get("args") or []],
        env={str(k): str(v) for k, v in dict(connection.get("env") or {}).items()} or None,
    )
    try:
        async with asyncio.timeout(25):
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                tools = [
                    {"name": tool.name, "description": tool.description or ""}
                    for tool in listed.tools
                ]
                return {"ok": True, "tool_count": len(tools), "tools": tools}
    except TimeoutError:
        return {"ok": False, "error": "stdio MCP probe timed out"}
    except Exception as exc:
        logger.info("custom MCP stdio probe failed: %s", exc)
        return {"ok": False, "error": str(exc)}


async def probe_custom_mcp_server(spec: dict[str, Any]) -> dict[str, Any]:
    """Probe a saved or draft custom MCP server."""
    from artemis.infra.connectors.custom_mcp import harness_spec_for_server, normalize_server_spec

    try:
        connection = harness_spec_for_server(normalize_server_spec("probe", spec))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if connection.get("transport") == "stdio":
        return await _probe_stdio_mcp(connection)
    if connection.get("transport") != "streamable_http":
        return {"ok": False, "error": "unsupported MCP transport"}
    headers = {str(k): str(v) for k, v in dict(connection.get("headers") or {}).items()}
    headers.setdefault("Accept", "application/json, text/event-stream")
    result = await probe_streamable_http_mcp(str(connection["url"]), headers)
    if result.get("error_type") == "auth" and not headers.get("Authorization"):
        found = await discover_oauth_from_mcp_url(str(connection["url"]))
        result["oauth"] = {
            "available": bool(found.get("available")),
            "issuer": found.get("issuer"),
            "resource": found.get("resource"),
        }
    return result
