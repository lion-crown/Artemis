"""Tests for `artemis version`."""

from __future__ import annotations

import importlib.metadata

import pytest
from click.testing import CliRunner

from artemis.cli.main import cli


def test_version_prints_artemis_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "artemis" in result.output.lower()
    assert any(ch.isdigit() for ch in result.output)


def test_version_reads_artemis_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []

    def _version(name: str) -> str:
        requested.append(name)
        return "9.8.7"

    monkeypatch.setattr(importlib.metadata, "version", _version)
    result = CliRunner().invoke(cli, ["version"])

    assert result.exit_code == 0
    assert requested == ["artemis"]
    assert "artemis v9.8.7" in result.output


def test_version_in_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert "version" in result.output


def test_root_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["-v"])
    assert result.exit_code == 0
    assert "artemis" in result.output.lower()
