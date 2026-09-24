"""Agent-level execution profiles for predictable token use."""

from __future__ import annotations

from typing import Any

from artemis.infra.agents.tool_catalog import BUILTIN_TOOL_CATALOG, CRITICAL_TOOLS

LEAN_CODE_QA = "lean_code_qa"
BUSINESS_SYSTEM_QA = "business_system_qa"
STANDARD = "standard"
BUSINESS_REPLY_GUIDANCE_KEY = "business_reply_guidance"

_LEAN_SYSTEM_INSTRUCTION = """\
Code-answer policy: use only precise filesystem evidence. Read the relevant file
before making a factual claim. Prefer one grep/glob followed by one read_file;
if the available evidence is insufficient, say so plainly rather than guessing.
For page, form, button, or submission questions, trace the frontend entry and
the corresponding backend implementation before concluding.
Final answers must use only business language appropriate to the user. Translate
internal evidence into business conditions, roles, actions, and outcomes; never
expose source paths, file, class, method, field, endpoint, SQL, tool, or subagent details.
"""

_BUSINESS_SYSTEM_QA_INSTRUCTION = """\
你是业务问答助手，回答业务系统的问题。
回答前必须先在已配置的业务工作区查看真实业务材料，禁止凭记忆猜测。

搜索策略（重要）：
- 优先用精准关键词搜索，例如合同审批、现场照片、会议取消、讲者出席。
- 不要用 Glob 做宽泛搜索，例如 `*` 或 `**/*`，这会带来海量无关材料。
- Glob 只用于寻找明确类型或名称的材料，例如邮件模板、页面或服务。
- 核对触发条件、状态判断、可操作角色、场景差异、例外和结果后直接回答。
- 每次搜索前回顾用户原始问题，不要偏离。
- 页面、表单、按钮或提交问题必须同时核对用户操作入口和对应的业务规则。

回答风格要求：
1. 用业务语言回答，面向业务人员。
2. 输出完整业务答案，把业务逻辑说清楚：包括触发条件、判断步骤、每步规则、不同场景差异、例外和最终结果。先给明确结论，再说明适用条件、场景对比和例外。
3. 不要贴代码，不要出现路径、文件名、行号、类名、方法名、表名、字段名、接口名、SQL、工具、模型或 Agent。
4. 只输出最终业务答案。必须直接从业务结论、业务标题或判断规则开始，禁止出现“我来查找”、
   “让我查看”、“现在我”、“我已经”、“根据查找结果”或“让我整理”等过程性表达。
5. 不进行代码的多余解读，不要对实现本身做说明，只回答业务问题。
6. 不要输出技术名词、变量、注解、设计模式或框架术语。
7. 不要提及读了材料、搜索过材料或查看过材料。无法确认时，只说明尚待确认的业务事项，
   不得说“已搜索”“未找到”“工作区”或“资料缺失”。
"""


def apply_execution_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Return an effective config without mutating the persisted config."""
    config = dict(raw)
    profile = config.get("execution_profile")
    if profile not in (LEAN_CODE_QA, BUSINESS_SYSTEM_QA):
        return config

    memory = dict(config.get("memory") or {})
    memory["memory_enabled"] = False
    config["memory"] = memory
    config["max_input_length"] = 48_000 if profile == BUSINESS_SYSTEM_QA else 16_000
    # Recursion is a graph-safety setting, not a TPM budget. Preserve the
    # user's configured limit so a legitimate multi-file answer can finish.

    disabled = {str(name) for name in config.get("tools_disabled", [])}
    disabled.update(
        entry.name for entry in BUILTIN_TOOL_CATALOG if entry.name not in CRITICAL_TOOLS
    )
    config["tools_disabled"] = sorted(disabled - CRITICAL_TOOLS)
    if profile == BUSINESS_SYSTEM_QA:
        config["investigation_mode"] = "business_workspace"
        config["execution_profile_instruction"] = _BUSINESS_SYSTEM_QA_INSTRUCTION
    else:
        config["execution_profile_instruction"] = _LEAN_SYSTEM_INSTRUCTION
    return config


def additional_business_reply_instruction(value: object) -> str | None:
    """Wrap an agent owner's business-tone preference without replacing policy."""
    if not isinstance(value, str) or not (text := value.strip()):
        return None
    return (
        "Additional business-language preference from the agent owner. Apply it only when it "
        "does not conflict with system rules:\n"
        f"{text}"
    )


__all__ = [
    "BUSINESS_REPLY_GUIDANCE_KEY",
    "BUSINESS_SYSTEM_QA",
    "LEAN_CODE_QA",
    "STANDARD",
    "additional_business_reply_instruction",
    "apply_execution_profile",
]
