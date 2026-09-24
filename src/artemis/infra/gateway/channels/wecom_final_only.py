"""Enterprise WeChat delivery mode that sends only an acknowledgement and final answer."""

from __future__ import annotations

import logging
from typing import Any

from harness_gateway.channels.wecom import WeComChannel, WeComConfig
from harness_gateway.models import InboundMessage, MessageEventType, TextContent

logger = logging.getLogger(__name__)

_WECOM_MARKDOWN_LIMIT = 2_000


def _markdown_chunks(text: str) -> list[str]:
    """Split a final WeCom markdown reply into platform-sized messages."""
    remaining = text or "✅"
    chunks: list[str] = []
    while len(remaining) > _WECOM_MARKDOWN_LIMIT:
        cut = remaining.rfind("\n", 0, _WECOM_MARKDOWN_LIMIT + 1)
        if cut > _WECOM_MARKDOWN_LIMIT // 2:
            chunks.append(remaining[:cut])
            remaining = remaining[cut + 1 :]
        else:
            chunks.append(remaining[:_WECOM_MARKDOWN_LIMIT])
            remaining = remaining[_WECOM_MARKDOWN_LIMIT:]
    chunks.append(remaining)
    return chunks


class FinalOnlyWeComConfig(WeComConfig):
    """Configuration for a WeCom channel that suppresses intermediate output."""


class FinalOnlyWeComChannel(WeComChannel):
    """Small testable core for the final-only WeCom delivery path.

    The production event loop will invoke this through the channel manager; keeping
    the acknowledgement/final-send pair separate makes it impossible to update the
    original stream after the long-running turn has completed.
    """

    def __init__(
        self,
        *args: Any,
        client: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if client is not None:
            self._ws_client = client

    async def start(self) -> None:
        """Connect with the SDK that supports proactive ``send_message``."""
        if self._ws_client is None:
            try:
                from artemis._vendor.aibot import WSClient, WSClientOptions
            except ImportError as exc:  # pragma: no cover - dependency error is operational
                raise ImportError("bundled WeCom final-only client is unavailable") from exc
            self._ws_client = WSClient(
                WSClientOptions(
                    bot_id=self._config.bot_id,
                    secret=self._config.secret,
                    ws_url=self._config.ws_url,
                    max_reconnect_attempts=-1,
                )
            )
            self._ws_client.on("message", self._on_final_only_message)
            self._ws_client.on("authenticated", self._on_authenticated)
            self._ws_client.on("disconnected", self._on_disconnected)
            self._ws_client.on("error", self._on_connection_error)
        await self._ws_client.connect()

    def _on_authenticated(self) -> None:
        self._connected = True
        logger.info("FinalOnlyWeComChannel WebSocket authenticated")

    def _on_disconnected(self, reason: str = "") -> None:
        self._connected = False
        logger.warning("FinalOnlyWeComChannel disconnected: %s", reason)

    def _on_connection_error(self, error: Exception) -> None:
        logger.error("FinalOnlyWeComChannel WebSocket error: %s", error)

    async def _on_final_only_message(self, frame: dict[str, Any]) -> None:
        """Forward a normalized SDK frame into the manager queue."""
        body = dict(frame.get("body") or {})
        body["_frame"] = frame
        body["chatid"] = body.get("chatid") or (body.get("from") or {}).get("userid", "")
        enqueue = self._enqueue_callback
        if enqueue is None:
            raise RuntimeError("WeCom channel is not registered")
        enqueue(body)

    async def handle_inbound(self, raw_payload: Any) -> None:
        """Acknowledge once, then proactively send only the completed answer."""
        if isinstance(raw_payload, InboundMessage):
            message = raw_payload
            frame = message.metadata.get("_frame", raw_payload)
        else:
            message = self.parse_inbound(raw_payload)
            frame = raw_payload.get("_frame", raw_payload)
        client = self._ws_client
        if client is None:
            raise RuntimeError("WeCom client is not connected")
        await client.reply_stream(frame, "ack", "正在分析，请稍候…", True)

        final_parts: list[str] = []
        async for event in self._processor(message):
            if event.type == MessageEventType.ERROR:
                final_parts = [event.error or "处理失败，请稍后重试。"]
                break
            if event.type != MessageEventType.MESSAGE:
                continue
            final_parts.extend(
                part.text for part in event.content if isinstance(part, TextContent) and part.text
            )

        subject = message.channel_subject
        chat_id = str(message.metadata.get("chat_id") or (subject.subject_id if subject else ""))
        if not chat_id:
            raise RuntimeError("WeCom inbound message has no chat target")
        final_text = "\n".join(final_parts)
        for chunk in _markdown_chunks(final_text):
            await client.send_message(
                chat_id,
                {"msgtype": "markdown", "markdown": {"content": chunk}},
            )

    async def send_final_for_test(self, frame: dict[str, Any], text: str) -> None:
        """Exercise the acknowledgement plus proactive final-send contract."""
        client = self._ws_client
        if client is None:
            raise RuntimeError("WeCom client is not connected")
        chat_id = str((frame.get("body") or {}).get("chatid") or "")
        if not chat_id:
            raise RuntimeError("WeCom inbound message has no chatid")
        await client.reply_stream(frame, "ack", "正在分析，请稍候…", True)
        for chunk in _markdown_chunks(text):
            await client.send_message(
                chat_id,
                {"msgtype": "markdown", "markdown": {"content": chunk}},
            )
