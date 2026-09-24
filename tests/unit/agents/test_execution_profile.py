from artemis.infra.agents.execution_profile import (
    BUSINESS_SYSTEM_QA,
    additional_business_reply_instruction,
    apply_execution_profile,
)


def test_lean_code_qa_profile_disables_memory_and_non_code_tools() -> None:
    config = apply_execution_profile({"execution_profile": "lean_code_qa"})

    assert config["memory"]["memory_enabled"] is False
    assert config["max_input_length"] == 16_000
    assert "max_iters" not in config
    assert {"memory_search", "web_fetch", "browser_use"} <= set(config["tools_disabled"])
    assert "grep" not in config["tools_disabled"]
    assert "read_file" not in config["tools_disabled"]


def test_lean_code_qa_profile_requires_frontend_to_backend_trace_for_ui_questions() -> None:
    config = apply_execution_profile({"execution_profile": "lean_code_qa"})

    assert "frontend" in config["execution_profile_instruction"].lower()
    assert "backend" in config["execution_profile_instruction"].lower()


def test_lean_code_qa_profile_requires_business_language_final_answer() -> None:
    config = apply_execution_profile({"execution_profile": "lean_code_qa"})

    instruction = config["execution_profile_instruction"].lower()
    assert "business language" in instruction
    assert "source paths" in instruction


def test_custom_business_reply_guidance_is_an_additive_preference() -> None:
    instruction = additional_business_reply_instruction("面向销售同事，先说结论，再说明影响。")

    assert instruction is not None
    assert "does not conflict with system rules" in instruction
    assert "面向销售同事" in instruction


def test_blank_custom_business_reply_guidance_is_ignored() -> None:
    assert additional_business_reply_instruction("  ") is None


def test_standard_profile_preserves_existing_config() -> None:
    config = apply_execution_profile({"execution_profile": "standard", "max_input_length": 42_000})

    assert config == {"execution_profile": "standard", "max_input_length": 42_000}


def test_business_system_qa_leaves_investigation_budget_to_the_controlled_runner() -> None:
    config = apply_execution_profile({"execution_profile": BUSINESS_SYSTEM_QA})

    assert config["memory"]["memory_enabled"] is False
    assert config["investigation_mode"] == "business_workspace"
    instruction = config["execution_profile_instruction"]
    assert "精准关键词搜索" in instruction
    assert "触发条件" in instruction
    assert "角色" in instruction
    assert "场景差异" in instruction
    assert "例外" in instruction
    assert "两轮" not in instruction
    assert "最多进行 10 次工具调用" not in instruction
    assert "完整业务答案" in instruction
    assert "过程性表达" in instruction
    assert "不进行代码的多余解读" in instruction
    assert "技术名词" in instruction
    assert "表名" in instruction
    assert "字段名" in instruction
    assert "不要用 Glob 做宽泛搜索" in instruction
    assert "每次搜索前回顾用户原始问题" in instruction
