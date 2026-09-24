from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from artemis.infra.agents.business_model import BusinessOpenAIModel
from artemis.infra.gateway.process.business_investigation import (
    _INVESTIGATION_SYSTEM_PROMPT,
    _MAX_TOOL_CALLS,
    BusinessInvestigationCancelled,
    BusinessInvestigationRunner,
    _tool_schemas,
    business_investigation_trajectory_chunks,
)


@dataclass
class _Reader:
    greps: list[dict[str, object]] = field(default_factory=list)
    scopes: dict[str, str] = field(default_factory=lambda: {"backend": "/"})

    async def grep(
        self,
        *,
        pattern: str,
        scope: str,
        file_glob: str | None,
        max_results: int,
        case_insensitive: bool,
    ) -> str:
        self.greps.append(
            {
                "pattern": pattern,
                "scope": scope,
                "file_glob": file_glob,
                "max_results": max_results,
                "case_insensitive": case_insensitive,
            }
        )
        return "已核实：会议结束不收回提交权限。"

    async def glob(self, *, pattern: str, scope: str) -> str:
        return "没有匹配的文件。"

    async def read(self, *, path: str, offset: int, limit: int) -> str:
        return "已核实：照片审批中不可重复提交。"


def _tool_call(call_id: str, *, pattern: str = "photo") -> object:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(
            name="grep",
            arguments=json.dumps(
                {
                    "pattern": pattern,
                    "path": "backend",
                    "max_results": 5,
                    "case_insensitive": False,
                }
            ),
        ),
    )


def _completion(*, content: str = "", tool_calls: list[object] | None = None) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class _Completions:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> object:
        self.calls.append(copy.deepcopy(kwargs))
        if not self._responses:
            raise AssertionError("unexpected additional model request")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _Client:
    def __init__(self, responses: list[object]) -> None:
        self.completions = _Completions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def _model() -> BusinessOpenAIModel:
    return BusinessOpenAIModel(
        model="glm-5.2",
        base_url="https://example.invalid/v1",
        api_key="test-key",
        headers={},
    )


def test_investigation_prompt_uses_agentscope_search_and_business_answer_rules() -> None:
    assert "最多进行 2 次工具调用" in _INVESTIGATION_SYSTEM_PROMPT
    assert "直接输出最终业务答复" in _INVESTIGATION_SYSTEM_PROMPT
    assert "归纳维度：" in _INVESTIGATION_SYSTEM_PROMPT
    assert "多个独立对象" in _INVESTIGATION_SYSTEM_PROMPT
    assert "代码、文件、路径" in _INVESTIGATION_SYSTEM_PROMPT


def test_tool_limit_matches_agentscope_search_budget() -> None:
    assert _MAX_TOOL_CALLS == 2


def test_tool_schemas_match_agentscope_code_mount_names() -> None:
    assert [tool["function"]["name"] for tool in _tool_schemas(_Reader())] == [
        "grep",
        "glob",
        "read",
    ]


def test_business_investigation_trajectory_chunks_preserve_tool_inputs_and_outputs() -> None:
    messages = [
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
        {"role": "tool", "tool_call_id": "call-1", "content": "匹配到直接提交规则"},
    ]

    assert list(business_investigation_trajectory_chunks(messages)) == [
        {
            "type": "tool_call_chunk",
            "id": "call-1",
            "name": "grep",
            "args": '{"pattern":"现场照片","path":"backend"}',
        },
        {
            "type": "tool_result",
            "id": "call-1",
            "name": "grep",
            "content": "匹配到直接提交规则",
        },
    ]


@pytest.mark.asyncio
async def test_runner_sends_the_first_direct_business_answer_without_a_second_finalizer() -> None:
    reader = _Reader()
    client = _Client(
        [
            _completion(tool_calls=[_tool_call("evidence")]),
            _completion(content="✅ 可以。会议结束不收回提交权限。"),
        ]
    )
    runner = BusinessInvestigationRunner(client_factory=lambda _model: client)

    result = await runner.answer(
        model=_model(),
        reader=reader,  # type: ignore[arg-type]
        question="会议结束后，现场照片是否还能提交？",
        cancelled=asyncio.Event(),
    )

    assert result.answer == "✅ 可以。会议结束不收回提交权限。"
    assert len(client.completions.calls) == 2
    assert "tools" in client.completions.calls[0]
    assert "tools" in client.completions.calls[1]
    assert len(reader.greps) == 1


@pytest.mark.asyncio
async def test_runner_forces_one_direct_answer_after_two_tool_calls() -> None:
    reader = _Reader()
    client = _Client(
        [
            _completion(tool_calls=[_tool_call("first", pattern="支持性材料")]),
            _completion(tool_calls=[_tool_call("second", pattern="GOA")]),
            _completion(content="对象A：✅ 可以；对象B：⚠️ 待确认。"),
        ]
    )
    runner = BusinessInvestigationRunner(client_factory=lambda _model: client)

    result = await runner.answer(
        model=_model(),
        reader=reader,  # type: ignore[arg-type]
        question="支持性材料和GOA审批文件分别有什么条件？",
        cancelled=asyncio.Event(),
    )

    assert result.answer == "对象A：✅ 可以；对象B：⚠️ 待确认。"
    assert len(client.completions.calls) == 3
    assert all("tools" in call for call in client.completions.calls[:2])
    assert "tools" not in client.completions.calls[-1]
    assert len(reader.greps) == 2


@pytest.mark.asyncio
async def test_runner_honors_a_preexisting_cancellation() -> None:
    cancelled = asyncio.Event()
    cancelled.set()
    runner = BusinessInvestigationRunner(client_factory=lambda _model: _Client([]))

    with pytest.raises(BusinessInvestigationCancelled):
        await runner.answer(
            model=_model(),
            reader=_Reader(),  # type: ignore[arg-type]
            question="问题",
            cancelled=cancelled,
        )
