"""Static contracts for package-name consumers outside Python imports."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_portable_runner_and_desktop_upgrade_use_artemis_distribution() -> None:
    package = (ROOT / "desktop/portable/package.sh").read_text(encoding="utf-8")
    verify = (ROOT / "desktop/portable/verify_imports.py").read_text(encoding="utf-8")
    launch = (ROOT / "desktop/portable/templates/launch.py").read_text(encoding="utf-8")
    download = (ROOT / "desktop/src/download.go").read_text(encoding="utf-8")

    assert "build_artemis_wheel" in package
    assert "artemis-*.whl" in package
    assert '"artemis",' in verify
    assert 'run_module("artemis"' in launch
    assert '"artemis-*.dist-info"' in download


def test_installers_and_fnos_workflow_reference_artemis_distribution() -> None:
    installers = [
        ROOT / "scripts/install.sh",
        ROOT / "scripts/install-artemis.sh",
        ROOT / "scripts/install.bat",
        ROOT / "scripts/install.ps1",
    ]
    for installer in installers:
        text = installer.read_text(encoding="utf-8")
        assert "import importlib.resources, artemis" in text
        assert "files('artemis')" in text
        assert "artemis[browser]" in text

    workflow = (ROOT / ".github/workflows/fnos-build-fpk.yml").read_text(encoding="utf-8")
    assert "artemis-*.whl" in workflow
    assert "artemis.__version__" in workflow
    assert "octop-*.whl" not in workflow


def test_test_home_fixture_keeps_legacy_root_but_uses_artemis_test_identifier() -> None:
    conftest = (ROOT / "tests/conftest.py").read_text(encoding="utf-8")
    assert "def tmp_artemis_home" in conftest
    assert 'runtime_home = _isolated_user_home / ".artemis"' in conftest
    assert "runtime_home.mkdir(exist_ok=True)" in conftest
