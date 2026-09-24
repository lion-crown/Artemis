from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from harness_gateway.models import ChannelSubject, InboundMessage, TextContent
from tests.support.fakes import FakeHarnessAgent

from artemis.infra.gateway.process.business_investigation import BusinessInvestigationResult
from artemis.infra.gateway.process.processor import GlobalProcessor
from artemis.infra.gateway.slash.dispatcher import SlashDispatcher


def _processor(agent: FakeHarnessAgent, *, runner: object) -> GlobalProcessor:
    manager = MagicMock()
    manager.get_agent = MagicMock(return_value=agent)
    manager.get_config = MagicMock(return_value={"execution_profile": "business_system_qa"})
    manager.artemis_config = SimpleNamespace(max_upload_bytes=10_000_000)
    manager.merge_turn_mcp_servers = MagicMock(return_value=None)
    manager.prepare_chat_mcp = AsyncMock(return_value=[])
    manager.get_row = MagicMock(return_value=None)
    manager.get_thread_model = MagicMock(return_value=None)
    manager.providers.is_model_ref_usable = MagicMock(return_value=False)
    manager.providers.resolve_explicit_default_model = MagicMock(return_value=None)
    manager.providers.resolve_model_for_multimodal_turn = MagicMock(
        side_effect=lambda ref, **_kwargs: ref
    )
    manager.get_business_openai_model = MagicMock(return_value=MagicMock())
    manager.begin_business_investigation = MagicMock(return_value=asyncio.Event())
    manager.end_business_investigation = MagicMock()

    threads = MagicMock()
    threads.get_or_create_by_key = AsyncMock(return_value="thread-1")
    agent_repo = MagicMock()
    agent_repo.get = MagicMock(return_value=MagicMock(user_id=7, default_model=None))
    return GlobalProcessor(
        agent_manager=manager,
        thread_registry=threads,
        audit_repo=MagicMock(),
        agent_repo=agent_repo,
        user_repo=MagicMock(),
        connector_repo=MagicMock(),
        dispatcher=SlashDispatcher(),
        usage_repo=None,
        gateway=None,
        business_runner=runner,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_im_business_system_qa_emits_only_the_controlled_final_answer(
    tmp_path: Path,
) -> None:
    runner = MagicMock()
    runner.answer = AsyncMock(
        return_value=BusinessInvestigationResult(
            answer="会议结束后可以提交。", usage=None, messages=[]
        )
    )
    processor = _processor(
        FakeHarnessAgent(workspace_dir=tmp_path, virtual_mode=True), runner=runner
    )
    message = InboundMessage(
        channel_id="wecom",
        channel_type="wecom",
        tenant_id="agent-1",
        channel_subject=ChannelSubject(subject_id="user-1"),
        content=[TextContent(text="会议结束后，现场照片是否还能提交？")],
    )

    async def unexpected_project_stream(*_args: object, **_kwargs: object):
        raise AssertionError("business profile must not enter generic ReAct streaming")
        yield None  # pragma: no cover

    with patch(
        "artemis.infra.gateway.process.processor.project_stream",
        new=unexpected_project_stream,
    ):
        events = [event async for event in processor(message)]

    content = "\n".join(
        part.text
        for event in events
        for part in event.content or []
        if isinstance(part, TextContent)
    )
    assert content == "会议结束后可以提交。"
    runner.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_business_system_qa_emits_only_a_final_token(tmp_path: Path) -> None:
    runner = MagicMock()
    runner.answer = AsyncMock(
        return_value=BusinessInvestigationResult(answer="业务结论", usage=None, messages=[])
    )
    processor = _processor(
        FakeHarnessAgent(workspace_dir=tmp_path, virtual_mode=True), runner=runner
    )
    message = InboundMessage(
        channel_id="dashboard",
        channel_type="dashboard",
        tenant_id="agent-1",
        channel_subject=ChannelSubject(subject_id="user-1"),
        content=[TextContent(text="业务问题")],
        metadata={"thread_id": "thread-1", "mcp_servers": []},
    )

    chunks = [chunk async for chunk in processor.iter_turn_chunks(message)]

    assert chunks == [
        {"type": "token", "content": "业务结论", "node": "business_investigation"},
        {"type": "done"},
    ]
    runner.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_business_system_qa_records_controlled_tool_trace(tmp_path: Path) -> None:
    runner = MagicMock()
    runner.answer = AsyncMock(
        return_value=BusinessInvestigationResult(
            answer="业务结论",
            usage=None,
            messages=[
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "grep",
                                "arguments": '{"pattern":"现场照片","path":"backend"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "content": "匹配到提交规则",
                },
            ],
        )
    )
    processor = _processor(
        FakeHarnessAgent(workspace_dir=tmp_path, virtual_mode=True), runner=runner
    )
    observed: list[dict[str, object]] = []
    processor._observe_trajectory = lambda **kwargs: observed.append(kwargs["chunk"])  # type: ignore[method-assign]
    message = InboundMessage(
        channel_id="dashboard",
        channel_type="dashboard",
        tenant_id="agent-1",
        channel_subject=ChannelSubject(subject_id="user-1"),
        content=[TextContent(text="业务问题")],
        metadata={"thread_id": "thread-1", "mcp_servers": []},
    )

    _chunks = [chunk async for chunk in processor.iter_turn_chunks(message)]

    assert {
        "type": "tool_call_chunk",
        "id": "call-1",
        "name": "grep",
        "args": '{"pattern":"现场照片","path":"backend"}',
    } in observed
    assert {
        "type": "tool_result",
        "id": "call-1",
        "name": "grep",
        "content": "匹配到提交规则",
    } in observed
