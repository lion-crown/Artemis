from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from artemis.infra.agents.business_workspace import BusinessWorkspaceReader, business_public_scopes


class _Workspace:
    def __init__(self) -> None:
        self.grep_paths: list[str] = []
        self.glob_paths: list[str] = []

    async def agrep(self, query: str, path: str = ".") -> object:
        self.grep_paths.append(path)
        return SimpleNamespace(
            matches=[
                SimpleNamespace(path="/PhotoRule.java", line=12, text=f"{query} allowed"),
                SimpleNamespace(path="/.artemis/secret.txt", line=1, text="secret"),
                SimpleNamespace(
                    path="/Users/example/business/.artemis/secret.java",
                    line=1,
                    text="host secret",
                ),
                SimpleNamespace(
                    path="/db/migration.java",
                    line=1,
                    text="migration noise",
                ),
            ],
            truncated=False,
        )

    async def aglob(self, pattern: str, path: str = ".") -> object:
        self.glob_paths.append(path)
        return SimpleNamespace(
            matches=[
                SimpleNamespace(path="/data/OnsitePhotos.vue"),
                SimpleNamespace(path="/.artemis/session.json"),
            ],
            truncated=False,
        )

    async def aread_text(self, path: str, *, limit: int = 10_000_000) -> str | None:
        if path == "/.artemis/secret.txt":
            return "secret"
        return "line one\nline two\nline three\nline four"


class _TruncatingWorkspace(_Workspace):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content
        self.read_limits: list[int] = []

    async def aread_text(self, path: str, *, limit: int = 10_000_000) -> str | None:
        self.read_limits.append(limit)
        return self.content[:limit]


class _ContextWorkspace(_Workspace):
    async def aread_text(self, path: str, *, limit: int = 10_000_000) -> str | None:
        return "\n".join(f"line {index}" for index in range(1, 21))

    async def aglob(self, pattern: str, path: str = ".") -> object:
        self.glob_paths.append(path)
        return SimpleNamespace(matches=[SimpleNamespace(path="/PhotoRule.java")], truncated=False)


class _ModuleNavigationWorkspace(_ContextWorkspace):
    async def aread_text(self, path: str, *, limit: int = 10_000_000) -> str | None:
        if path.endswith("UploadPhotoTaskJob.java"):
            return "D+1 自动完成上传照片待办"
        return await super().aread_text(path, limit=limit)

    async def agrep(self, query: str, path: str = ".") -> object:
        self.grep_paths.append(path)
        return SimpleNamespace(
            matches=[
                SimpleNamespace(
                    path="/sp-service/src/main/java/com/ey/e2e/sp/modules/photo/domain/MeetingPhotoDispatch.java",
                    line=12,
                    text="现场照片逻辑控制",
                )
            ],
            truncated=False,
        )

    async def aglob(self, pattern: str, path: str = ".") -> object:
        self.glob_paths.append(path)
        if path.endswith("/modules/photo") and pattern == "**/job/*.java":
            return SimpleNamespace(
                matches=[
                    SimpleNamespace(
                        path="/sp-service/src/main/java/com/ey/e2e/sp/modules/photo/job/UploadPhotoTaskJob.java"
                    )
                ],
                truncated=False,
            )
        return SimpleNamespace(matches=[], truncated=False)


class _MultiModuleNavigationWorkspace(_ModuleNavigationWorkspace):
    async def agrep(self, query: str, path: str = ".") -> object:
        self.grep_paths.append(path)
        return SimpleNamespace(
            matches=[
                SimpleNamespace(
                    path="/st-service/src/main/java/com/ey/e2e/st/modules/photo/domain/MeetingPhotoDispatch.java",
                    line=12,
                    text="现场照片逻辑控制",
                ),
                SimpleNamespace(
                    path="/sp-service/src/main/java/com/ey/e2e/sp/modules/photo/domain/MeetingPhotoDispatch.java",
                    line=12,
                    text="现场照片逻辑控制",
                ),
            ],
            truncated=False,
        )

    async def aglob(self, pattern: str, path: str = ".") -> object:
        self.glob_paths.append(path)
        if path.endswith("/st/modules/photo") and pattern == "**/job/*.java":
            return SimpleNamespace(
                matches=[
                    SimpleNamespace(
                        path=f"/st-service/src/main/java/com/ey/e2e/st/modules/photo/job/StJob{index}.java"
                    )
                    for index in range(12)
                ],
                truncated=False,
            )
        if path.endswith("/sp/modules/photo") and pattern == "**/job/*.java":
            return SimpleNamespace(
                matches=[
                    SimpleNamespace(
                        path="/sp-service/src/main/java/com/ey/e2e/sp/modules/photo/job/UploadPhotoTaskJob.java"
                    )
                ],
                truncated=False,
            )
        return SimpleNamespace(matches=[], truncated=False)


def _reader() -> tuple[BusinessWorkspaceReader, _Workspace]:
    workspace = _Workspace()
    return (
        BusinessWorkspaceReader(
            workspace=workspace,  # type: ignore[arg-type]
            scopes={"backend": "/", "frontend": "/data/"},
        ),
        workspace,
    )


def test_public_scopes_exclude_the_private_system_route() -> None:
    scopes = business_public_scopes(
        {
            "type": "composite",
            "default": {"type": "local_shell", "root_dir": "backend"},
            "routes": {
                "/data/": {"type": "local_shell", "root_dir": "frontend"},
                "/.artemis/": {"type": "local_shell", "root_dir": "private"},
            },
        },
        ".artemis",
    )

    assert scopes == {"backend": "/", "data": "/data/"}


def test_public_scopes_use_named_storage_label_for_a_host_absolute_route() -> None:
    scopes = business_public_scopes(
        {
            "type": "composite",
            "default": {"type": "named", "name": "gsk后端"},
            "routes": {
                "/Users/example/gsk/e2e-web": {"type": "named", "name": "gsk前端"},
            },
        },
        ".artemis",
    )

    assert scopes == {"backend": "/", "gsk前端": "/Users/example/gsk/e2e-web/"}


@pytest.mark.asyncio
async def test_search_filters_private_matches_and_uses_the_selected_scope() -> None:
    reader, workspace = _reader()

    raw = await reader.search(
        query="photo",
        scope="backend",
        file_glob="*.java",
        max_matches=10,
    )

    payload = json.loads(raw)
    assert workspace.grep_paths == ["/"]
    assert payload["matches"] == [{"path": "/PhotoRule.java", "line": 12, "text": "photo allowed"}]
    assert "/.artemis/" not in raw
    assert "host secret" not in raw
    assert "migration noise" not in raw


@pytest.mark.asyncio
async def test_find_filters_private_matches_and_uses_a_public_route() -> None:
    reader, workspace = _reader()

    raw = await reader.find(pattern="*Photos.vue", scope="frontend")

    payload = json.loads(raw)
    assert workspace.glob_paths == ["/data/"]
    assert payload["paths"] == ["/data/OnsitePhotos.vue"]
    assert "/.artemis/" not in raw


@pytest.mark.asyncio
async def test_search_does_not_return_another_public_scope() -> None:
    reader, _workspace = _reader()

    raw = await reader.search(
        query="photo",
        scope="frontend",
        file_glob=None,
        max_matches=10,
    )

    assert json.loads(raw)["matches"] == []


@pytest.mark.asyncio
async def test_read_rejects_private_paths_without_returning_private_content() -> None:
    reader, _workspace = _reader()

    raw = await reader.read(path="/.artemis/secret.txt", offset=0, limit=100)

    assert "not available" in raw
    assert "secret" not in raw


@pytest.mark.asyncio
async def test_read_applies_offset_and_line_limit() -> None:
    reader, _workspace = _reader()

    raw = await reader.read(path="/PhotoRule.java", offset=2, limit=2)

    assert raw == "文件: /PhotoRule.java (共 4 行，显示 2-3)\n     2→line two\n     3→line three"


@pytest.mark.asyncio
async def test_grep_returns_matching_line_with_context() -> None:
    workspace = _ContextWorkspace()
    reader = BusinessWorkspaceReader(
        workspace=workspace,  # type: ignore[arg-type]
        scopes={"backend": "/"},
    )

    raw = await reader.grep(
        pattern="photo",
        scope="backend",
        file_glob="*.java",
        max_results=10,
        case_insensitive=False,
    )

    assert "PhotoRule.java:12: photo allowed" in raw
    assert "    10→line 10" in raw
    assert "    14→line 14" in raw
    assert "host secret" not in raw
    assert workspace.grep_paths == ["/PhotoRule.java"]


@pytest.mark.asyncio
async def test_glob_returns_agent_scope_file_list() -> None:
    reader, _workspace = _reader()

    raw = await reader.glob(pattern="*Photos.vue", scope="frontend")

    assert raw == "找到 1 个文件:\n/data/OnsitePhotos.vue"


@pytest.mark.asyncio
async def test_grep_surfaces_same_module_task_and_job_candidates() -> None:
    workspace = _ModuleNavigationWorkspace()
    reader = BusinessWorkspaceReader(
        workspace=workspace,  # type: ignore[arg-type]
        scopes={"backend": "/"},
    )

    raw = await reader.grep(
        pattern="现场照片",
        scope="backend",
        file_glob=None,
        max_results=10,
        case_insensitive=False,
    )

    assert "同模块的任务/定时任务候选" in raw
    assert "UploadPhotoTaskJob.java" in raw
    assert "同模块任务/定时任务摘要" in raw
    assert "D+1 自动完成上传照片待办" in raw
    assert raw.index("同模块任务/定时任务摘要") < raw.index("MeetingPhotoDispatch.java:12")


@pytest.mark.asyncio
async def test_grep_collects_candidates_from_every_matched_business_module() -> None:
    workspace = _MultiModuleNavigationWorkspace()
    reader = BusinessWorkspaceReader(
        workspace=workspace,  # type: ignore[arg-type]
        scopes={"backend": "/"},
    )

    raw = await reader.grep(
        pattern="现场照片",
        scope="backend",
        file_glob=None,
        max_results=10,
        case_insensitive=False,
    )

    assert "UploadPhotoTaskJob.java" in raw


@pytest.mark.asyncio
async def test_read_uses_the_full_material_before_applying_a_late_line_offset() -> None:
    content = "\n".join([*(f"filler {index} {'x' * 50}" for index in range(600)), "target rule"])
    workspace = _TruncatingWorkspace(content)
    reader = BusinessWorkspaceReader(
        workspace=workspace,  # type: ignore[arg-type]
        scopes={"backend": "/"},
    )

    raw = await reader.read(path="/PhotoRule.java", offset=601, limit=1)

    assert raw.endswith("   601→target rule")
    assert workspace.read_limits[0] >= len(content)
