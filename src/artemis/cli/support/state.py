"""CLI state — pinned default user/agent."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from artemis.infra.utils.paths import PathLayout


def default_state_path() -> Path:
    """Default location for the CLI state file (``~/.artemis/cli_state.json``)."""
    return PathLayout.from_env().root / "cli_state.json"


@dataclass
class CLIState:
    default_user: str | None = None
    default_agent: str | None = None


def load(path: Path) -> CLIState:
    if not path.exists():
        return CLIState()
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    base = asdict(CLIState())
    base.update(raw)
    allowed = {f.name for f in fields(CLIState)}
    return CLIState(**{k: v for k, v in base.items() if k in allowed})


def save(path: Path, state: CLIState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
