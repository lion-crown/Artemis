"""AgentScope-style bounded code investigation for business answers."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from artemis.infra.agents.business_model import BusinessOpenAIModel
from artemis.infra.agents.business_workspace import BusinessWorkspaceReader

_MAX_TOOL_CALLS = 2

_INVESTIGATION_SYSTEM_PROMPT = """你是业务问答助手，回答关于公司业务系统的问题。
回答前必须用 grep、glob 或 read 核对真实业务材料，不能凭记忆猜测。默认在 backend 范围调查；只有用户明确询问页面、前端或界面时，才切换到其他范围。优先用 grep 按具体关键词定位；glob 只用于寻找特定文件；read 用于读取已经定位的文件片段。
最多进行 2 次工具调用。每次调用必须围绕用户原始问题，并优先核对触发条件、状态判断、角色、场景差异、例外和结果。两次工具调用后，或一旦材料足够，必须直接输出最终业务答复，不能继续调用工具。

最终答复面向业务人员：
1. 先给明确业务结论，用“✅ 可以”“❌ 不可以”或“⚠️ 待确认”标识。
2. 若问题比较多个独立对象，必须分别给出每个对象的结论，不能用一个笼统的“视条件而定”替代。
3. 用“归纳维度：……”说明比较维度，并用 Markdown 表格直接回答用户问到的条件、角色、状态、类型、例外或影响。
4. 最后用简短总结收束适用边界；只有用户明确问如何操作时才给操作建议。
5. 只用业务语言。不得提及代码、文件、路径、表名、字段、方法、接口、工具、模型或调查过程；不得输出工具调用格式。
6. 材料不能确认的内容必须明确写“待确认”，不得猜测或编造。"""

_DIRECT_ANSWER_REQUEST = "工具调用已结束。请立即基于已核实材料直接输出最终业务答复。"

_ClientFactory = Callable[[BusinessOpenAIModel], Any]


class BusinessInvestigationCancelled(Exception):
    """Raised when a user stops a controlled business investigation."""


@dataclass(frozen=True)
class BusinessInvestigationResult:
    """Direct business answer and OpenAI-wire messages from one investigation."""

    answer: str
    usage: dict[str, Any] | None
    messages: list[dict[str, Any]]


def _tool_schemas(reader: BusinessWorkspaceReader) -> list[dict[str, Any]]:
    scopes = sorted(reader.scopes)
    scope_property = {"type": "string", "enum": scopes}
    return [
        {
            "type": "function",
            "function": {
                "name": "grep",
                "description": "在业务代码材料中搜索关键词，返回匹配行及上下文。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": scope_property,
                        "glob": {"type": "string"},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
                        "case_insensitive": {"type": "boolean"},
                    },
                    "required": ["pattern", "path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "glob",
                "description": "按文件名模式在指定业务范围内查找材料。",
                "parameters": {
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}, "path": scope_property},
                    "required": ["pattern", "path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read",
                "description": "读取已经定位到的公开业务材料片段，行号从 1 开始。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "offset": {"type": "integer", "minimum": 1},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 300},
                    },
                    "required": ["file_path"],
                },
            },
        },
    ]


async def _await_or_cancel[T](awaitable: Awaitable[T], cancelled: asyncio.Event) -> T:
    if cancelled.is_set():
        raise BusinessInvestigationCancelled()
    operation = asyncio.ensure_future(awaitable)
    cancellation = asyncio.create_task(cancelled.wait())
    done, _pending = await asyncio.wait(
        {operation, cancellation}, return_when=asyncio.FIRST_COMPLETED
    )
    if cancellation in done:
        operation.cancel()
        with suppress(asyncio.CancelledError):
            await operation
        raise BusinessInvestigationCancelled()
    cancellation.cancel()
    with suppress(asyncio.CancelledError):
        await cancellation
    return await operation


def _message_from_completion(completion: object) -> object:
    choices = getattr(completion, "choices", None)
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("business model returned no completion choices")
    message = getattr(choices[0], "message", None)
    if message is None:
        raise RuntimeError("business model returned no completion message")
    return message


def _text(message: object) -> str:
    return str(getattr(message, "content", "") or "").strip()


def _tool_calls(message: object) -> list[object]:
    raw = getattr(message, "tool_calls", None)
    return list(raw) if isinstance(raw, list) else []


def _tool_call_wire(call: object) -> dict[str, Any]:
    function = getattr(call, "function", None)
    return {
        "id": str(getattr(call, "id", "") or ""),
        "type": str(getattr(call, "type", "function") or "function"),
        "function": {
            "name": str(getattr(function, "name", "") or ""),
            "arguments": str(getattr(function, "arguments", "{}") or "{}"),
        },
    }


def _assistant_wire(message: object, calls: list[object]) -> dict[str, Any]:
    out: dict[str, Any] = {"role": "assistant", "content": _text(message) or None}
    if calls:
        out["tool_calls"] = [_tool_call_wire(call) for call in calls]
    return out


def _arguments(call: object) -> dict[str, Any]:
    raw = getattr(getattr(call, "function", None), "arguments", "{}")
    try:
        parsed = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


async def _execute_tool(
    reader: BusinessWorkspaceReader,
    call: object,
    *,
    cancelled: asyncio.Event,
) -> str:
    function = getattr(call, "function", None)
    name = str(getattr(function, "name", "") or "")
    args = _arguments(call)
    try:
        if name == "grep":
            return await _await_or_cancel(
                reader.grep(
                    pattern=str(args.get("pattern") or ""),
                    scope=str(args.get("path") or ""),
                    file_glob=str(args["glob"]) if args.get("glob") else None,
                    max_results=int(args.get("max_results") or 50),
                    case_insensitive=bool(args.get("case_insensitive", False)),
                ),
                cancelled,
            )
        if name == "glob":
            return await _await_or_cancel(
                reader.glob(
                    pattern=str(args.get("pattern") or ""), scope=str(args.get("path") or "")
                ),
                cancelled,
            )
        if name == "read":
            return await _await_or_cancel(
                reader.read(
                    path=str(args.get("file_path") or ""),
                    offset=int(args.get("offset") or 1),
                    limit=int(args.get("limit") or 100),
                ),
                cancelled,
            )
    except BusinessInvestigationCancelled:
        raise
    except Exception:
        return "业务材料暂时不可读取。"
    return "该业务材料工具不可用。"


def _usage(completions: list[object], model: BusinessOpenAIModel) -> dict[str, Any] | None:
    if not completions:
        return None
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for completion in completions:
        usage = getattr(completion, "usage", None)
        input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens or input_tokens + output_tokens,
        "model": model.model,
        "model_calls": len(completions),
    }


def business_investigation_trajectory_chunks(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project controlled tool calls into the standard trajectory format."""
    names: dict[str, str] = {}
    chunks: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "assistant":
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list):
                continue
            for call in tool_calls:
                if not isinstance(call, Mapping):
                    continue
                call_id = str(call.get("id") or "")
                function = call.get("function")
                if not call_id or not isinstance(function, Mapping):
                    continue
                name = str(function.get("name") or "tool")
                names[call_id] = name
                chunks.append(
                    {
                        "type": "tool_call_chunk",
                        "id": call_id,
                        "name": name,
                        "args": function.get("arguments"),
                    }
                )
        elif message.get("role") == "tool":
            call_id = str(message.get("tool_call_id") or "")
            if call_id:
                chunks.append(
                    {
                        "type": "tool_result",
                        "id": call_id,
                        "name": names.get(call_id, "business_material"),
                        "content": message.get("content"),
                    }
                )
    return chunks


def _default_client(model: BusinessOpenAIModel) -> Any:
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=model.api_key,
        base_url=model.base_url,
        default_headers=model.headers or None,
    )


async def _close_client(client: object) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result


async def _complete(
    *,
    client: Any,
    model: BusinessOpenAIModel,
    messages: list[dict[str, Any]],
    settings: Mapping[str, Any],
    cancelled: asyncio.Event,
    tools: list[dict[str, Any]] | None,
) -> object:
    if cancelled.is_set():
        raise BusinessInvestigationCancelled()
    kwargs: dict[str, Any] = {"model": model.model, "messages": messages, **settings}
    if tools is not None:
        kwargs["tools"] = tools
    return await _await_or_cancel(client.chat.completions.create(**kwargs), cancelled)


class BusinessInvestigationRunner:
    """Run up to two material lookups, then return the model's direct answer."""

    def __init__(self, *, client_factory: _ClientFactory = _default_client) -> None:
        self._client_factory = client_factory

    async def answer(
        self,
        *,
        model: BusinessOpenAIModel,
        reader: BusinessWorkspaceReader,
        question: str,
        cancelled: asyncio.Event,
        model_settings: Mapping[str, Any] | None = None,
    ) -> BusinessInvestigationResult:
        settings = {
            key: value
            for key, value in dict(model_settings or {}).items()
            if key in {"temperature", "top_p", "max_tokens"}
        }
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _INVESTIGATION_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        completions: list[object] = []
        client = self._client_factory(model)
        tool_calls_used = 0
        try:
            while tool_calls_used < _MAX_TOOL_CALLS:
                completion = await _complete(
                    client=client,
                    model=model,
                    messages=messages,
                    settings=settings,
                    cancelled=cancelled,
                    tools=_tool_schemas(reader),
                )
                completions.append(completion)
                message = _message_from_completion(completion)
                calls = _tool_calls(message)
                messages.append(_assistant_wire(message, calls))
                answer = _text(message)
                if not calls:
                    if answer:
                        return BusinessInvestigationResult(
                            answer=answer,
                            usage=_usage(completions, model),
                            messages=messages,
                        )
                    break

                remaining = _MAX_TOOL_CALLS - tool_calls_used
                for index, call in enumerate(calls[:remaining]):
                    result = await _execute_tool(reader, call, cancelled=cancelled)
                    call_id = str(getattr(call, "id", "") or f"business-{tool_calls_used}-{index}")
                    messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
                    tool_calls_used += 1

            messages.append({"role": "user", "content": _DIRECT_ANSWER_REQUEST})
            completion = await _complete(
                client=client,
                model=model,
                messages=messages,
                settings=settings,
                cancelled=cancelled,
                tools=None,
            )
            completions.append(completion)
            message = _message_from_completion(completion)
            answer = _text(message)
            if not answer:
                raise RuntimeError("business model returned an empty direct answer")
            messages.append(_assistant_wire(message, []))
            return BusinessInvestigationResult(
                answer=answer,
                usage=_usage(completions, model),
                messages=messages,
            )
        finally:
            await _close_client(client)


__all__ = [
    "BusinessInvestigationCancelled",
    "BusinessInvestigationResult",
    "BusinessInvestigationRunner",
    "business_investigation_trajectory_chunks",
]
