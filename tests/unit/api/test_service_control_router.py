"""Unit tests for the service-control API router."""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks

from artemis.api.routers import service_control
from artemis.infra.errors import ErrorCode, ArtemisError


@pytest.mark.asyncio
async def test_service_status_reports_only_runtime_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_control, "detect_service_mode", lambda: "systemd")
    monkeypatch.setattr(service_control, "_is_desktop_process", lambda: False)

    assert await service_control.service_status(_=None) == {
        "service_mode": "systemd",
        "desktop": False,
    }


@pytest.mark.asyncio
async def test_restart_schedules_background_service_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    restarted: list[object] = []
    runtime = type(
        "Runtime",
        (),
        {"mode": "systemd", "scope": None, "run_as_user": None},
    )()
    monkeypatch.setattr(service_control, "detect_service_mode", lambda: "systemd")
    monkeypatch.setattr(service_control, "_is_desktop_process", lambda: False)
    monkeypatch.setattr(service_control, "build_runtime", lambda mode: runtime)
    monkeypatch.setattr(service_control, "is_service_installed", lambda *_, **__: True)
    monkeypatch.setattr(
        service_control,
        "restart_service",
        lambda value: restarted.append(value),
    )

    tasks = BackgroundTasks()
    result = await service_control.restart_service_endpoint(tasks, _=None)

    assert result == {"status": "restarting", "service_mode": "systemd"}
    assert restarted == []
    for task in tasks.tasks:
        await task()
    assert restarted == [runtime]


@pytest.mark.asyncio
async def test_restart_rejects_without_a_managed_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service_control, "_is_desktop_process", lambda: False)
    monkeypatch.setattr(service_control, "detect_service_mode", lambda: None)

    with pytest.raises(ArtemisError) as exc_info:
        await service_control.restart_service_endpoint(BackgroundTasks(), _=None)

    assert exc_info.value.code == ErrorCode.FORBIDDEN
