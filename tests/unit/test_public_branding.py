"""Regression guard for the product name shown in public repository surfaces."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_ROOTS = (
    "README.md",
    "README_CN.md",
    "LICENSE",
    "pyproject.toml",
    ".env.example",
    "Makefile",
    "docs",
    "docker",
    "desktop",
    ".github",
    "plugins",
    "dashboard",
)
EXCLUDED_PATH_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "vendor",
    }
)
RETAINED_PROTOCOL_KEYS = (
    "artemis:active-agent",
    "artemis:admin-agents-view",
    "artemis:agent_errors",
    "artemis:browser-panel:mode",
    "artemis:browser-panel:size",
    "artemis:browser-panel:viewport-mode",
    "artemis:chat-connectors:",
    "artemis:chat-dock:mode",
    "artemis:chat-dock:size",
    "artemis:chat-draft:",
    "artemis:chat-sidebar:open",
    "artemis:chat-sidebar:width",
    "artemis:chunk-reload",
    "artemis:connector-oauth",
    "artemis:connectors-changed",
    "artemis:expand-chat-rail",
    "artemis:experts-view",
    "artemis:file-panel:mode",
    "artemis:file-panel:size",
    "artemis:forbidden",
    "artemis:form-draft:",
    "artemis:knowledge-bases-docs-view",
    "artemis:knowledge-bases:list-collapsed",
    "artemis:knowledge-bases:sidebar-width",
    "artemis:layout-mode",
    "artemis:minimal-agent-folders-collapsed",
    "artemis:open-nav-records",
    "artemis:pending-chat-message",
    "artemis:personalization:tab",
    "artemis:remote-browser:ai-panel-height",
    "artemis:remote-browser:ai-panel-open",
    "artemis:remote-browser:ai-panel-width",
    "artemis:remote-browser:harness-profile",
    "artemis:remote-browser:refresh-interval",
    "artemis:remote-browser:session-id",
    "artemis:remote-browser:stream-active",
    "artemis:remote-browser:viewport",
    "artemis:remote-desktop:max-fps",
    "artemis:remote-desktop:resolution",
    "artemis:remote-desktop:tab",
    "artemis:remote-phone:ai-panel-height",
    "artemis:remote-phone:ai-panel-open",
    "artemis:remote-phone:ai-panel-width",
    "artemis:remote-phone:shell-panel-open",
    "artemis:remote-phone:shell-split-width",
    "artemis:remote-phone:stream-quality",
    "artemis:remote-phone:view-tab",
    "artemis:setup-jwt",
    "artemis:sidebar-minimal-pane-v2",
    "artemis:sidebar-nav-groups",
    "artemis:sidebar:collapsed",
    "artemis:skill-drawer-tree-collapsed",
    "artemis:skill-packages:list-collapsed",
    "artemis:skill-packages:sidebar-width",
    "artemis:skillhub-rankings:v1",
    "artemis:stream_errors",
    "artemis:terminal-ai-height",
    "artemis:terminal-ai-layout",
    "artemis:terminal-ai-width",
    "artemis:terminal-sessions",
    "artemis:test-list-collapsed",
    "artemis:toggle-nav",
    "artemis:ui-locale",
    "artemis:ui-palette",
    "artemis:unauthorized",
    "artemis:wizard-draft",
    "artemis:wizard-step",
    "artemis:wizard-token",
    "artemis:workbench:tab",
    "artemis:workspace-drawer-tree-collapsed",
    "artemis:workspace-drawer-tree-width",
)
RETAINED_PROTOCOL_PREFIXES = tuple(key for key in RETAINED_PROTOCOL_KEYS if key.endswith(":"))
RETAINED_PROTOCOL_KEY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.:-])(?:"
    + "|".join(re.escape(key) for key in RETAINED_PROTOCOL_KEYS if not key.endswith(":"))
    + r")(?![A-Za-z0-9_.:-])"
)
# Error-code protocol keys are dynamically selected from this fixed source list.
RETAINED_DYNAMIC_PROTOCOL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.:-])artemis:agent_errors\."
    r"(?:no_models_configured|model_ref_unavailable)(?![A-Za-z0-9_.:-])"
)
RUNTIME_PROTOCOL_SOURCE_ROOTS = frozenset({"dashboard", "desktop", "src"})
RUNTIME_PACKAGE_SOURCE_ROOTS = frozenset({"desktop", "src"})
ALLOWED_COMPATIBILITY_TOKENS = (
    re.compile(r"src/artemis(?:/|\b)"),
    re.compile(r"ARTEMIS_[A-Z0-9_]+"),
    re.compile(r"(?:~|/data)/\.artemis(?:/|\b)"),
    re.compile(r"(?<![A-Za-z0-9_])\.artemis(?:/|\b)"),
    re.compile(r"\boctop\.db\b"),
    re.compile(r"\boctop-login\.txt\b"),
    re.compile(r"\boctop\.log(?:\.[A-Za-z0-9_-]+)*\b"),
    re.compile(r"\boctop\.\*"),
    re.compile(r"\boctop\.(?:infra|cli|launch)(?:\.[A-Za-z_][A-Za-z0-9_]*)+"),
    re.compile(r"\boctop(?:-auto)?-backup-[A-Za-z0-9_.*-]+\.tar\.gz"),
)
# These deployment-only references are binary/package compatibility contracts,
# not product-facing names. Keep this map deliberately path-specific: a new
# public Artemis reference anywhere else must continue to fail the guard.
RETAINED_DEPLOYMENT_COMPATIBILITY_TOKENS = {
    "pyproject.toml": (re.compile(r"artemis(?:\.[A-Za-z_][A-Za-z0-9_]*)+"),),
    "docker/docker-entrypoint.sh": (re.compile(r"\$\{HOME\}/\.artemis\b"),),
    "desktop/portable/verify_imports.py": (re.compile(r'"artemis",'),),
    "desktop/portable/package.sh": (
        re.compile(r"artemis-\*\.whl"),
        re.compile(r"\bartemis_version\b"),
    ),
    "desktop/portable/_common.sh": (
        re.compile(r"\bartemis_version\b"),
        re.compile(r"artemis-unsupported"),
    ),
    "desktop/portable/templates/launch.py": (re.compile(r'run_module\("artemis"'),),
    "desktop/src/download.go": (
        re.compile(r"artemis-\*\.dist-info"),
        re.compile(r'"/artemis-"'),
        re.compile(r"\bartemis_version\b"),
    ),
    "desktop/src/settings.go": (re.compile(r'"\.artemis"'),),
    "desktop/src/window_chrome.go": (
        re.compile(r"artemis-desktop-drag"),
        re.compile(r"data-artemis-no-drag"),
        re.compile(r"artemis-desktop-no-drag"),
    ),
    "desktop/src/assets/index.html": (
        re.compile(r"artemis-desktop-drag"),
        re.compile(r"data-artemis-no-drag"),
        re.compile(r"artemis-mascot-(?:peek|type)\.webp"),
    ),
    "desktop/src/download_test.go": (
        re.compile(r'"Artemis-test/packages/artemis-"'),
        re.compile(r"\bartemis_version="),
        re.compile(r"Name: artemis\\n"),
    ),
    "desktop/src/portable_upgrade_test.go": (
        re.compile(r'"artemis-"\+version\+"\.dist-info"'),
        re.compile(r"\bartemis_version="),
    ),
    "desktop/src/window_chrome_test.go": (
        re.compile(r"artemis-desktop-drag"),
        re.compile(r"data-artemis-no-drag"),
        re.compile(r"artemis-window-drag-overlay"),
    ),
    ".github/workflows/fnos-build-fpk.yml": (
        re.compile(r"artemis-\*\.whl"),
        re.compile(r"/tmp/artemis-pinned"),
        re.compile(r"\$SP/artemis\.whl"),
        re.compile(r"\b(?:from|import)\s+artemis\b"),
        re.compile(r"artemis(?:\.[A-Za-z_][A-Za-z0-9_]*)+"),
    ),
    "plugins/README.md": (re.compile(r"artemis-toolkit|veenyi/artemis-plugins"),),
    "plugins/README_CN.md": (re.compile(r"artemis-toolkit|veenyi/artemis-plugins"),),
    "plugins/demo-greeting-skill/skills/polite-greeting/SKILL.md": (re.compile(r"\boctop:"),),
    "dashboard/src/locales/en.json": (
        re.compile(r'(?<=metadata: \{ \\")artemis(?=\\":)'),
        re.compile(r"(?<=metadata:\\n  )artemis(?=:)"),
        re.compile(r"\bartemis-assistant\b"),
    ),
    "dashboard/src/locales/zh.json": (
        re.compile(r'(?<=metadata: \{ \\")artemis(?=\\":)'),
        re.compile(r"(?<=metadata:\\n  )artemis(?=:)"),
        re.compile(r"\bartemis-assistant\b"),
    ),
    "dashboard/src/api/types/channel.ts": (re.compile(r"\bartemisbot(?=:)"),),
    "dashboard/src/pages/Agent/Channels/components/constants.ts": (
        re.compile(r"\bartemisbot(?=:)"),
        re.compile(r"(?<=[\"'])artemisbot(?=[\"'])"),
    ),
    "dashboard/src/pages/Chat/components/SessionChannelIcon.tsx": (re.compile(r"\.artemisbot\b"),),
    "dashboard/src/pages/Agent/Channels/components/constants.test.ts": (
        re.compile(r"\.artemisbot\b"),
    ),
    "dashboard/src/pages/Agent/Channels/components/ChannelDrawer.tsx": (
        re.compile(r"(?<=[\"\'])artemisbot(?=[\"\'])"),
    ),
    "dashboard/src/pages/Agent/Connectors/customMcpUtils.ts": (
        re.compile(r"\boctop\.customMcp\.probeOnSave\b"),
    ),
    "dashboard/src/pages/Agent/Personalization/components/MBTISelector.tsx": (
        re.compile(r"\boctop\.pendingChatMessage\b"),
    ),
    "dashboard/src/pages/Agent/Personalization/components/MBTITest.tsx": (
        re.compile(r"\boctop\.pendingChatMessage\b"),
    ),
    "dashboard/src/pages/Chat/hooks/useChatSend.ts": (
        re.compile(r"\boctop\.pendingChatMessage\b"),
    ),
    "dashboard/src/pages/Agent/Skills/components/SkillDrawer.tsx": (
        re.compile(r"\boctop\.(?:emoji|label\.(?:zh|en)|summary\.(?:zh|en))\b"),
    ),
    "dashboard/src/pages/Agent/Skills/components/SkillDrawer.test.ts": (
        re.compile(r"\boctop\.(?:emoji|requires\.bins)\b"),
    ),
}
LEGACY_BRAND_PATTERNS = (
    ("TencentCloud/Octop", re.compile(r"TencentCloud/Octop")),
    ("ghcr.io/tencentcloud/octop", re.compile(r"ghcr\.io/tencentcloud/octop")),
    ("pypi.org/project/octop", re.compile(r"pypi\.org/project/octop")),
    ("octop.cloud.tencent.com", re.compile(r"octop\.cloud\.tencent\.com", re.IGNORECASE)),
    ("octop contributors", re.compile(r"\boctop contributors\b")),
    ("octopbot", re.compile(r"\boctopbot\b", re.IGNORECASE)),
    ("Octop", re.compile(r"\bOctop\b")),
    ("octop", re.compile(r"\boctop\b(?!\.cloud\.tencent\.com)")),
)


@pytest.mark.parametrize(
    ("text", "relative_path", "expected"),
    (
        (
            "ArtemisAgent ArtemisServer ArtemisConfig startOctop X-Artemis-Agent-Id",
            Path("desktop/src/main.go"),
            [],
        ),
        (
            "from artemis.cli import main\nsrc/artemis\nARTEMIS_PORT=8088\n~/.artemis/artemis.db",
            Path("desktop/src/main.go"),
            [],
        ),
        ("/home/artemis/.artemis/agents/main/SOUL.md", Path("dashboard/src/App.tsx"), []),
        ("artemis.infra.gateway.processor", Path("docs/architecture.md"), []),
        ("artemis-auto-backup-2026.tar.gz", Path("docs/cli.md"), []),
        ("data-artemis-no-drag artemis-desktop-drag", Path("dashboard/src/App.tsx"), []),
        ("artemis-assistant", Path("dashboard/src/locales/en.json"), []),
        (
            "https://artemis.cloud.tencent.com",
            Path("dashboard/src/pages/Agent/Channels/components/constants.ts"),
            [],
        ),
        (
            "ArtemisBot",
            Path("dashboard/src/pages/Agent/Channels/components/constants.ts"),
            [],
        ),
        ("artemis:active-agent", Path("dashboard/src/context/AgentContext.tsx"), []),
        ("Artemis-<plat>/packages", Path("desktop/portable/verify_imports.py"), []),
        ("Artemis-<plat>/packages", Path("desktop/portable/verify_imports.py"), []),
        ("Artemis arbitrary", Path("desktop/src/download_test.go"), []),
        ("artemis arbitrary", Path("desktop/src/download_test.go"), []),
        (
            "artemis:agent_errors.no_models_configured",
            Path("dashboard/src/utils/agentError.ts"),
            [],
        ),
        ("pip install artemis", Path("README.md"), []),
        ("artemis init", Path("README.md"), []),
        ("artemis run", Path("README.md"), []),
        ("artemis:latest", Path("README.md"), []),
        ("image: artemis:latest", Path("README.md"), []),
        ("myreg/artemis:v1", Path("README.md"), []),
        ("image: artemis:active-agent", Path("README.md"), []),
        ("image: artemis:agent_errors.foo", Path("README.md"), []),
    ),
)
def test_legacy_brand_matching_distinguishes_public_branding_from_compatibility(
    text: str, relative_path: Path, expected: list[str]
) -> None:
    assert _legacy_brand_references(text, relative_path) == expected


@pytest.mark.parametrize("protocol_key", RETAINED_PROTOCOL_KEYS)
def test_retained_protocol_keys_do_not_count_as_public_branding(protocol_key: str) -> None:
    assert _legacy_brand_references(protocol_key, Path("dashboard/src/App.tsx")) == []


def _legacy_brand_references(text: str, relative_path: Path) -> list[str]:
    if relative_path.parts and relative_path.parts[0] in RUNTIME_PROTOCOL_SOURCE_ROOTS:
        text = re.sub(r"\bdata-artemis-[A-Za-z0-9-]+", "", text)
        text = re.sub(r"\boctop-desktop-[A-Za-z0-9-]+", "", text)
        text = re.sub(r"\boctop:", "", text)
        for protocol_prefix in RETAINED_PROTOCOL_PREFIXES:
            text = text.replace(protocol_prefix, "")
        text = RETAINED_PROTOCOL_KEY_PATTERN.sub("", text)
        text = RETAINED_DYNAMIC_PROTOCOL_PATTERN.sub("", text)
        text = re.sub(r"\bX-Artemis-[A-Za-z-]+\b", "", text)
    if relative_path.parts and relative_path.parts[0] in RUNTIME_PACKAGE_SOURCE_ROOTS:
        text = re.sub(r"\b(?:from|import)\s+artemis\b", "", text)
        text = re.sub(r"artemis(?:\.[A-Za-z_][A-Za-z0-9_]*)+", "", text)
    for token_pattern in ALLOWED_COMPATIBILITY_TOKENS:
        text = token_pattern.sub("", text)
    for token_pattern in RETAINED_DEPLOYMENT_COMPATIBILITY_TOKENS.get(str(relative_path), ()):
        text = token_pattern.sub("", text)
    return [
        reference
        for reference, reference_pattern in LEGACY_BRAND_PATTERNS
        if reference_pattern.search(text)
    ]


def test_desktop_workflow_uses_artemis_filename() -> None:
    assert (REPOSITORY_ROOT / ".github/workflows/artemis-desktop.yml").is_file()
    assert not (REPOSITORY_ROOT / ".github/workflows/octop-desktop.yml").exists()


def _public_text_paths() -> Iterator[Path]:
    for root_name in PUBLIC_ROOTS:
        root = REPOSITORY_ROOT / root_name
        if root.is_file():
            yield root
            continue
        yield from (
            path
            for path in root.rglob("*")
            if path.is_file() and not EXCLUDED_PATH_PARTS.intersection(path.parts)
        )


def _human_readable_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


@pytest.mark.parametrize(
    "path",
    list(_public_text_paths()),
    ids=lambda path: str(path.relative_to(REPOSITORY_ROOT)),
)
def test_public_surfaces_do_not_reference_legacy_brand(path: Path) -> None:
    text = _human_readable_text(path)
    if text is None:
        return

    matches = _legacy_brand_references(text, path.relative_to(REPOSITORY_ROOT))
    assert not matches, f"{path.relative_to(REPOSITORY_ROOT)} exposes legacy branding: {matches}"
