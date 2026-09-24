"""CLI error helpers."""

from __future__ import annotations

import click

from artemis.infra.errors import ArtemisError


def fail_artemis(exc: ArtemisError) -> None:
    click.echo(f"error: {exc.message}", err=True)
    raise SystemExit(1) from exc
