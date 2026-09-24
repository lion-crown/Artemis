from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_desktop_and_fnos_use_artemis_as_the_display_name() -> None:
    desktop = (ROOT / "desktop/src/build/config.yml").read_text()
    desktop_main = (ROOT / "desktop/src/main.go").read_text()
    sleep_inhibitor = (ROOT / "desktop/src/preventsleep_linux.go").read_text()
    desktop_shell = (ROOT / "desktop/src/assets/index.html").read_text()
    nsis_tools = (ROOT / "desktop/src/build/windows/nsis/wails_tools.nsh").read_text()
    native_manifest = (ROOT / "fnos/native/manifest").read_text()
    docker_manifest = (ROOT / "fnos/docker/manifest").read_text()
    native_ui = (ROOT / "fnos/native/app/ui/config").read_text()
    docker_ui = (ROOT / "fnos/docker/app/ui/config").read_text()
    native_install = (ROOT / "fnos/native/wizard/install").read_text()
    native_uninstall = (ROOT / "fnos/native/wizard/uninstall").read_text()
    docker_install = (ROOT / "fnos/docker/wizard/install").read_text()
    docker_uninstall = (ROOT / "fnos/docker/wizard/uninstall").read_text()
    dockerfile = (ROOT / "fnos/docker/Dockerfile").read_text()

    assert 'companyName: "Artemis"' in desktop
    assert 'productName: "Artemis"' in desktop
    assert 'Name:        "Artemis"' in desktop_main
    assert 'Description: "Artemis desktop"' in desktop_main
    assert 'Title:                "Artemis"' in desktop_main
    assert 'Title:            "Artemis 设置"' in desktop_main
    assert 'tray.SetTooltip("Artemis")' in desktop_main
    assert '"Artemis",' in sleep_inhibitor
    assert '"Artemis desktop is running",' in sleep_inhibitor
    assert "<title>Artemis</title>" in desktop_shell
    assert 'loading-brand" id="loading-brand">Artemis<' in desktop_shell
    assert 'title: "Artemis Settings"' in desktop_shell
    assert 'showMain: "Show Artemis"' in desktop_shell
    assert '!define INFO_PROJECTNAME "Artemis"' in nsis_tools
    assert '!define INFO_COMPANYNAME "Artemis"' in nsis_tools
    assert '!define INFO_PRODUCTNAME "Artemis"' in nsis_tools
    assert "display_name=Artemis" in native_manifest
    assert "display_name=Artemis" in docker_manifest
    assert "desc=Artemis 是一款" in native_manifest
    assert "desc=Artemis 是一款" in docker_manifest
    assert "appname=artemis-native" in native_manifest
    assert "appname=artemis" in docker_manifest
    assert '"title": "Artemis"' in native_ui
    assert '"title": "Artemis"' in docker_ui
    assert "<b>Artemis</b>" in native_install
    assert '"stepTitle": "卸载 Artemis 本地版"' in native_uninstall
    assert "<b>Artemis（Docker 版）</b>" in docker_install
    assert '"stepTitle": "卸载 Artemis"' in docker_uninstall
    assert "artemis-login.txt" in docker_install
    assert 'LABEL org.opencontainers.image.title="Artemis"' in dockerfile
    assert 'LABEL org.opencontainers.image.description="Artemis' in dockerfile
