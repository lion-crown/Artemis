"""HTTP API for user-defined MCP servers."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from contextlib import suppress
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

from artemis.api.common.public_base import resolve_public_base
from artemis.api.deps import current_user, get_server, require_permission
from artemis.i18n import tr
from artemis.infra.connectors.custom_mcp import (
    CUSTOM_MCP_KIND,
    oauth_configured,
    parse_synthetic_instance_id,
    redact_servers_for_api,
)
from artemis.infra.connectors.oauth import (
    delete_oauth_ctx,
    exchange_oauth_code,
    load_oauth_ctx,
    save_oauth_ctx,
    start_oauth_for_target,
)
from artemis.infra.connectors.oauth.registry import oauth_state_kind_for_target
from artemis.infra.connectors.probe import probe_custom_mcp_server
from artemis.infra.connectors.service import ConnectorNameTakenError, ConnectorService
from artemis.infra.errors import ErrorCode, ArtemisError
from artemis.infra.utils.locale import resolve_request_locale
from artemis.infra.utils.ulid import new_ulid

logger = logging.getLogger(__name__)
router = APIRouter()


class CustomMcpPutBody(BaseModel):
    servers: dict[str, Any] = Field(default_factory=dict)


class CustomMcpServerPatchBody(BaseModel):
    enabled: bool | None = None
    default_open: bool | None = None
    shared: bool | None = None

    @model_validator(mode="after")
    def _require_one_field(self) -> CustomMcpServerPatchBody:
        if self.enabled is None and self.default_open is None and self.shared is None:
            raise ValueError("provide enabled, default_open and/or shared")
        return self


class CustomMcpTestBody(BaseModel):
    name: str | None = None
    server: dict[str, Any] | None = None


class OAuthStartBody(BaseModel):
    redirect_after: str | None = None
    target: dict[str, Any] | None = None


def _connector_service(server: Any) -> ConnectorService:
    return ConnectorService(
        repo=server.services.repos.connector_repo,
        secret_repo=server.services.secret_repo,
        settings_repo=server.services.settings_repo,
        config=server.services.config,
    )


def _schedule_connector_reload(server: Any, user_id: int, *, all_users: bool = False) -> None:
    assert server.app_runtime is not None

    async def _run() -> None:
        try:
            if all_users:
                await server.app_runtime.agent_registry.reload_all()
            else:
                await server.app_runtime.agent_registry.reload_connectors_for_user(user_id)
        except Exception:
            logger.exception("background custom MCP reload failed for user %s", user_id)

    asyncio.create_task(_run())


def _is_public_http_uri(uri: str) -> bool:
    parsed = urlparse(uri)
    return parsed.scheme == "http" and (parsed.hostname or "").lower() not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def _oauth_callback_html(
    request: Request, key: str, *, status_code: int = 200, **fmt: Any
) -> HTMLResponse:
    return HTMLResponse(
        f"<html><body>{tr(f'connector.oauth.{key}', resolve_request_locale(request), **fmt)}</body></html>",
        status_code=status_code,
    )


def _custom_target(target: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not isinstance(target, dict) or str(target.get("type") or "") != "custom_mcp":
        raise ArtemisError(ErrorCode.CONNECTOR_INVALID_CREDENTIALS, "custom_mcp target is required")
    name = str(target.get("server_name") or "").strip()
    if not name:
        raise ArtemisError(
            ErrorCode.CONNECTOR_INVALID_CREDENTIALS, "custom_mcp target requires server_name"
        )
    return name, {"type": "custom_mcp", "server_name": name}


@router.get("/connector-instances", summary="List custom MCP servers")
async def list_instances(
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> list[dict[str, Any]]:
    """List custom MCP servers available to the current user."""
    rows = _connector_service(server).list_instances_for_api(user.id)
    for row in rows:
        owner_id = int(row.get("owner_user_id") or user.id)
        owner = server.services.user_repo.get(owner_id)
        row["owner_username"] = owner.username if owner is not None else None
        row["owner_display_name"] = (owner.display_name or owner.username) if owner else None
        row["can_manage"] = owner_id == user.id or user.role == "admin"
    return rows


@router.get("/connectors/custom-mcp", summary="Get custom MCP servers")
async def get_custom_mcp(
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> dict[str, Any]:
    return {"servers": _connector_service(server).get_custom_servers_for_api(user.id)}


@router.put("/connectors/custom-mcp", summary="Save custom MCP servers")
async def put_custom_mcp(
    body: CustomMcpPutBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> dict[str, Any]:
    svc = _connector_service(server)
    try:
        saved = svc.put_custom_servers(user.id, body.servers)
    except ConnectorNameTakenError as exc:
        raise ArtemisError(ErrorCode.CONNECTOR_NAME_TAKEN, str(exc)) from exc
    except ValueError as exc:
        raise ArtemisError(ErrorCode.CONNECTOR_INVALID_CREDENTIALS, str(exc)) from exc
    _schedule_connector_reload(
        server, user.id, all_users=any(spec.get("shared") is True for spec in saved.values())
    )
    return {"servers": redact_servers_for_api(saved)}


@router.patch("/connectors/custom-mcp/servers/{server_name}", summary="Patch a custom MCP server")
async def patch_custom_mcp_server(
    server_name: str,
    body: CustomMcpServerPatchBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> dict[str, Any]:
    svc = _connector_service(server)
    try:
        saved = svc.patch_custom_server(
            user.id,
            server_name,
            enabled=body.enabled,
            default_open=body.default_open,
            shared=body.shared,
        )
    except KeyError as exc:
        raise ArtemisError(ErrorCode.CONNECTOR_NOT_FOUND, "custom MCP server not found") from exc
    _schedule_connector_reload(server, user.id, all_users=body.shared is not None)
    return {"servers": redact_servers_for_api(saved)}


@router.delete(
    "/connector-instances/{instance_id}", status_code=204, summary="Delete a custom MCP server"
)
async def delete_custom_mcp_instance(
    instance_id: str,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> None:
    name = parse_synthetic_instance_id(instance_id)
    if not name:
        raise ArtemisError(ErrorCode.CONNECTOR_NOT_FOUND, "connector not found")
    svc = _connector_service(server)
    saved = svc.get_custom_servers(user.id)
    if name not in saved:
        raise ArtemisError(ErrorCode.CONNECTOR_NOT_FOUND, "custom MCP server not found")
    del saved[name]
    svc.put_custom_servers(user.id, saved)
    _schedule_connector_reload(server, user.id)


@router.post("/connectors/custom-mcp/test", summary="Probe a custom MCP server")
async def test_custom_mcp(
    body: CustomMcpTestBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> dict[str, Any]:
    svc = _connector_service(server)
    if body.server is not None:
        spec = dict(body.server)
    elif body.name:
        saved = svc.get_custom_servers(user.id).get(body.name)
        if not isinstance(saved, dict):
            raise ArtemisError(ErrorCode.CONNECTOR_NOT_FOUND, "custom MCP server not found")
        spec = saved
    else:
        raise ArtemisError(
            ErrorCode.CONNECTOR_INVALID_CREDENTIALS, "provide name or server spec to probe"
        )
    result = await probe_custom_mcp_server(spec)
    if body.name:
        with suppress(KeyError):
            svc.note_custom_server_oauth_required(
                user.id,
                body.name,
                required=bool(result.get("oauth", {}).get("available"))
                and not oauth_configured(spec),
            )
    return result


@router.post("/connectors/oauth/start", summary="Start custom MCP OAuth")
async def oauth_start(
    body: OAuthStartBody,
    request: Request,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> dict[str, Any]:
    name, target = _custom_target(body.target)
    svc = _connector_service(server)
    spec = svc.get_custom_servers(user.id).get(name)
    if not isinstance(spec, dict) or str(spec.get("transport") or "") not in {
        "http",
        "streamable_http",
    }:
        raise ArtemisError(
            ErrorCode.CONNECTOR_NOT_FOUND, "streamable HTTP custom MCP server not found"
        )
    mcp_url = str(spec.get("url") or "").strip()
    redirect_uri = f"{resolve_public_base(request)}/api/connectors/oauth/callback"
    if _is_public_http_uri(redirect_uri):
        raise ArtemisError(
            ErrorCode.CONNECTOR_OAUTH_HTTPS_REQUIRED, "custom MCP OAuth callbacks require HTTPS"
        )
    state, state_id = secrets.token_urlsafe(24), new_ulid()
    try:
        authorize_url, verifier, ctx = await start_oauth_for_target(
            target=target,
            redirect_uri=redirect_uri,
            state=state,
            settings_repo=server.services.settings_repo,
            mcp_url=mcp_url,
        )
    except Exception as exc:
        raise ArtemisError(ErrorCode.CONNECTOR_INVALID_CREDENTIALS, str(exc)) from exc
    server.services.repos.connector_repo.create_oauth_state(
        state_id=state_id,
        state=state,
        user_id=user.id,
        kind=oauth_state_kind_for_target(target),
        code_verifier=verifier,
        redirect_after=body.redirect_after,
    )
    save_oauth_ctx(server.services.settings_repo, state_id, ctx)
    return {"authorize_url": authorize_url, "state_id": state_id}


@router.get("/connectors/oauth/callback", summary="Complete custom MCP OAuth")
async def oauth_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    server: Any = Depends(get_server),
) -> HTMLResponse:
    if error:
        return _oauth_callback_html(request, "callback_auth_failed", status_code=400, error=error)
    if not code or not state:
        return _oauth_callback_html(request, "callback_missing_params", status_code=400)
    row = server.services.repos.connector_repo.consume_oauth_state(state)
    if row is None or row.kind != CUSTOM_MCP_KIND:
        return _oauth_callback_html(request, "callback_invalid_state", status_code=400)
    redirect_uri = f"{resolve_public_base(request)}/api/connectors/oauth/callback"
    try:
        tokens = await exchange_oauth_code(
            kind=row.kind,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=row.code_verifier,
            settings_repo=server.services.settings_repo,
            state_id=row.state_id,
        )
        ctx = load_oauth_ctx(server.services.settings_repo, row.state_id)
        for key in ("client_id", "client_secret"):
            if ctx.get(key):
                tokens[f"oauth_{key}"] = ctx[key]
        delete_oauth_ctx(server.services.settings_repo, row.state_id)
        name = str(ctx.get("server_name") or "")
        _connector_service(server).apply_custom_server_oauth(
            row.user_id,
            name,
            tokens,
            issuer=str(ctx.get("issuer") or ""),
            resource=str(ctx.get("resource") or "").strip() or None,
        )
        _schedule_connector_reload(server, row.user_id)
    except Exception as exc:
        logger.exception("custom MCP OAuth callback failed")
        return _oauth_callback_html(
            request, "callback_save_failed", status_code=400, detail=str(exc)
        )
    server.services.settings_repo.set(
        f"connector.oauth.pending.{row.state_id}",
        json.dumps(
            {"user_id": row.user_id, "kind": row.kind, "server_name": name, "applied": True}
        ),
    )
    success = tr("connector.oauth.callback_success", resolve_request_locale(request))
    return HTMLResponse(f"<html><body><p>{success}</p></body></html>")


@router.get("/connectors/oauth/pending/{state_id}", summary="Poll custom MCP OAuth result")
async def oauth_pending(
    state_id: str,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
    _: Any = Depends(require_permission("connectors")),
) -> dict[str, Any]:
    key = f"connector.oauth.pending.{state_id}"
    raw = server.services.settings_repo.get(key)
    if not raw:
        raise ArtemisError(ErrorCode.NOT_FOUND, "pending oauth not found")
    data = json.loads(raw)
    if int(data.get("user_id") or 0) != user.id:
        raise ArtemisError(ErrorCode.FORBIDDEN, "not your oauth session")
    server.services.settings_repo.delete(key)
    return {
        "kind": data.get("kind"),
        "server_name": data.get("server_name"),
        "applied": data.get("applied"),
    }


async def validate_chat_mcp_servers(
    server: Any, *, user_id: int, names: list[str] | None
) -> list[str] | None:
    from artemis.api.common.validators import validate_chat_mcp_servers as validate

    return await validate(server, user_id=user_id, names=names)
