"""Custom MCP persistence, visibility and runtime configuration."""

from __future__ import annotations

import logging
import time
from typing import Any

from artemis.config import ArtemisConfig
from artemis.infra.connectors.crypto import decrypt_credentials, encrypt_credentials
from artemis.infra.connectors.custom_mcp import (
    CUSTOM_MCP_DISPLAY_NAME,
    CUSTOM_MCP_KIND,
    build_oauth_storage,
    enabled_harness_configs,
    expand_custom_instances,
    extract_servers,
    is_custom_mcp_kind,
    mark_oauth_reauth_required,
    merge_preserved_oauth,
    oauth_configured,
    oauth_tokens_from_spec,
    redact_servers_for_api,
    server_enabled,
    set_oauth_required_in_spec,
    shared_mcp_server_name,
    validate_servers_map,
    wrap_servers,
)
from artemis.infra.connectors.default_open import merge_mcp_servers_with_defaults
from artemis.infra.connectors.oauth.registry import refresh_custom_mcp_oauth
from artemis.infra.db.repos.connectors import ConnectorRepo, ConnectorRow
from artemis.infra.db.repos.secrets import SecretRepo
from artemis.infra.utils.ulid import new_ulid

logger = logging.getLogger(__name__)
_OAUTH_REFRESH_SKEW_SEC = 120


class ConnectorNameTakenError(ValueError):
    """Raised when a custom MCP display name is already in use."""


def list_user_connector_instances(
    repo: ConnectorRepo,
    user_id: int,
    *,
    active_only: bool = False,
    with_credentials: bool = False,
) -> list[ConnectorRow]:
    """Compatibility list for the slash command; only custom-MCP parent rows remain."""
    rows = [row for row in repo.list_by_user(user_id) if is_custom_mcp_kind(row.kind)]
    if active_only:
        rows = [row for row in rows if row.status == "active"]
    if with_credentials:
        rows = [row for row in rows if row.has_credentials]
    return rows


class ConnectorService:
    def __init__(
        self,
        *,
        repo: ConnectorRepo,
        secret_repo: SecretRepo,
        settings_repo: Any,
        config: ArtemisConfig,
    ) -> None:
        self._repo = repo
        self._secret_repo = secret_repo
        self._settings_repo = settings_repo
        self._config = config

    def decrypt(self, instance_id: str) -> dict[str, Any]:
        row = self._repo.get(instance_id)
        if row is None or not row.credential_blob:
            return {}
        return decrypt_credentials(self._secret_repo, row.credential_blob)

    def encrypt_and_store(self, *, instance_id: str, payload: dict[str, Any]) -> None:
        stored = dict(payload)
        stored["instance_id"] = instance_id
        expires_at = stored.get("expires_at")
        self._repo.upsert_credentials(
            instance_id=instance_id,
            blob=encrypt_credentials(self._secret_repo, stored),
            expires_at=int(expires_at) if expires_at is not None else None,
        )

    def get_custom_servers(self, user_id: int) -> dict[str, Any]:
        row = self._repo.get_by_user_kind(user_id, CUSTOM_MCP_KIND)
        if row is None or not row.has_credentials:
            return {}
        return extract_servers(self.decrypt(row.instance_id))

    def get_custom_servers_for_api(self, user_id: int) -> dict[str, Any]:
        return redact_servers_for_api(self.get_custom_servers(user_id))

    def put_custom_servers(self, user_id: int, servers: dict[str, Any]) -> dict[str, Any]:
        return self._save_custom_servers(
            user_id,
            merge_preserved_oauth(servers, self.get_custom_servers(user_id)),
        )

    def _save_custom_servers(self, user_id: int, servers: dict[str, Any]) -> dict[str, Any]:
        normalized = validate_servers_map(servers)
        display_names: set[str] = set()
        for name, spec in normalized.items():
            display_name = str(spec.get("display_name") or "").strip() or name
            if display_name in display_names:
                raise ConnectorNameTakenError(display_name)
            display_names.add(display_name)
        row = self._repo.get_by_user_kind(user_id, CUSTOM_MCP_KIND)
        if not normalized:
            if row is not None:
                self._repo.delete(row.instance_id)
            return {}
        if row is None:
            instance_id = new_ulid()
            self._repo.create(
                instance_id=instance_id,
                user_id=user_id,
                kind=CUSTOM_MCP_KIND,
                display_name=CUSTOM_MCP_DISPLAY_NAME,
                mcp_server_name=f"{CUSTOM_MCP_KIND}__{instance_id}",
            )
        else:
            instance_id = row.instance_id
        self.encrypt_and_store(instance_id=instance_id, payload=wrap_servers(normalized))
        return normalized

    def apply_custom_server_oauth(
        self,
        user_id: int,
        server_name: str,
        tokens: dict[str, Any],
        *,
        issuer: str,
        resource: str | None,
    ) -> dict[str, Any]:
        servers = self.get_custom_servers(user_id)
        if server_name not in servers:
            raise KeyError(server_name)
        spec = dict(servers[server_name])
        spec["oauth"] = build_oauth_storage(tokens, issuer=issuer, resource=resource)
        servers[server_name] = set_oauth_required_in_spec(spec, required=False)
        return self._save_custom_servers(user_id, servers)

    async def ensure_fresh_custom_servers(self, user_id: int) -> dict[str, Any]:
        servers = self.get_custom_servers(user_id)
        changed = False
        now = int(time.time())
        for name, raw in list(servers.items()):
            if not isinstance(raw, dict) or not oauth_configured(raw):
                continue
            oauth = oauth_tokens_from_spec(raw)
            expires_at = oauth.get("expires_at")
            expires = int(expires_at) if expires_at is not None else None
            refresh = str(oauth.get("refresh_token") or "").strip()
            if expires is not None and expires <= now and not refresh:
                servers[name] = mark_oauth_reauth_required(raw)
                changed = True
                continue
            if not refresh or (expires is not None and expires > now + _OAUTH_REFRESH_SKEW_SEC):
                continue
            try:
                updated = await refresh_custom_mcp_oauth(oauth)
            except Exception:
                logger.warning("custom MCP oauth refresh failed for %s", name, exc_info=True)
                if expires is not None and expires <= now:
                    servers[name] = mark_oauth_reauth_required(raw)
                    changed = True
                continue
            spec = dict(raw)
            spec["oauth"] = updated
            servers[name] = spec
            changed = True
        return self._save_custom_servers(user_id, servers) if changed else servers

    def patch_custom_server(
        self,
        user_id: int,
        server_name: str,
        *,
        enabled: bool | None = None,
        default_open: bool | None = None,
        shared: bool | None = None,
    ) -> dict[str, Any]:
        servers = self.get_custom_servers(user_id)
        if server_name not in servers:
            raise KeyError(server_name)
        spec = dict(servers[server_name])
        for key, value in (
            ("enabled", enabled),
            ("default_open", default_open),
            ("shared", shared),
        ):
            if value is None:
                continue
            if key == "enabled":
                spec[key] = value
            elif value:
                spec[key] = True
            else:
                spec.pop(key, None)
        if enabled is False:
            spec.pop("default_open", None)
        servers[server_name] = spec
        return self.put_custom_servers(user_id, servers)

    def patch_custom_server_enabled(
        self, user_id: int, server_name: str, *, enabled: bool
    ) -> dict[str, Any]:
        return self.patch_custom_server(user_id, server_name, enabled=enabled)

    def note_custom_server_oauth_required(
        self, user_id: int, server_name: str, *, required: bool
    ) -> dict[str, Any]:
        servers = self.get_custom_servers(user_id)
        if server_name not in servers:
            raise KeyError(server_name)
        servers[server_name] = set_oauth_required_in_spec(servers[server_name], required=required)
        return self._save_custom_servers(user_id, servers)

    def list_instances_for_api(self, user_id: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        own = self._repo.get_by_user_kind(user_id, CUSTOM_MCP_KIND)
        if own is not None and own.has_credentials:
            out.extend(
                expand_custom_instances(parent=own, servers=self.get_custom_servers(user_id))
            )
        for parent in self._repo.list_by_kind(CUSTOM_MCP_KIND):
            if parent.user_id != user_id and parent.has_credentials:
                out.extend(
                    expand_custom_instances(
                        parent=parent,
                        servers=extract_servers(self.decrypt(parent.instance_id)),
                        shared_view=True,
                    )
                )
        return out

    def list_active_mcp_server_names(self, user_id: int) -> list[str]:
        names = [
            name
            for name, spec in self.get_custom_servers(user_id).items()
            if isinstance(spec, dict) and server_enabled(spec)
        ]
        for parent in self._repo.list_by_kind(CUSTOM_MCP_KIND):
            if parent.user_id == user_id or not parent.has_credentials:
                continue
            for name, spec in extract_servers(self.decrypt(parent.instance_id)).items():
                if isinstance(spec, dict) and spec.get("shared") is True and server_enabled(spec):
                    names.append(shared_mcp_server_name(parent.instance_id, name))
        return sorted(names)

    def list_default_open_mcp_server_names(self, user_id: int) -> list[str]:
        return sorted(
            name
            for name, spec in self.get_custom_servers(user_id).items()
            if isinstance(spec, dict) and server_enabled(spec) and spec.get("default_open") is True
        )

    def merge_turn_mcp_servers(
        self,
        user_id: int,
        explicit: list[str] | None,
        *,
        apply_defaults: bool | None = None,
        extra_defaults: list[str] | None = None,
    ) -> list[str] | None:
        defaults = self.list_default_open_mcp_server_names(user_id)
        allowed = set(self.list_active_mcp_server_names(user_id))
        defaults.extend(
            name for name in extra_defaults or [] if name in allowed and name not in defaults
        )
        return merge_mcp_servers_with_defaults(explicit, defaults, apply_defaults=apply_defaults)

    def validate_mcp_servers_for_user(self, user_id: int, names: list[str]) -> list[str]:
        unknown = sorted(set(names) - set(self.list_active_mcp_server_names(user_id)))
        if unknown:
            raise ValueError(f"mcp_servers not available for user: {unknown}")
        return list(names)

    def custom_harness_configs(self, user_id: int) -> dict[str, Any]:
        configs = enabled_harness_configs(self.get_custom_servers(user_id))
        for parent in self._repo.list_by_kind(CUSTOM_MCP_KIND):
            if parent.user_id == user_id or not parent.has_credentials:
                continue
            for name, spec in extract_servers(self.decrypt(parent.instance_id)).items():
                if isinstance(spec, dict) and spec.get("shared") is True and server_enabled(spec):
                    built = enabled_harness_configs({name: spec}).get(name)
                    if built is not None:
                        configs[shared_mcp_server_name(parent.instance_id, name)] = built
        return configs

    async def mcp_configs_for_user(self, user_id: int) -> dict[str, Any]:
        await self.ensure_fresh_custom_servers(user_id)
        return self.custom_harness_configs(user_id)
