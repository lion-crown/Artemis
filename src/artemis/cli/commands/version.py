"""artemis version command."""

from __future__ import annotations

import click


@click.command("version")
def version() -> None:
    """Show the installed Artemis version."""
    try:
        from importlib.metadata import version as _v

        v = _v("artemis")
    except Exception:
        v = "unknown"
    click.echo(f"artemis v{v}")
