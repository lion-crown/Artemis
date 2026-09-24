"""Hard-cutover contracts for Artemis runtime identifiers."""

from __future__ import annotations

from pathlib import Path

from artemis.config import env_bind_overrides, load_config
from artemis.infra.backup.auto import to_auto_backup_filename
from artemis.infra.backup.system_archive import suggested_backup_filename
from artemis.infra.setup.service import LAUNCHD_LABEL, SERVICE_NAME, ServiceRuntime, render_launchd_plist
from artemis.infra.utils.paths import PathLayout


def test_runtime_uses_artemis_root_env_prefix_database_and_backup_names(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("ARTEMIS_HOME", str(tmp_path / ".artemis"))
    monkeypatch.setenv("ARTEMIS_PORT", "19001")
    monkeypatch.setenv("ARTEMIS_HOME", str(tmp_path / "custom-artemis"))
    monkeypatch.setenv("ARTEMIS_PORT", "19002")

    paths = PathLayout.from_env()
    config = load_config(paths.config)

    assert paths.root == tmp_path / "custom-artemis"
    assert paths.db == tmp_path / "custom-artemis" / "artemis.db"
    assert config.port == 19002
    assert env_bind_overrides() == (None, 19002)
    assert suggested_backup_filename().startswith("artemis-backup-")
    assert to_auto_backup_filename("artemis-backup-20260923T000000Z.tar.gz") == (
        "artemis-auto-backup-20260923T000000Z.tar.gz"
    )


def test_runtime_ignores_legacy_root_and_configuration_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("OCTOP_HOME", str(tmp_path / "legacy-octop-home"))
    monkeypatch.setenv("OCTOP_PORT", "19001")
    monkeypatch.delenv("ARTEMIS_HOME", raising=False)
    monkeypatch.delenv("ARTEMIS_PORT", raising=False)

    paths = PathLayout.from_env()

    assert paths.root == tmp_path / ".artemis"
    assert load_config(paths.config).port == 8088


def test_first_party_runtime_sources_use_only_artemis_identifiers() -> None:
    root = Path(__file__).resolve().parents[2]
    sources = (
        root / "dashboard/src",
        root / "desktop/src",
        root / "src/artemis",
    )
    forbidden = (
        "octopbot",
        "octopHome",
        "__octopSpeech",
        "octopDragReady",
        "octopDesktopChrome",
        "octopSpinnerSpin",
        "octopUi",
        "parseOctop",
        "octopSettings",
        "octopCron",
        "octopDesc",
        "sectionOctop",
        "fromOctop",
        "_octop",
    )
    text_files = (
            path
            for source in sources
            for path in source.rglob("*")
            if path.suffix in {".css", ".go", ".js", ".json", ".less", ".py", ".ts", ".tsx"}
            and not path.is_relative_to(root / "src/artemis/dashboard")
    )
    contents = {path: path.read_text(encoding="utf-8") for path in text_files}

    matches = {
        token: sorted(
            str(path.relative_to(root))
            for path, content in contents.items()
            if token in content
        )
        for token in forbidden
    }

    assert not {token: paths for token, paths in matches.items() if paths}


def test_docker_environment_footer_uses_the_artemis_i18n_key() -> None:
    root = Path(__file__).resolve().parents[2]
    footer = (root / "dashboard/src/pages/Admin/Storage/DockerEnvFooter.tsx").read_text(
        encoding="utf-8"
    )

    assert 't("storage.dockerEnv.sectionArtemis")' in footer
    assert "sectionOctop" not in footer
    for locale in ("en", "zh"):
        catalog = (root / f"dashboard/src/locales/{locale}.json").read_text(encoding="utf-8")
        assert '"sectionArtemis"' in catalog


def test_launchd_template_uses_artemis_label_and_environment(tmp_path: Path) -> None:
    executable = tmp_path / "bin" / "artemis"
    executable.parent.mkdir()
    runtime = ServiceRuntime(
        mode="launchd",
        host="127.0.0.1",
        port=8088,
        home=tmp_path / ".artemis",
        artemis_bin=executable,
        run_as_user="tester",
    )

    plist = render_launchd_plist(runtime)

    assert SERVICE_NAME == "artemis"
    assert LAUNCHD_LABEL == "artemis"
    assert "<string>artemis</string>" in plist
    assert "<key>ARTEMIS_HOME</key>" in plist
    assert "OCTOP_" not in plist
