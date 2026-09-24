"""OAuth 2.1 flows discovered from user-defined MCP servers."""

from __future__ import annotations

import json
from typing import Any

from artemis.infra.connectors.custom_mcp import CUSTOM_MCP_KIND
from artemis.infra.connectors.oauth.discovery import discover_oauth_from_mcp_url
from artemis.infra.connectors.oauth.mcp import (
    build_authorize_url,
    exchange_authorization_code,
    fetch_authorization_metadata,
    refresh_access_token,
    register_dynamic_client,
)
from artemis.infra.connectors.oauth.pkce import new_pkce_pair

OAUTH_CTX_PREFIX = "connector.oauth.ctx."


def save_oauth_ctx(settings_repo: Any, state_id: str, ctx: dict[str, Any]) -> None:
    settings_repo.set(f"{OAUTH_CTX_PREFIX}{state_id}", json.dumps(ctx))


def load_oauth_ctx(settings_repo: Any, state_id: str) -> dict[str, Any]:
    raw = settings_repo.get(f"{OAUTH_CTX_PREFIX}{state_id}")
    if not raw:
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def delete_oauth_ctx(settings_repo: Any, state_id: str) -> None:
    settings_repo.delete(f"{OAUTH_CTX_PREFIX}{state_id}")


async def _start_custom_mcp_oauth(
    *, server_name: str, mcp_url: str, redirect_uri: str, state: str
) -> tuple[str, str, dict[str, Any]]:
    found = await discover_oauth_from_mcp_url(mcp_url)
    if not found.get("available"):
        raise ValueError(str(found.get("error") or "OAuth not available for this MCP URL"))
    issuer = str(found["issuer"])
    resource = str(found.get("resource") or "").strip() or None
    metadata = found.get("metadata")
    if not isinstance(metadata, dict):
        metadata = await fetch_authorization_metadata(issuer)
    verifier, challenge = new_pkce_pair()
    registration = await register_dynamic_client(metadata, issuer=issuer, redirect_uri=redirect_uri)
    client_id = str(registration["client_id"])
    client_secret = str(registration.get("client_secret") or "") or None
    scopes = metadata.get("scopes_supported")
    scope = " ".join(str(item) for item in scopes if item) if isinstance(scopes, list) else None
    return (
        build_authorize_url(
            metadata,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
            scope=scope,
            resource=resource,
        ),
        verifier,
        {
            "flow": "custom_mcp",
            "kind": CUSTOM_MCP_KIND,
            "server_name": server_name,
            "metadata": metadata,
            "client_id": client_id,
            "client_secret": client_secret,
            "resource": resource,
            "redirect_uri": redirect_uri,
            "issuer": issuer,
        },
    )


async def start_oauth_for_target(
    *,
    target: dict[str, Any],
    redirect_uri: str,
    state: str,
    settings_repo: Any,
    mcp_url: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    del settings_repo
    if str(target.get("type") or "") != "custom_mcp":
        raise ValueError("only custom_mcp OAuth targets are supported")
    name, url = str(target.get("server_name") or "").strip(), str(mcp_url or "").strip()
    if not name or not url:
        raise ValueError("custom MCP server name and URL are required")
    return await _start_custom_mcp_oauth(
        server_name=name, mcp_url=url, redirect_uri=redirect_uri, state=state
    )


def oauth_state_kind_for_target(target: dict[str, Any]) -> str:
    if str(target.get("type") or "") != "custom_mcp":
        raise ValueError("only custom_mcp OAuth targets are supported")
    return CUSTOM_MCP_KIND


async def exchange_oauth_code(
    *,
    kind: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    settings_repo: Any,
    state_id: str,
) -> dict[str, Any]:
    if kind != CUSTOM_MCP_KIND:
        raise ValueError("only custom MCP OAuth is supported")
    ctx = load_oauth_ctx(settings_repo, state_id)
    metadata = ctx.get("metadata")
    issuer = str(ctx.get("issuer") or "")
    if not isinstance(metadata, dict):
        metadata = await fetch_authorization_metadata(issuer)
    client_id = str(ctx.get("client_id") or "")
    if not issuer or not client_id:
        raise ValueError("missing custom MCP OAuth context")
    secret = str(ctx.get("client_secret") or "") or None
    return await exchange_authorization_code(
        metadata,
        issuer=issuer,
        client_id=client_id,
        client_secret=secret,
        code=code,
        redirect_uri=str(ctx.get("redirect_uri") or redirect_uri),
        code_verifier=code_verifier,
        resource=str(ctx.get("resource") or "") or None,
    )


async def refresh_custom_mcp_oauth(oauth: dict[str, Any]) -> dict[str, Any]:
    refresh, issuer, client_id = (
        str(oauth.get("refresh_token") or "").strip(),
        str(oauth.get("oauth_issuer") or "").strip(),
        str(oauth.get("oauth_client_id") or "").strip(),
    )
    if not refresh or not issuer or not client_id:
        return oauth
    refreshed = await refresh_access_token(
        await fetch_authorization_metadata(issuer),
        issuer=issuer,
        client_id=client_id,
        client_secret=str(oauth.get("oauth_client_secret") or "") or None,
        refresh_token=refresh,
        resource=str(oauth.get("oauth_resource") or "") or None,
    )
    return {**oauth, **refreshed}
