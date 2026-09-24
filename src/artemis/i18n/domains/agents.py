"""``agents.*`` — agent runtime labels and startup error keys."""

from __future__ import annotations

from artemis.i18n.loader import lookup, tr
from artemis.infra.utils.locale import Locale

_START_ERROR_PREFIX = "artemis:"
NO_MODELS_CONFIGURED = f"{_START_ERROR_PREFIX}agent_errors.no_models_configured"
MODEL_REF_UNAVAILABLE = f"{_START_ERROR_PREFIX}agent_errors.model_ref_unavailable"

__all__ = [
    "MODEL_REF_UNAVAILABLE",
    "NO_MODELS_CONFIGURED",
    "agent_error_message",
    "agent_state_label",
    "classify_agent_start_error_message",
    "format_agent_start_error",
]


def _is_model_ref_error(msg: str) -> bool:
    return (
        "unknown provider" in msg
        or "not found or disabled" in msg
        or "has no model" in msg
        or "malformed model ref" in msg
        or "default_model=" in msg
        or (" is disabled" in msg and "model" in msg)
        or ("must be in the form" in msg and "model" in msg)
    )


def _is_no_models_error(msg: str) -> bool:
    return (
        "requires providers" in msg
        or "model_factory" in msg
        or "enabled models" in msg
        or "no models" in msg
        or "no provider" in msg
    )


def classify_agent_start_error_message(message: str) -> str | None:
    """Return a stable ``artemis:…`` key for known harness failures, else ``None``."""
    msg = message.lower()
    if _is_model_ref_error(msg):
        return MODEL_REF_UNAVAILABLE
    if _is_no_models_error(msg):
        return NO_MODELS_CONFIGURED
    return None


def _leaf_exception_message(exc: BaseException) -> str:
    """Unwrap ExceptionGroup (e.g. MCP SSE / anyio TaskGroup) for display."""
    if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        return _leaf_exception_message(exc.exceptions[0])
    return str(exc)


def format_agent_start_error(exc: BaseException) -> str:
    """Return a stable ``artemis:…`` key for known failures, else raw text (truncated)."""
    message = _leaf_exception_message(exc)
    classified = classify_agent_start_error_message(message)
    if classified is not None:
        return classified
    return message[:500]


def agent_state_label(state: str | None, locale: str | Locale = "en") -> str:
    """Localized harness agent ``last_state`` for user-facing output."""
    if not state:
        return tr("agents.state.unknown", locale)
    key = f"agents.state.{state}"
    if lookup(key, locale) is None:
        return state
    return tr(key, locale)


def agent_error_message(error: str | None, locale: str | Locale = "en") -> str:
    """Localized agent ``last_error`` for user-facing output."""
    if not error:
        return ""
    if error.startswith("artemis:"):
        key = error.removeprefix("artemis:")
        if lookup(key, locale) is not None:
            return tr(key, locale)
    classified = classify_agent_start_error_message(error)
    if classified is not None:
        return tr(classified.removeprefix("artemis:"), locale)
    return error
