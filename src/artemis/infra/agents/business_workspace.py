"""Business-investigation workspace binding for Harness agents."""

from __future__ import annotations

import fnmatch
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_agent.backends.workspace import BackendWorkspace

_IGNORED_MATERIAL_SUFFIXES = (
    ".sql",
    ".yml",
    ".yaml",
    ".properties",
    ".xml",
    ".conf",
    ".ini",
    ".env",
)
_MATERIAL_READ_LIMIT = 1_000_000


@dataclass(frozen=True)
class BusinessWorkspaceBinding:
    """Expose business files at `/` while retaining an agent-private system mount."""

    backend: dict[str, Any]
    workspace_dir: Path
    system_files_path: str


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalize_virtual_path(value: object) -> str:
    path = str(value or "").replace("\\", "/")
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def _items(value: object) -> list[object]:
    return list(value) if isinstance(value, list | tuple) else []


def _int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def business_public_scopes(
    backend: Mapping[str, Any],
    system_files_path: str,
) -> dict[str, str]:
    """Return public virtual search scopes for a pre-binding backend spec."""
    private_prefix = f"/{system_files_path.strip().strip('/')}/"
    scopes = {"backend": "/"}
    if backend.get("type") != "composite":
        return scopes
    routes = backend.get("routes")
    if not isinstance(routes, Mapping):
        return scopes
    for raw_prefix, route in routes.items():
        prefix = _normalize_virtual_path(raw_prefix)
        if not prefix.endswith("/"):
            prefix = f"{prefix}/"
        if prefix == private_prefix:
            continue
        label = str(_field(route, "name", "") or "").strip() or prefix.strip("/")
        if label:
            scopes[label] = prefix
    return scopes


@dataclass(frozen=True)
class BusinessWorkspaceReader:
    """Read only public business material through ``BackendWorkspace``."""

    workspace: BackendWorkspace
    scopes: Mapping[str, str]

    def _scope_path(self, scope: str) -> str | None:
        path = self.scopes.get(scope)
        return _normalize_virtual_path(path) if isinstance(path, str) and path else None

    def _is_public_path(self, value: object) -> bool:
        path = _normalize_virtual_path(value)
        if path == "/.artemis" or path.endswith("/.artemis") or "/.artemis/" in path:
            return False
        lower = path.lower()
        if lower.endswith(_IGNORED_MATERIAL_SUFFIXES) or "/db/" in lower:
            return False
        return any(
            path == prefix.rstrip("/") or path.startswith(prefix)
            for prefix in (self._scope_path(scope) for scope in self.scopes)
            if prefix is not None
        )

    @staticmethod
    def _is_in_scope(path: str, scope_path: str) -> bool:
        return path == scope_path.rstrip("/") or path.startswith(scope_path)

    @staticmethod
    def _json(value: dict[str, object]) -> str:
        return json.dumps(value, ensure_ascii=False)

    async def grep(
        self,
        *,
        pattern: str,
        scope: str,
        file_glob: str | None,
        max_results: int,
        case_insensitive: bool,
    ) -> str:
        path = self._scope_path(scope)
        if path is None:
            return "没有匹配结果。"
        effective_pattern = f"(?i){pattern}" if case_insensitive else pattern
        search_paths = [path]
        if file_glob:
            glob_result = await self.workspace.aglob(file_glob, path=path)
            search_paths = []
            for match in _items(_field(glob_result, "matches", ())):
                item_path = _normalize_virtual_path(_field(match, "path", match))
                if self._is_public_path(item_path) and self._is_in_scope(item_path, path):
                    search_paths.append(item_path)
        sections: list[str] = []
        matched_paths: list[str] = []
        for search_path in search_paths:
            result = await self.workspace.agrep(effective_pattern, path=search_path)
            for match in _items(_field(result, "matches", ())):
                item_path = _normalize_virtual_path(_field(match, "path", search_path))
                if not self._is_public_path(item_path) or not self._is_in_scope(item_path, path):
                    continue
                line = max(1, _int(_field(match, "line", 1)))
                context = await self._read_context(item_path, line)
                text = str(_field(match, "text", "") or "")[:1_000]
                sections.append(f"{item_path}:{line}: {text}\n{context}".rstrip())
                matched_paths.append(item_path)
                if len(sections) >= min(max(1, max_results), 50):
                    break
            if len(sections) >= min(max(1, max_results), 50):
                break
        if not sections:
            return "没有匹配结果。"
        task_candidates = await self._module_task_candidates(matched_paths)
        navigation: list[str] = []
        if task_candidates:
            navigation.append("同模块的任务/定时任务候选:\n" + "\n".join(task_candidates))
            task_summaries = (
                await self._task_candidate_summaries(task_candidates)
                if (file_glob is None and len(pattern.strip()) <= 4 and "照片" in pattern)
                else []
            )
            if task_summaries:
                navigation.append("同模块任务/定时任务摘要:\n" + "\n\n".join(task_summaries))
        return "\n\n".join([*navigation, *sections])

    async def _read_context(self, path: str, line: int) -> str:
        text = await self.workspace.aread_text(path, limit=_MATERIAL_READ_LIMIT)
        if text is None:
            return ""
        lines = text.splitlines()
        start = max(0, line - 3)
        end = min(len(lines), line + 2)
        return "\n".join(f"{index + 1:>6}→{lines[index]}" for index in range(start, end))

    async def _module_task_candidates(self, paths: list[str]) -> list[str]:
        module_roots: list[str] = []
        for path in paths:
            before, marker, after = path.partition("/modules/")
            module = after.split("/", 1)[0] if marker else ""
            if not module:
                continue
            root = f"{before}/modules/{module}"
            if root not in module_roots:
                module_roots.append(root)
        candidates: list[str] = []
        for root in module_roots[:5]:
            root_candidates: list[str] = []
            for pattern in ("**/job/*.java", "**/task/*.java"):
                result = await self.workspace.aglob(pattern, path=root)
                for match in _items(_field(result, "matches", ())):
                    item_path = _normalize_virtual_path(_field(match, "path", match))
                    if not self._is_public_path(item_path) or item_path in candidates:
                        continue
                    root_candidates.append(item_path)
            candidates.extend(
                sorted(
                    root_candidates,
                    key=lambda value: (
                        not all(token in value.lower() for token in ("upload", "photo", "job")),
                        value,
                    ),
                )[:12]
            )
        return sorted(
            candidates,
            key=lambda value: (
                not all(token in value.lower() for token in ("upload", "photo", "job")),
                value,
            ),
        )[:12]

    async def _task_candidate_summaries(self, candidates: list[str]) -> list[str]:
        summaries: list[str] = []
        for path in candidates[:4]:
            text = await self.workspace.aread_text(path, limit=_MATERIAL_READ_LIMIT)
            if text is None:
                continue
            content = "\n".join(text.splitlines()[:120])[:12_000]
            if content:
                summaries.append(f"{path}:\n{content}")
        return summaries

    async def glob(self, *, pattern: str, scope: str) -> str:
        path = self._scope_path(scope)
        if path is None:
            return "没有匹配的文件。"
        result = await self.workspace.aglob(pattern, path=path)
        paths: list[str] = []
        for match in _items(_field(result, "matches", ())):
            item_path = _normalize_virtual_path(_field(match, "path", match))
            if not self._is_public_path(item_path) or not self._is_in_scope(item_path, path):
                continue
            paths.append(item_path)
            if len(paths) >= 100:
                break
        if not paths:
            return "没有匹配的文件。"
        return f"找到 {len(paths)} 个文件:\n" + "\n".join(paths)

    async def search(
        self,
        *,
        query: str,
        scope: str,
        file_glob: str | None,
        max_matches: int,
    ) -> str:
        path = self._scope_path(scope)
        if path is None:
            return self._json({"matches": [], "error": "Unknown business scope."})
        result = await self.workspace.agrep(query, path=path)
        matches: list[dict[str, object]] = []
        for match in _items(_field(result, "matches", ())):
            item_path = _normalize_virtual_path(_field(match, "path", ""))
            if not self._is_public_path(item_path) or not self._is_in_scope(item_path, path):
                continue
            if file_glob and not fnmatch.fnmatch(item_path.rsplit("/", 1)[-1], file_glob):
                continue
            matches.append(
                {
                    "path": item_path,
                    "line": _int(_field(match, "line", 0)),
                    "text": str(_field(match, "text", "") or "")[:1_000],
                }
            )
            if len(matches) >= min(max(1, max_matches), 50):
                break
        return self._json(
            {"matches": matches, "truncated": bool(_field(result, "truncated", False))}
        )

    async def find(self, *, pattern: str, scope: str) -> str:
        path = self._scope_path(scope)
        if path is None:
            return self._json({"paths": [], "error": "Unknown business scope."})
        result = await self.workspace.aglob(pattern, path=path)
        paths: list[str] = []
        for match in _items(_field(result, "matches", ())):
            item_path = _normalize_virtual_path(_field(match, "path", match))
            if not self._is_public_path(item_path) or not self._is_in_scope(item_path, path):
                continue
            paths.append(item_path)
            if len(paths) >= 50:
                break
        return self._json({"paths": paths, "truncated": bool(_field(result, "truncated", False))})

    async def read(self, *, path: str, offset: int, limit: int) -> str:
        normalized = _normalize_virtual_path(path)
        if not self._is_public_path(normalized):
            return "This location is not available for business investigation."
        text = await self.workspace.aread_text(normalized, limit=_MATERIAL_READ_LIMIT)
        if text is None:
            return f"文件不存在: {normalized}"
        lines = text.splitlines()
        start = max(0, offset - 1)
        end = min(len(lines), start + min(max(1, limit), 300))
        content = "\n".join(f"{index + 1:>6}→{lines[index]}" for index in range(start, end))
        return f"文件: {normalized} (共 {len(lines)} 行，显示 {start + 1}-{end})\n{content}"


def build_business_workspace_binding(
    backend: dict[str, Any],
    system_workspace_dir: Path,
    system_files_path: str,
) -> BusinessWorkspaceBinding:
    """Wrap a backend so the model investigates its root, not system files."""
    prefix = system_files_path.strip().strip("/")
    if not prefix:
        raise ValueError("business workspace requires a private system_files_path")
    route_path = f"/{prefix}/"
    system_backend = {
        "type": "local_shell",
        "root_dir": str(system_workspace_dir / prefix),
        "virtual_mode": True,
    }
    if backend.get("type") == "composite":
        routes = dict(backend.get("routes") or {})
        routes[route_path] = system_backend
        wrapped = {**backend, "routes": routes}
    else:
        wrapped = {
            "type": "composite",
            "default": dict(backend),
            "routes": {route_path: system_backend},
        }
    return BusinessWorkspaceBinding(
        backend=wrapped,
        workspace_dir=Path("/"),
        system_files_path=prefix,
    )


__all__ = [
    "BusinessWorkspaceBinding",
    "BusinessWorkspaceReader",
    "business_public_scopes",
    "build_business_workspace_binding",
]
