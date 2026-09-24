"""tests/unit/mobile/test_mobile_setup.py"""

from __future__ import annotations

from unittest.mock import patch

from artemis.config import CapabilitiesConfig, MobileCapabilities, ArtemisConfig
from artemis.infra.mobile.setup import mobile_status


def _cfg(**mobile: object) -> ArtemisConfig:
    return ArtemisConfig(
        capabilities=CapabilitiesConfig(
            mobile=MobileCapabilities(**mobile)  # type: ignore[arg-type]
        )
    )


def test_mobile_status_disabled() -> None:
    status = mobile_status(_cfg(enabled=False, backend="none"))
    assert status.mobile_supported is False
    assert status.setup_state == "unsupported"


def test_mobile_status_physical_ready() -> None:
    with (
        patch("artemis.infra.mobile.setup.find_adb", return_value="/adb"),
        patch("artemis.infra.mobile.setup.list_devices", return_value=["emulator-5554"]),
    ):
        status = mobile_status(_cfg(enabled=True, backend="physical"))
    assert status.setup_state == "ready"
    assert status.selected_device == "emulator-5554"


def test_mobile_status_physical_needs_device() -> None:
    with (
        patch("artemis.infra.mobile.setup.find_adb", return_value="/adb"),
        patch("artemis.infra.mobile.setup.list_devices", return_value=[]),
    ):
        status = mobile_status(_cfg(enabled=True, backend="physical"))
    assert status.setup_state == "needs_device"


def test_mobile_status_container_reconnects_adb() -> None:
    with (
        patch("artemis.infra.mobile.setup.find_adb", return_value="/adb"),
        patch("artemis.infra.mobile.setup._container_running", return_value=True),
        patch(
            "artemis.infra.mobile.setup.list_devices",
            side_effect=[[], ["127.0.0.1:5555"]],
        ),
        patch("artemis.infra.mobile.setup.adb_connect", return_value=True) as connect,
    ):
        status = mobile_status(_cfg(enabled=True, backend="redroid"))
    connect.assert_called_once_with("127.0.0.1:5555", adb="/adb")
    assert status.setup_state == "ready"
    assert status.selected_device == "127.0.0.1:5555"


def test_mobile_status_container_missing_adb_binary() -> None:
    with (
        patch("artemis.infra.mobile.setup.find_adb", return_value=None),
        patch("artemis.infra.mobile.setup._container_running", return_value=True),
        patch("artemis.infra.mobile.setup.list_devices", return_value=[]),
    ):
        status = mobile_status(_cfg(enabled=True, backend="redroid"), locale="en")
    assert status.setup_state == "needs_device"
    assert "adb was not found" in status.reason
