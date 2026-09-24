"""SkillHub skillset retrieval for global skill packages."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import zipfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from artemis.infra.utils.ssl_errors import looks_like_ssl_error

logger = logging.getLogger(__name__)

DEFAULT_SKILLHUB_HOST = "https://api.skillhub.cn"
_HTTP_TIMEOUT = 30
_SKILLSET_PAGE_SIZE = 100
_MAX_SKILLSET_PAGES = 20
_SKILLSET_LIST_CACHE_TTL_SECONDS = 300.0
_MAX_HTTP_BYTES = 32 * 1024 * 1024
_MAX_ZIP_ENTRIES = 2_000
_MAX_ZIP_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
_MAX_ZIP_COMPRESSION_RATIO = 100.0
_HTTP_READ_CHUNK = 64 * 1024
_SCENE_ORDER = (
    "ecommerce",
    "finance",
    "content-creation",
    "lifestyle",
    "marketing",
    "mysticism",
    "academic",
    "legal",
    "tech",
    "education",
    "healthcare",
    "hr",
    "media",
    "design",
)
_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class SkillHubMarketErrorKind(StrEnum):
    NOT_FOUND = "not_found"
    INVALID_SLUG = "invalid_slug"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_BAD_PAYLOAD = "upstream_bad_payload"
    PACKAGE_INVALID = "package_invalid"
    PACKAGE_TOO_LARGE = "package_too_large"
    UPSTREAM_FAILED = "upstream_failed"
    SSL_ERROR = "ssl_error"


class SkillHubMarketError(RuntimeError):
    """Raised when a SkillHub skillset request fails."""

    def __init__(
        self,
        message: str,
        *,
        kind: SkillHubMarketErrorKind = SkillHubMarketErrorKind.UPSTREAM_FAILED,
    ) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class SkillHubSkillset:
    slug: str
    display_name: str
    display_name_en: str = ""
    summary: str = ""
    summary_en: str = ""
    scene: str = ""
    sub_scene: str = ""
    content: str = ""
    content_en: str = ""
    icon_url: str = ""
    skill_slugs: tuple[str, ...] = ()
    skill_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


_skillset_list_cache: list[SkillHubSkillset] | None = None
_skillset_list_cache_at: float = 0.0
_skillset_list_lock = threading.Lock()
_skillset_list_cv = threading.Condition(_skillset_list_lock)
_skillset_list_loading = False


def validate_skillset_slug(slug: str) -> str:
    trimmed = slug.strip()
    if not trimmed or not _SLUG_RE.fullmatch(trimmed):
        raise SkillHubMarketError(
            "invalid skillset slug",
            kind=SkillHubMarketErrorKind.INVALID_SLUG,
        )
    return trimmed


def fetch_skillsets(query: str = "", *, scene: str = "") -> list[SkillHubSkillset]:
    items, _scenes = browse_skillsets(query, scene=scene)
    return items


def list_skillset_scenes() -> list[str]:
    """Return distinct SkillHub scenes in product nav order."""
    _items, scenes = browse_skillsets()
    return scenes


def _ordered_scenes(present: set[str]) -> list[str]:
    ordered = [scene for scene in _SCENE_ORDER if scene in present]
    extras = sorted(scene for scene in present if scene not in _SCENE_ORDER)
    return ordered + extras


def browse_skillsets(
    query: str = "",
    *,
    scene: str = "",
) -> tuple[list[SkillHubSkillset], list[str]]:
    """Fetch skillsets once and return ``(filtered_items, all_scenes)``."""
    all_items = _fetch_all_skillsets()
    present = {item.scene.strip() for item in all_items if item.scene.strip()}
    scenes = _ordered_scenes(present)

    items = all_items
    scene_key = scene.strip().lower()
    if scene_key:
        items = [item for item in items if item.scene.lower() == scene_key]
    q = query.strip().lower()
    if q:
        items = [
            item
            for item in items
            if q in item.slug.lower()
            or q in item.display_name.lower()
            or q in item.display_name_en.lower()
            or q in item.summary.lower()
            or q in item.summary_en.lower()
            or q in item.scene.lower()
            or q in item.sub_scene.lower()
        ]
    return items, scenes


def _fetch_all_skillsets(*, force: bool = False) -> list[SkillHubSkillset]:
    """Fetch the full SkillHub skillset list.

    The SkillHub endpoint defaults to 20 rows even though it returns ``total``.
    ``limit=`` is ignored by the current API; ``page`` + ``pageSize`` is the
    supported shape. Results are cached in-process for a short TTL with
    single-flight refresh and stale fallback on upstream failure.
    """
    global _skillset_list_cache, _skillset_list_cache_at, _skillset_list_loading

    with _skillset_list_cv:
        now = time.monotonic()
        if (
            not force
            and _skillset_list_cache is not None
            and (now - _skillset_list_cache_at) < _SKILLSET_LIST_CACHE_TTL_SECONDS
        ):
            return list(_skillset_list_cache)

        while _skillset_list_loading:
            _skillset_list_cv.wait(timeout=_HTTP_TIMEOUT + 5)
            now = time.monotonic()
            if (
                not force
                and _skillset_list_cache is not None
                and (now - _skillset_list_cache_at) < _SKILLSET_LIST_CACHE_TTL_SECONDS
            ):
                return list(_skillset_list_cache)

        stale = list(_skillset_list_cache) if _skillset_list_cache is not None else None
        _skillset_list_loading = True

    try:
        items = _load_all_skillsets_uncached()
        with _skillset_list_cv:
            _skillset_list_cache = items
            _skillset_list_cache_at = time.monotonic()
            return list(items)
    except SkillHubMarketError:
        if stale is not None and not force:
            logger.warning("SkillHub skillset list refresh failed; serving stale cache")
            return stale
        raise
    finally:
        with _skillset_list_cv:
            _skillset_list_loading = False
            _skillset_list_cv.notify_all()


def _load_all_skillsets_uncached() -> list[SkillHubSkillset]:
    items: list[SkillHubSkillset] = []
    seen: set[str] = set()
    total: int | None = None
    page = 1

    while page <= _MAX_SKILLSET_PAGES:
        data = _http_json_get(
            _api_url(
                "/api/v1/skillsets",
                params={"page": page, "pageSize": _SKILLSET_PAGE_SIZE},
            )
        )
        raw_items = data.get("skillSets") if isinstance(data, dict) else None
        if not isinstance(raw_items, list):
            raise SkillHubMarketError(
                "SkillHub skillsets response is invalid",
                kind=SkillHubMarketErrorKind.UPSTREAM_BAD_PAYLOAD,
            )
        if total is None:
            total = _coerce_positive_int(data.get("total")) if isinstance(data, dict) else None

        page_items = [_skillset_from_raw(x) for x in raw_items if isinstance(x, dict)]
        for item in page_items:
            if not item.slug or item.slug in seen:
                continue
            seen.add(item.slug)
            items.append(item)

        if not raw_items:
            break
        if total is not None and len(items) >= total:
            break
        if len(raw_items) < _SKILLSET_PAGE_SIZE:
            break
        page += 1

    return items


def fetch_skillset(slug: str) -> SkillHubSkillset:
    safe_slug = validate_skillset_slug(slug)
    data = _http_json_get(_api_url(f"/api/v1/skillsets/{quote(safe_slug, safe='')}"))
    if not isinstance(data, dict):
        raise SkillHubMarketError(
            f"SkillHub skillset {safe_slug!r} not found",
            kind=SkillHubMarketErrorKind.NOT_FOUND,
        )
    item = _skillset_from_raw(data)
    if not item.slug:
        raise SkillHubMarketError(
            f"SkillHub skillset {safe_slug!r} not found",
            kind=SkillHubMarketErrorKind.NOT_FOUND,
        )
    return item


def skill_slugs_for_skillset(item: SkillHubSkillset) -> list[str]:
    """Return a skillset's skills, using its download manifest when needed."""
    if item.skill_slugs:
        return list(item.skill_slugs)
    package = _download_skillset_package(item.slug)
    manifest, _prompt = _parse_skillset_package(
        package,
        skillset_slug=item.slug,
        fallback_content=item.content,
    )
    skill_slugs = _manifest_skill_slugs(manifest)
    if not skill_slugs:
        raise SkillHubMarketError(
            f"SkillHub skillset {item.slug!r} has no skills",
            kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
        )
    return skill_slugs


def _skillset_from_raw(raw: dict[str, Any]) -> SkillHubSkillset:
    skill_slugs = raw.get("skillSlugs")
    if not isinstance(skill_slugs, list):
        skill_slugs = []
    cleaned_slugs = tuple(str(s).strip() for s in skill_slugs if str(s).strip())
    return SkillHubSkillset(
        slug=str(raw.get("slug") or "").strip(),
        display_name=str(raw.get("displayName") or raw.get("name") or "").strip(),
        display_name_en=str(raw.get("displayNameEn") or "").strip(),
        summary=str(raw.get("summary") or raw.get("description") or "").strip(),
        summary_en=str(raw.get("summaryEn") or "").strip(),
        scene=str(raw.get("scene") or "").strip(),
        sub_scene=str(raw.get("subScene") or raw.get("sub_scene") or "").strip(),
        content=str(raw.get("content") or "").strip(),
        content_en=str(raw.get("contentEn") or "").strip(),
        icon_url=str(raw.get("iconUrl") or "").strip(),
        skill_slugs=cleaned_slugs,
        skill_count=_coerce_nonneg_int(raw.get("skillCount"), default=len(cleaned_slugs)),
        raw=raw,
    )


def _coerce_positive_int(value: Any) -> int | None:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _coerce_nonneg_int(value: Any, *, default: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return default
    return out if out >= 0 else default


def _api_host() -> str:
    return (os.environ.get("SKILLHUB_HOST", "").strip() or DEFAULT_SKILLHUB_HOST).rstrip("/")


def _api_url(path: str, params: dict[str, Any] | None = None) -> str:
    url = f"{_api_host()}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def _http_get(url: str, *, accept: str) -> bytes:
    req = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "artemis-expert-skillhub/1.0",
        },
    )
    try:
        with urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            return _read_response_limited(resp, url=url)
    except HTTPError as exc:
        if exc.code == 404:
            raise SkillHubMarketError(
                "SkillHub resource not found",
                kind=SkillHubMarketErrorKind.NOT_FOUND,
            ) from exc
        raise SkillHubMarketError(
            f"SkillHub request failed: HTTP {exc.code}",
            kind=SkillHubMarketErrorKind.UPSTREAM_FAILED,
        ) from exc
    except TimeoutError as exc:
        raise SkillHubMarketError(
            "SkillHub request timed out",
            kind=SkillHubMarketErrorKind.UPSTREAM_TIMEOUT,
        ) from exc
    except URLError as exc:
        reason = str(getattr(exc, "reason", "") or exc)
        reason_l = reason.lower()
        if looks_like_ssl_error(reason):
            raise SkillHubMarketError(
                "SkillHub request failed: SSL error",
                kind=SkillHubMarketErrorKind.SSL_ERROR,
            ) from exc
        kind = (
            SkillHubMarketErrorKind.UPSTREAM_TIMEOUT
            if "timed out" in reason_l or "timeout" in reason_l
            else SkillHubMarketErrorKind.UPSTREAM_FAILED
        )
        raise SkillHubMarketError(
            "SkillHub request failed",
            kind=kind,
        ) from exc
    except OSError as exc:
        if looks_like_ssl_error(exc):
            raise SkillHubMarketError(
                "SkillHub request failed: SSL error",
                kind=SkillHubMarketErrorKind.SSL_ERROR,
            ) from exc
        raise SkillHubMarketError(
            "SkillHub request failed",
            kind=SkillHubMarketErrorKind.UPSTREAM_FAILED,
        ) from exc


def _read_response_limited(resp: Any, *, url: str) -> bytes:
    content_length = resp.headers.get("Content-Length")
    if content_length:
        try:
            declared = int(content_length)
        except ValueError:
            declared = -1
        if declared > _MAX_HTTP_BYTES:
            raise SkillHubMarketError(
                f"SkillHub response too large for {url}",
                kind=SkillHubMarketErrorKind.PACKAGE_TOO_LARGE,
            )
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = resp.read(_HTTP_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_HTTP_BYTES:
            raise SkillHubMarketError(
                f"SkillHub response too large for {url}",
                kind=SkillHubMarketErrorKind.PACKAGE_TOO_LARGE,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _http_json_get(url: str) -> Any:
    payload = _http_get(url, accept="application/json")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillHubMarketError(
            "SkillHub returned invalid JSON",
            kind=SkillHubMarketErrorKind.UPSTREAM_BAD_PAYLOAD,
        ) from exc


def _download_skillset_package(slug: str) -> bytes:
    url = _api_url(f"/api/v1/skillsets/{quote(slug, safe='')}/download")
    return _http_get(url, accept="application/zip,*/*")


def _download_skill_package(slug: str) -> bytes:
    url = _api_url("/api/v1/download", params={"slug": slug})
    return _http_get(url, accept="application/zip,*/*")


def _parse_skillset_package(
    zip_bytes: bytes,
    *,
    skillset_slug: str,
    fallback_content: str,
) -> tuple[dict[str, Any], str]:
    try:
        import io

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            _validate_zip(zf)
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            prompt = ""
            zip_names = zf.namelist()
            skillset_files = [
                n for n in zip_names if n.startswith("skillsets/") and n.endswith(".md")
            ]
            if skillset_files:
                preferred = f"skillsets/{skillset_slug}.md"
                selected = preferred if preferred in zip_names else skillset_files[0]
                prompt = zf.read(selected).decode("utf-8")
            elif "identify.md" in zip_names:
                prompt = zf.read("identify.md").decode("utf-8")
            elif fallback_content:
                prompt = fallback_content
    except SkillHubMarketError:
        raise
    except KeyError as exc:
        raise SkillHubMarketError(
            "SkillHub skillset package missing manifest.json",
            kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
        ) from exc
    except zipfile.BadZipFile as exc:
        raise SkillHubMarketError(
            "SkillHub skillset package is not a valid zip",
            kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise SkillHubMarketError(
            "Failed to parse SkillHub skillset package",
            kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
        ) from exc
    if not isinstance(manifest, dict):
        raise SkillHubMarketError(
            "SkillHub skillset manifest is invalid",
            kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
        )
    if not prompt.strip():
        raise SkillHubMarketError(
            "SkillHub skillset package missing workflow prompt",
            kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
        )
    return manifest, _dedupe_frontmatter(prompt)


def _manifest_skill_slugs(manifest: dict[str, Any]) -> list[str]:
    raw = manifest.get("skillSlugs")
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    skillsets = manifest.get("skillSets")
    if not isinstance(skillsets, list):
        return []
    out: list[str] = []
    for item in skillsets:
        if not isinstance(item, dict):
            continue
        slugs = item.get("skillSlugs")
        if isinstance(slugs, list):
            out.extend(str(s).strip() for s in slugs if str(s).strip())
    seen: set[str] = set()
    deduped: list[str] = []
    for slug in out:
        if slug in seen:
            continue
        seen.add(slug)
        deduped.append(slug)
    return deduped


def _read_zip_member_limited(src: Any, member: zipfile.ZipInfo) -> bytes:
    remaining = member.file_size
    if remaining < 0 or remaining > _MAX_ZIP_UNCOMPRESSED_BYTES:
        raise SkillHubMarketError(
            f"zip entry too large: {member.filename}",
            kind=SkillHubMarketErrorKind.PACKAGE_TOO_LARGE,
        )
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = src.read(_HTTP_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > remaining or total > _MAX_ZIP_UNCOMPRESSED_BYTES:
            raise SkillHubMarketError(
                f"zip entry too large: {member.filename}",
                kind=SkillHubMarketErrorKind.PACKAGE_TOO_LARGE,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_zip(zf: zipfile.ZipFile) -> None:
    infos = zf.infolist()
    if len(infos) > _MAX_ZIP_ENTRIES:
        raise SkillHubMarketError(
            "zip has too many entries",
            kind=SkillHubMarketErrorKind.PACKAGE_TOO_LARGE,
        )
    total_uncompressed = 0
    for member in infos:
        path = Path(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise SkillHubMarketError(
                f"unsafe zip path entry: {member.filename}",
                kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
            )
        if member.file_size < 0:
            raise SkillHubMarketError(
                f"invalid zip entry size: {member.filename}",
                kind=SkillHubMarketErrorKind.PACKAGE_INVALID,
            )
        total_uncompressed += member.file_size
        if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_BYTES:
            raise SkillHubMarketError(
                "zip uncompressed size exceeds limit",
                kind=SkillHubMarketErrorKind.PACKAGE_TOO_LARGE,
            )
        compressed = member.compress_size or 0
        if (
            compressed > 0
            and member.file_size / compressed > _MAX_ZIP_COMPRESSION_RATIO
            and member.file_size > 1024 * 1024
        ):
            raise SkillHubMarketError(
                f"zip compression ratio too high: {member.filename}",
                kind=SkillHubMarketErrorKind.PACKAGE_TOO_LARGE,
            )


def _dedupe_frontmatter(text: str) -> str:
    """Remove a repeated leading YAML frontmatter block if SkillHub duplicated it."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    block = text[: end + 4]
    rest = text[end + 4 :].lstrip("\n")
    if rest.startswith(block):
        return f"{block}\n\n{rest[len(block) :].lstrip()}"
    return text


def _scene_icon_name(scene: str) -> str:
    mapping = {
        "academic": "book-open",
        "content-creation": "pen-tool",
        "design": "palette",
        "ecommerce": "globe",
        "education": "book-open",
        "finance": "candlestick-chart",
        "healthcare": "heart",
        "lifestyle": "heart",
        "marketing": "trending-up",
        "mysticism": "sparkles",
        "tech": "cpu",
        "media": "video",
        "legal": "file-text",
        "hr": "user",
        "office": "presentation",
        "data": "trending-up",
    }
    return mapping.get(scene, "zap")
