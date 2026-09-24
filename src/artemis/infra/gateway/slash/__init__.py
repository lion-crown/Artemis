"""Slash command parsing and dispatch."""

from harness_agent.slash import BufferSink, SlashCommand, SlashSink

from artemis.infra.gateway.slash.ctx import SlashCtx, build_slash_ctx
from artemis.infra.gateway.slash.dispatcher import SlashDispatcher, build_default_dispatcher
from artemis.infra.gateway.slash.parser import parse_slash

__all__ = [
    "BufferSink",
    "SlashCommand",
    "SlashCtx",
    "SlashDispatcher",
    "SlashSink",
    "build_default_dispatcher",
    "build_slash_ctx",
    "parse_slash",
]
