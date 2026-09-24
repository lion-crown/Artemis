"""Unit tests for TLS preflight checks."""

from __future__ import annotations

from unittest.mock import patch

from artemis.config import ArtemisConfig, TlsConfig
from artemis.infra.setup.tls.preflight import run_preflight


def test_preflight_requires_domain():
    result = run_preflight("", ArtemisConfig())
    assert not result.ok
    assert any(c.id == "domain" and not c.ok for c in result.checks)


def test_preflight_bind_host_and_port(tmp_path):
    cfg = ArtemisConfig(bind_host="127.0.0.1", port=8088)
    with (
        patch("artemis.infra.setup.tls.preflight._port_available", return_value=True),
        patch("artemis.infra.setup.tls.preflight._fetch_public_ip", return_value="203.0.113.1"),
        patch("artemis.infra.setup.tls.preflight._resolve_domain_ips", return_value={"203.0.113.1"}),
    ):
        result = run_preflight("artemis.example.com", cfg)
    assert not result.ok
    ids = {c.id for c in result.checks}
    assert "bind_host" in ids
    assert "port" in ids
    bind = next(c for c in result.checks if c.id == "bind_host")
    port = next(c for c in result.checks if c.id == "port")
    assert not bind.ok
    assert not port.ok


def test_preflight_ok_when_all_match():
    cfg = ArtemisConfig(
        bind_host="0.0.0.0",
        port=80,
        tls=TlsConfig(enabled=False),
    )
    with (
        patch("artemis.infra.setup.tls.preflight._port_available", return_value=True),
        patch("artemis.infra.setup.tls.preflight._fetch_public_ip", return_value="203.0.113.1"),
        patch("artemis.infra.setup.tls.preflight._resolve_domain_ips", return_value={"203.0.113.1"}),
    ):
        result = run_preflight("artemis.example.com", cfg)
    assert result.ok
    assert all(c.ok for c in result.checks)


def test_preflight_rejects_when_tls_already_enabled():
    cfg = ArtemisConfig(
        bind_host="0.0.0.0",
        port=8088,
        tls=TlsConfig(enabled=True),
    )
    with (
        patch("artemis.infra.setup.tls.preflight._port_available", return_value=True),
        patch("artemis.infra.setup.tls.preflight._fetch_public_ip", return_value="203.0.113.1"),
        patch("artemis.infra.setup.tls.preflight._resolve_domain_ips", return_value={"203.0.113.1"}),
    ):
        result = run_preflight("artemis.example.com", cfg)
    assert not result.ok
    assert any(c.id == "tls_enabled" and not c.ok for c in result.checks)


def test_preflight_renewal_mode_dual_port():
    cfg = ArtemisConfig(
        bind_host="0.0.0.0",
        port=443,
        tls=TlsConfig(enabled=True, http_port=80),
    )
    with (
        patch("artemis.infra.setup.tls.preflight._fetch_public_ip", return_value="203.0.113.1"),
        patch("artemis.infra.setup.tls.preflight._resolve_domain_ips", return_value={"203.0.113.1"}),
    ):
        result = run_preflight("artemis.example.com", cfg)
    assert result.renewal
    assert result.ok
    assert any(c.id == "dual_port" and c.ok for c in result.checks)
