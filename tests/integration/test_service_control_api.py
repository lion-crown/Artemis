"""Integration coverage for service-control endpoints."""

from __future__ import annotations

from typing import Any


async def test_service_status_replaces_the_update_status_endpoint(
    env_admin_client: Any,
) -> None:
    client, auth = env_admin_client

    status = await client.get("/api/admin/service/status", headers=auth)
    assert status.status_code == 200
    assert set(status.json()) == {"service_mode", "desktop"}

    removed = await client.get("/api/update/status", headers=auth)
    assert removed.status_code == 404
