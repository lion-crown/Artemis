from __future__ import annotations

import pytest
from harness_gateway.models import MessageEvent, MessageEventType, TextContent

from artemis.infra.gateway.channels.wecom_final_only import (
    FinalOnlyWeComChannel,
    FinalOnlyWeComConfig,
)


class FakeAibotClient:
    def __init__(self) -> None:
        self.reply_stream_calls: list[str] = []
        self.sent_messages: list[tuple[str, dict[str, object]]] = []

    async def reply_stream(
        self, _frame: object, _stream_id: str, content: str, _finish: bool
    ) -> None:
        self.reply_stream_calls.append(content)

    async def send_message(self, chat_id: str, body: dict[str, object]) -> None:
        self.sent_messages.append((chat_id, body))


@pytest.mark.asyncio
async def test_final_only_sends_ack_then_final_message() -> None:
    client = FakeAibotClient()
    channel = FinalOnlyWeComChannel(
        processor=None,
        config=FinalOnlyWeComConfig(bot_id="bot", secret="secret"),
        client=client,
    )

    await channel.send_final_for_test({"body": {"chatid": "chat-1"}}, "审批节点会生成待办。")

    assert client.reply_stream_calls == ["正在分析，请稍候…"]
    assert client.sent_messages == [
        ("chat-1", {"msgtype": "markdown", "markdown": {"content": "审批节点会生成待办。"}})
    ]


@pytest.mark.asyncio
async def test_final_only_splits_long_final_messages_for_wecom() -> None:
    client = FakeAibotClient()
    channel = FinalOnlyWeComChannel(
        processor=None,
        config=FinalOnlyWeComConfig(bot_id="bot", secret="secret"),
        client=client,
    )
    text = "a" * 2_001

    await channel.send_final_for_test({"body": {"chatid": "chat-1"}}, text)

    assert [body["markdown"]["content"] for _, body in client.sent_messages] == [
        "a" * 2_000,
        "a",
    ]


@pytest.mark.asyncio
async def test_final_only_hides_intermediate_events() -> None:
    async def processor(_message: object):
        yield MessageEvent(type=MessageEventType.DELTA, content=[TextContent(text="intermediate")])
        yield MessageEvent(type=MessageEventType.MESSAGE, content=[TextContent(text="final")])

    client = FakeAibotClient()
    channel = FinalOnlyWeComChannel(
        processor=processor,
        config=FinalOnlyWeComConfig(bot_id="bot", secret="secret"),
        client=client,
    )
    await channel.handle_inbound({"chatid": "chat-1", "msgtype": "text", "text": {"content": "q"}})

    assert client.reply_stream_calls == ["正在分析，请稍候…"]
    assert client.sent_messages[0][1]["markdown"] == {"content": "final"}


@pytest.mark.asyncio
async def test_final_only_accepts_a_preparsed_inbound_message() -> None:
    async def processor(_message: object):
        yield MessageEvent(type=MessageEventType.MESSAGE, content=[TextContent(text="final")])

    client = FakeAibotClient()
    channel = FinalOnlyWeComChannel(
        processor=processor,
        config=FinalOnlyWeComConfig(bot_id="bot", secret="secret"),
        client=client,
    )
    inbound = channel.parse_inbound(
        {"chatid": "chat-1", "msgtype": "text", "text": {"content": "q"}}
    )

    await channel.handle_inbound(inbound)

    assert client.sent_messages[0][0] == "chat-1"
