from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Default prompts shipped alongside this package.
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class Config:
    """Resolves ~/.boukensha (or $BOUKENSHA_DIR), loads .env and settings.yaml."""

    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable (explicit override)
    #   2. .boukensha in the current working directory, if it actually exists
    #   3. ~/.boukensha  (default)
    DEFAULT_DIR = Path.home() / ".boukensha"

    def __init__(self) -> None:
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()

    # ---------- tasks -------------------------------------------------

    def tasks(self, name: str | None = None) -> dict:
        """With no argument: the full tasks hash. With a name: that task's settings."""
        all_tasks = self.dig("tasks") or {}
        return all_tasks.get(name, {}) if name else all_tasks

    @property
    def user_prompts_dir(self) -> Path:
        return self.dir / "prompts"

    # ---------- MUD connection -----------------------------------------
    # (dropped in step 06's snapshot, back in step 07's — snapshot drift,
    # not a design change; still unused everywhere in this port)

    @property
    def mud_host(self) -> str:
        return self.dig("mud", "host") or "localhost"

    @property
    def mud_port(self) -> int:
        return self.dig("mud", "port") or 4000

    @property
    def mud_username(self) -> str | None:
        return self.dig("mud", "username")

    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- low-level helpers ----------------------------------------

    def dig(self, *keys: str):
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node = self.settings
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node

    def __repr__(self) -> str:
        return f"<Boukensha::Config dir={self.dir} tasks={','.join(self.tasks().keys())}>"

    # ---------- private -----------------------------------------------

    def _resolve_dir(self) -> Path:
        # 1. Explicit override
        env_dir = os.environ.get("BOUKENSHA_DIR")
        if env_dir:
            return Path(env_dir).expanduser().resolve()

        # 2. .boukensha in the current working directory
        cwd_dir = Path.cwd() / ".boukensha"
        if cwd_dir.is_dir():
            return cwd_dir

        # 3. ~/.boukensha default
        return self.DEFAULT_DIR.expanduser().resolve()

    def _load_env(self) -> None:
        env_file = self.dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self) -> dict:
        settings_file = self.dir / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
