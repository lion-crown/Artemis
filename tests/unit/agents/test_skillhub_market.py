"""Tests for SkillHub skillset retrieval used by global skill packages."""

from __future__ import annotations

import io
import json
import urllib.error
import zipfile
from typing import Any

import pytest

from artemis.infra.skills import skillhub_market


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_browse_skillsets_filters_by_scene(monkeypatch) -> None:
    from artemis.infra.agents.experts import skillhub_market

    monkeypatch.setattr(
        skillhub_market,
        "_fetch_all_skillsets",
        lambda: [
            skillhub_market.SkillHubSkillset(
                slug="a",
                display_name="A",
                scene="tech",
            ),
            skillhub_market.SkillHubSkillset(
                slug="b",
                display_name="B",
                scene="finance",
            ),
            skillhub_market.SkillHubSkillset(
                slug="c",
                display_name="C",
                scene="tech",
            ),
        ],
    )

    items, scenes = skillhub_market.browse_skillsets(scene="tech")

    assert [item.slug for item in items] == ["a", "c"]
    assert scenes == ["finance", "tech"]


def test_fetch_skillset_uses_detail_endpoint(monkeypatch) -> None:
    from artemis.infra.agents.experts import skillhub_market

    calls: list[str] = []

    def fake_json_get(url: str) -> dict[str, object]:
        calls.append(url)
        return {
            "slug": "tech-code-review",
            "displayName": "代码审查",
            "scene": "tech",
            "summary": "review PRs",
        }

    monkeypatch.setattr(skillhub_market, "_http_json_get", fake_json_get)

    item = skillhub_market.fetch_skillset("tech-code-review")

    assert item.slug == "tech-code-review"
    assert item.scene == "tech"
    assert "/api/v1/skillsets/tech-code-review" in calls[0]


def test_fetch_skillsets_uses_skillhub_pagination(monkeypatch) -> None:
    from artemis.infra.agents.experts import skillhub_market

    calls: list[str] = []

    def fake_json_get(url: str) -> dict[str, object]:
        calls.append(url)
        if "page=1" in url:
            return {
                "skillSets": [
                    {"slug": "one", "displayName": "One"},
                    {"slug": "two", "displayName": "Two"},
                ],
                "total": 3,
            }
        return {
            "skillSets": [{"slug": "three", "displayName": "Three"}],
            "total": 3,
        }

    monkeypatch.setattr(skillhub_market, "_SKILLSET_PAGE_SIZE", 2)
    monkeypatch.setattr(skillhub_market, "_skillset_list_cache", None)
    monkeypatch.setattr(skillhub_market, "_skillset_list_cache_at", 0.0)
    monkeypatch.setattr(skillhub_market, "_http_json_get", fake_json_get)

    items = skillhub_market.fetch_skillsets()

    assert [item.slug for item in items] == ["one", "two", "three"]
    assert "page=1" in calls[0]
    assert "pageSize=2" in calls[0]
    assert "page=2" in calls[1]


def test_skillhub_manifest_skill_slugs_are_deduped() -> None:
    from artemis.infra.agents.experts.skillhub_market import _manifest_skill_slugs

    manifest = {
        "skillSets": [
            {"skillSlugs": ["alpha", "beta"]},
            {"skillSlugs": ["beta", "gamma"]},
        ]
    }

    assert _manifest_skill_slugs(manifest) == ["alpha", "beta", "gamma"]


def test_parse_skillset_package_prefers_matching_skillsets_prompt() -> None:
    from artemis.infra.agents.experts.skillhub_market import _parse_skillset_package

    manifest = {"skillSets": [{"slug": "target", "skillSlugs": ["alpha"]}]}
    package = _zip_bytes(
        {
            "manifest.json": json.dumps(manifest),
            "identify.md": "# Wrong prompt\n",
            "skillsets/other.md": "# Other prompt\n",
            "skillsets/target.md": "# Target workflow\n",
        }
    )

    parsed_manifest, prompt = _parse_skillset_package(
        package,
        skillset_slug="target",
        fallback_content="# Fallback\n",
    )

    assert parsed_manifest == manifest
    assert prompt == "# Target workflow\n"


def test_parse_skillset_package_uses_identify_for_single_skillset() -> None:
    from artemis.infra.agents.experts.skillhub_market import _parse_skillset_package

    manifest = {"skillSlugs": ["alpha"]}
    package = _zip_bytes(
        {
            "manifest.json": json.dumps(manifest),
            "identify.md": "# Single skillset workflow\n",
        }
    )

    _parsed_manifest, prompt = _parse_skillset_package(
        package,
        skillset_slug="target",
        fallback_content="# Fallback\n",
    )

    assert prompt == "# Single skillset workflow\n"


def test_skillhub_dedupes_repeated_frontmatter() -> None:
    from artemis.infra.agents.experts.skillhub_market import _dedupe_frontmatter

    text = "---\ntitle: Demo\n---\n---\ntitle: Demo\n---\n# Body\n"

    assert _dedupe_frontmatter(text) == "---\ntitle: Demo\n---\n\n# Body\n"


def test_skillset_from_raw_tolerates_bad_skill_count() -> None:
    from artemis.infra.agents.experts.skillhub_market import _skillset_from_raw

    item = _skillset_from_raw(
        {
            "slug": "demo",
            "displayName": "Demo",
            "skillSlugs": ["a", "b"],
            "skillCount": "not-a-number",
        }
    )

    assert item.skill_count == 2


def test_validate_zip_rejects_path_traversal() -> None:
    import io
    import zipfile

    import pytest

    from artemis.infra.agents.experts.skillhub_market import (
        SkillHubMarketError,
        SkillHubMarketErrorKind,
        _validate_zip,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "x")
    with (
        zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf,
        pytest.raises(SkillHubMarketError) as exc,
    ):
        _validate_zip(zf)
    assert exc.value.kind == SkillHubMarketErrorKind.PACKAGE_INVALID


def test_validate_zip_rejects_too_many_entries(monkeypatch) -> None:
    import io
    import zipfile

    import pytest

    from artemis.infra.agents.experts import skillhub_market

    monkeypatch.setattr(skillhub_market, "_MAX_ZIP_ENTRIES", 2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", "a")
        zf.writestr("b.txt", "b")
        zf.writestr("c.txt", "c")
    with (
        zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf,
        pytest.raises(skillhub_market.SkillHubMarketError) as exc,
    ):
        skillhub_market._validate_zip(zf)
    assert exc.value.kind == skillhub_market.SkillHubMarketErrorKind.PACKAGE_TOO_LARGE


def test_fetch_all_skillsets_serves_stale_on_refresh_failure(monkeypatch) -> None:
    from artemis.infra.agents.experts import skillhub_market

    cached = [
        skillhub_market.SkillHubSkillset(slug="cached", display_name="Cached"),
    ]
    monkeypatch.setattr(skillhub_market, "_skillset_list_cache", cached)
    monkeypatch.setattr(skillhub_market, "_skillset_list_cache_at", 0.0)
    monkeypatch.setattr(skillhub_market, "_skillset_list_loading", False)

    def boom() -> list[skillhub_market.SkillHubSkillset]:
        raise skillhub_market.SkillHubMarketError(
            "upstream down",
            kind=skillhub_market.SkillHubMarketErrorKind.UPSTREAM_FAILED,
        )

    monkeypatch.setattr(skillhub_market, "_load_all_skillsets_uncached", boom)

    items = skillhub_market._fetch_all_skillsets()
    assert [item.slug for item in items] == ["cached"]


def test_http_get_ssl_urlerror_raises_ssl_kind(monkeypatch) -> None:
    from urllib.error import URLError

    from artemis.infra.agents.experts import skillhub_market

    def boom(*_args: object, **_kwargs: object) -> object:
        raise URLError("[SSL: RECORD_LAYER_FAILURE] record layer failure")

    monkeypatch.setattr(skillhub_market, "urlopen", boom)

    with pytest.raises(skillhub_market.SkillHubMarketError) as exc:
        skillhub_market._http_get("https://example.test/x", accept="application/json")
    assert exc.value.kind == skillhub_market.SkillHubMarketErrorKind.SSL_ERROR


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def test_fetch_ranking_json_uses_showcase_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        seen["url"] = request.full_url
        seen["accept"] = request.headers["Accept"]
        seen["timeout"] = timeout
        return _Response({"section": "hot_downloads", "skills": [], "total": 0})

    monkeypatch.setattr(skillhub_market.urllib.request, "urlopen", fake_urlopen)

    result = skillhub_market._fetch_ranking_json(
        "https://api.example.com",
        "hot",
        timeout=7,
    )

    assert result["section"] == "hot_downloads"
    assert seen == {
        "url": "https://api.example.com/api/v1/showcase/hot",
        "accept": "application/json",
        "timeout": 7,
    }


@pytest.mark.asyncio
async def test_fetch_all_returns_partial_results(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(
        _host: str,
        ranking_type: str,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        assert timeout == 10
        if ranking_type == "hot":
            raise skillhub_market.SkillHubMarketError("hot unavailable")
        return {"section": ranking_type, "skills": [], "total": 0}

    monkeypatch.setattr(skillhub_market, "_fetch_ranking_json", fake_fetch)

    result = await skillhub_market.fetch_skillhub_rankings("all")

    assert "hot" not in result["rankings"]
    assert result["rankings"]["recommended"]["section"] == "recommended"
    assert result["errors"] == {"hot": "hot unavailable"}


@pytest.mark.asyncio
async def test_fetch_all_raises_timeout_when_every_request_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch(
        _host: str,
        ranking_type: str,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        raise skillhub_market.SkillHubMarketTimeout(f"{ranking_type} timed out")

    monkeypatch.setattr(skillhub_market, "_fetch_ranking_json", fake_fetch)

    with pytest.raises(
        skillhub_market.SkillHubMarketTimeout,
        match="All SkillHub ranking requests timed out",
    ):
        await skillhub_market.fetch_skillhub_rankings("all")


def test_fetch_ranking_maps_url_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_request: Any, timeout: float) -> _Response:
        raise urllib.error.URLError(TimeoutError())

    monkeypatch.setattr(skillhub_market.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(skillhub_market.SkillHubMarketTimeout):
        skillhub_market._fetch_ranking_json(
            "https://api.example.com",
            "recommended",
            timeout=7,
        )
