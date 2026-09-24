"""Dashboard chat routers — WebSocket turns, thread CRUD, polish, HITL."""

from __future__ import annotations

from fastapi import APIRouter

from artemis.api.routers.chat.history import router as history_router
from artemis.api.routers.chat.notify_ws import router as notify_ws_router
from artemis.api.routers.chat.routes import router as routes_router
from artemis.api.routers.chat.trajectory import router as trajectory_router
from artemis.api.routers.chat.ws import router as ws_router

router = APIRouter()
router.include_router(routes_router)
router.include_router(history_router)
router.include_router(trajectory_router)
router.include_router(ws_router)
router.include_router(notify_ws_router)

__all__ = ["router"]
