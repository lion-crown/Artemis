import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README_FILES = ("README.md", "README_CN.md")


def test_readmes_present_artemis_and_its_cli_commands() -> None:
    for filename in README_FILES:
        content = (ROOT / filename).read_text(encoding="utf-8")
        product_body = content.split("\n---\n", maxsplit=1)[1]

        assert "**Artemis**" in product_body
        assert "artemis run" in product_body
        assert "octop run" not in product_body
        assert "~/.artemis/" in product_body
        assert "ARTEMIS_" in product_body


def test_project_installs_only_the_artemis_cli_command() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"] == {"artemis": "artemis.cli.main:cli"}


def test_product_documentation_uses_artemis_name() -> None:
    legacy_product_phrases = {
        "docs/adr/001-single-process-model.md": "Octop needs",
        "docs/adr/002-database-backends.md": "Octop control plane",
        "docs/learning/ai-agent-l3-study-plan.md": "Octop 项目",
        "docs/personas.md": "octop falls back",
        "docs/agent-interop-mailbox.md": "### octop",
        "docs/agent-delegation.md": "octop DB",
    }

    for filename, legacy_phrase in legacy_product_phrases.items():
        content = (ROOT / filename).read_text(encoding="utf-8")
        assert legacy_phrase not in content


def test_installer_compatibility_comments_name_the_artemis_distribution() -> None:
    shell_installer = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
    powershell_installer = (ROOT / "scripts/install.ps1").read_text(encoding="utf-8")

    assert "Artemis Python 分发包" in shell_installer
    assert "published Artemis distribution" in powershell_installer
