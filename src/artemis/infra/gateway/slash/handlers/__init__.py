"""Gateway slash command handler registry."""

from __future__ import annotations

from artemis.infra.gateway.slash.catalog import CATALOG
from artemis.infra.gateway.slash.dispatcher import SlashDispatcher
from artemis.infra.gateway.slash.handlers.composite import COMPOSITE_HANDLERS
from artemis.infra.gateway.slash.handlers.hitl import HITL_HANDLERS
from artemis.infra.gateway.slash.handlers.platform import PLATFORM_HANDLERS
from artemis.infra.gateway.slash.handlers.session import SESSION_HANDLERS
from artemis.infra.gateway.slash.types import GatewayHandler

GATEWAY_HANDLERS: dict[str, GatewayHandler] = {
    **SESSION_HANDLERS,
    **PLATFORM_HANDLERS,
    **COMPOSITE_HANDLERS,
    **HITL_HANDLERS,
}


def register_all(d: SlashDispatcher) -> None:
    for spec in CATALOG:
        handler = GATEWAY_HANDLERS.get(spec.name)
        if handler is None:
            continue
        d.register(spec, handler)
