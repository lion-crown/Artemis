"""Unit tests for chat SSE / WebSocket chunk serialization."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from artemis.api.routers.chat.sse import json_chunk_default


def test_json_chunk_default_serializes_langchain_messages() -> None:
    chunk = {
        "type": "state_update",
        "node": "BootstrapMiddleware.before_agent",
        "data": {
            "messages": [
                SystemMessage(content="bootstrap"),
                HumanMessage(content="hi"),
                AIMessage(content="hello"),
            ],
        },
    }
    payload = json.dumps(chunk, default=json_chunk_default)
    parsed = json.loads(payload)
    assert parsed["type"] == "state_update"
    assert len(parsed["data"]["messages"]) == 3
    assert parsed["data"]["messages"][0]["content"] == "bootstrap"
