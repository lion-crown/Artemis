"""Filesystem layout for ``~/.artemis/``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def restrict_to_owner(path: Path, mode: int) -> Path:
    """Apply POSIX owner-only permissions to a runtime path when supported."""
    if os.name == "posix":
        path.chmod(mode)
    return path


def ensure_private_dir(path: Path) -> Path:
    """Create a runtime directory and make it accessible only to its owner."""
    path.mkdir(parents=True, exist_ok=True)
    return restrict_to_owner(path, PRIVATE_DIR_MODE)


@dataclass(frozen=True)
class PathLayout:
    root: Path

    @classmethod
    def from_env(cls) -> PathLayout:
        """Resolve install root from ``ARTEMIS_HOME`` or ``~/.artemis``."""
        raw = os.environ.get("ARTEMIS_HOME", "").strip()
        if raw:
            return cls(Path(raw).expanduser())
        return cls(Path.home() / ".artemis")

    @property
    def db(self) -> Path:
        return self.root / "artemis.db"

    @property
    def logs_dir(self) -> Path:
        """Structured runtime logs: ``~/.artemis/logs/``."""
        return self.root / "logs"

    @property
    def log(self) -> Path:
        return self.logs_dir / "artemis.log"

    def ensure_logs_dir(self) -> Path:
        """Create the logs directory and return it."""
        self.ensure_root()
        out = ensure_private_dir(self.logs_dir)
        for existing_log in out.glob("*.log"):
            if existing_log.is_file():
                restrict_to_owner(existing_log, PRIVATE_FILE_MODE)
        return out

    def ensure_log(self) -> Path:
        """Create the logs directory and return ``artemis.log``."""
        return self.ensure_log_file(self.log.name)

    def ensure_log_file(self, name: str) -> Path:
        """Create an owner-only log file under the managed logs directory."""
        target = self.ensure_logs_dir() / Path(name).name
        target.touch(exist_ok=True)
        return restrict_to_owner(target, PRIVATE_FILE_MODE)

    @property
    def config(self) -> Path:
        return self.root / "config.json"

    @property
    def users_dir(self) -> Path:
        return self.root / "users"

    def user_dir(self, username: str) -> Path:
        return self.users_dir / username

    @property
    def agents_dir(self) -> Path:
        """Global agents directory: ~/.artemis/agents/"""
        return self.root / "agents"

    @property
    def published_experts_dir(self) -> Path:
        """User-published expert snapshots: ``~/.artemis/published_experts/``."""
        return self.root / "published_experts"

    @property
    def skill_packages_dir(self) -> Path:
        """Global skill package content: ``~/.artemis/skill-packages/``."""
        return self.root / "skill-packages"

    @property
    def knowledge_dir(self) -> Path:
        """Global knowledge base files: ``~/.artemis/knowledge/``."""
        return self.root / "knowledge"

    def agent_workspace(self, agent_id: str) -> Path:
        """Global agent workspace: ~/.artemis/agents/<agent_id>/"""
        return self.agents_dir / agent_id

    def ensure_agent_workspace(self, agent_id: str) -> Path:
        """Global agent workspace, mkdir -p."""
        self.ensure_root()
        ensure_private_dir(self.agents_dir)
        out = self.agent_workspace(agent_id)
        return ensure_private_dir(out)

    def ensure_root(self) -> Path:
        return ensure_private_dir(self.root)

    @property
    def plugins_dir(self) -> Path:
        return self.root / "plugins"

    @property
    def tool_guard_rules_dir(self) -> Path:
        """User-editable command guard rules: ``~/.artemis/security/tool_guard/``."""
        return self.root / "security" / "tool_guard"

    @property
    def tool_guard_rules_file(self) -> Path:
        return self.tool_guard_rules_dir / "dangerous_shell_commands.yaml"

    @property
    def backups_dir(self) -> Path:
        """Stored system backup archives: ``~/.artemis/backups/``."""
        return self.root / "backups"

    def ensure_backups_dir(self) -> Path:
        self.ensure_root()
        return ensure_private_dir(self.backups_dir)

    def backup_file(self, filename: str) -> Path:
        """Resolve a backup archive path under :attr:`backups_dir` (basename only)."""
        return self.backups_dir / Path(filename).name

    @property
    def ssl_dir(self) -> Path:
        """TLS certificates and ACME account keys: ``~/.artemis/ssl/``."""
        return self.root / "ssl"

    def ensure_ssl_dir(self) -> Path:
        self.ensure_root()
        return ensure_private_dir(self.ssl_dir)

    @property
    def connector_cli_dir(self) -> Path:
        """Per-instance CLI config roots: ``~/.artemis/connector-cli/``."""
        return self.root / "connector-cli"

    def connector_cli_instance_dir(self, kind: str, instance_key: str) -> Path:
        """Isolated config dir for one connector CLI instance."""
        safe_kind = Path(kind).name
        safe_key = (
            "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in instance_key)[:80]
            or "default"
        )
        return self.connector_cli_dir / safe_kind / safe_key

    def ensure_connector_cli_instance_dir(self, kind: str, instance_key: str) -> Path:
        self.ensure_root()
        ensure_private_dir(self.connector_cli_dir)
        ensure_private_dir(self.connector_cli_dir / Path(kind).name)
        out = self.connector_cli_instance_dir(kind, instance_key)
        return ensure_private_dir(out)
