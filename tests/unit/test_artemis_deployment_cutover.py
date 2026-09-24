"""Static contracts for the Artemis deployment and distribution surfaces."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_ROOTS = (
    ".github",
    "desktop",
    "docker",
    "fnos",
    "plugins",
    "scripts",
)
EXCLUDED_PATH_PARTS = frozenset({".git", "node_modules", "vendor", "__pycache__"})
# Match retired identity/protocol/path tokens at an actual word boundary.
LEGACY_IDENTIFIER = re.compile(
    r"(?i)\b(?:octopbot|octop_ui|octop(?:[._:/-]|$)|octopus(?:[._:/-]|$))"
)


def test_legacy_identifier_pattern_matches_boundary_delimited_tokens() -> None:
    for token in (
        "octop",
        "octop:active-agent",
        "octop_ui",
        "octopbot",
        ".octop/config.json",
        "octop-desktop-darwin",
        "octopus/path",
    ):
        assert LEGACY_IDENTIFIER.search(token), token

    for token in ("octop123", "myoctop", "artemis"):
        assert LEGACY_IDENTIFIER.search(token) is None, token


def _deployment_files() -> list[Path]:
    return [
        path
        for root_name in DEPLOYMENT_ROOTS
        for path in (REPOSITORY_ROOT / root_name).rglob("*")
        if path.is_file() and not EXCLUDED_PATH_PARTS.intersection(path.parts)
    ]


def test_deployment_filenames_and_identifiers_are_artemis_only() -> None:
    files = _deployment_files()
    matches: list[str] = []
    for path in files:
        relative_path = path.relative_to(REPOSITORY_ROOT)
        if LEGACY_IDENTIFIER.search(str(relative_path)):
            matches.append(str(relative_path))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if LEGACY_IDENTIFIER.search(text):
            matches.append(str(relative_path))

    assert not matches, f"legacy deployment identifiers remain in: {matches}"
    assert (REPOSITORY_ROOT / ".github/workflows/artemis-desktop.yml").is_file()
    assert not (REPOSITORY_ROOT / ".github/workflows/octop-desktop.yml").exists()
    assert (REPOSITORY_ROOT / "scripts/install-artemis.sh").is_file()
    assert not (REPOSITORY_ROOT / "scripts/install-octop.sh").exists()


def test_deployment_and_plugin_contracts_use_artemis_names() -> None:
    compose = (REPOSITORY_ROOT / "docker/docker-compose.yml").read_text(encoding="utf-8")
    plugin = (REPOSITORY_ROOT / "plugins/demo-ui-card/main.py").read_text(encoding="utf-8")
    custom_mcp = (
        REPOSITORY_ROOT / "dashboard/src/pages/Agent/Connectors/customMcpUtils.ts"
    ).read_text(encoding="utf-8")

    assert "container_name: artemis" in compose
    assert "ARTEMIS_" in compose
    assert ".artemis" in compose
    assert '"artemis_ui"' in plugin
    assert "artemis.customMcp.probeOnSave" in custom_mcp
