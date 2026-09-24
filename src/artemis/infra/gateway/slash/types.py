"""Gateway slash handler types."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_agent.slash import SlashCommand, SlashSink

    from artemis.infra.gateway.slash.ctx import SlashCtx
    from artemis.infra.gateway.slash.dispatcher import SlashDispatcher

GatewayHandler = Callable[
    ["SlashDispatcher", "SlashCommand", "SlashCtx", "SlashSink"],
    Awaitable[None],
]
