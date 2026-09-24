"""Resolved OpenAI-compatible model settings for controlled business QA."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessOpenAIModel:
    """Provider connection values kept inside the native business runner."""

    model: str
    base_url: str
    api_key: str
    headers: dict[str, str]


__all__ = ["BusinessOpenAIModel"]
