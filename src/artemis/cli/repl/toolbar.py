"""prompt_toolkit bottom toolbar for ``artemis chats repl``."""

from __future__ import annotations

from artemis.cli.repl.session import ReplSession


def format_repl_toolbar(state: ReplSession) -> str:
    """Format bottom toolbar: agent │ model │ session │ last turn."""
    parts = [
        state.agent_id[:12],
        f"model: {state.model_label}",
        f"session: {state.session_key[:10]}",
    ]
    if state.last_elapsed > 0:
        parts.append(f"last: {state.last_elapsed:.1f}s")
    return " │ ".join(parts)
