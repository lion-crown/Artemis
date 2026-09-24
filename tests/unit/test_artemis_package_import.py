"""Namespace cutover contract for the installed source tree."""

from __future__ import annotations

import importlib.util


def test_artemis_namespace_replaces_legacy_namespace() -> None:
    """The application is importable only through its Artemis namespace."""
    import artemis

    assert artemis.__name__ == "artemis"
    assert importlib.util.find_spec("octop") is None
