"""Service runtime status and restart endpoints."""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends

from artemis.api.deps import current_user, require_permission
from artemis.infra.errors import ErrorCode, ArtemisError
from artemis.infra.setup.service import (
    ServiceRuntime,
    build_runtime,
    detect_service_mode,
    is_service_installed,
    restart_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/service")


def _is_desktop_process() -> bool:
    raw = (os.environ.get("ARTEMIS_DESKTOP") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@router.get("/status")
async def service_status(
    _: Any = Depends(current_user),
) -> dict[str, str | bool | None]:
    """Return the runtime capabilities used by service-management UI."""
    return {
        "service_mode": detect_service_mode(),
        "desktop": _is_desktop_process(),
    }


def _restart_desktop_process() -> None:
    time.sleep(0.4)
    argv = list(getattr(sys, "orig_argv", None) or [sys.executable, *sys.argv])
    os.execv(argv[0], argv)


def _restart_service_task(runtime: ServiceRuntime) -> None:
    try:
        restart_service(runtime)
    except Exception:
        logger.exception("background service restart failed")


@router.post("/restart")
async def restart_service_endpoint(
    background_tasks: BackgroundTasks,
    _: Any = Depends(require_permission("tls")),
) -> dict[str, str]:
    """Restart the managed service after an administrator confirms it."""
    if _is_desktop_process():
        background_tasks.add_task(_restart_desktop_process)
        return {"status": "restarting", "service_mode": "desktop"}
    mode = detect_service_mode()
    if mode is None:
        raise ArtemisError(
            ErrorCode.FORBIDDEN,
            "service restart is only available when ARTEMIS_SERVICE_MODE is set",
        )
    try:
        runtime = build_runtime(mode=mode)
        if not is_service_installed(
            runtime.mode,
            scope=runtime.scope,
            run_as_user=runtime.run_as_user,
        ):
            raise RuntimeError(
                f"artemis system service is not installed (expected unit for mode={runtime.mode})"
            )
    except RuntimeError as exc:
        raise ArtemisError(ErrorCode.INTERNAL_ERROR, str(exc)) from exc
    except Exception as exc:
        raise ArtemisError(ErrorCode.INTERNAL_ERROR, str(exc)) from exc
    background_tasks.add_task(_restart_service_task, runtime)
    return {"status": "restarting", "service_mode": mode}
