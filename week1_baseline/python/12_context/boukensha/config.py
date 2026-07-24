from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


class Config:
    """Resolves ~/.boukensha (or $BOUKENSHA_DIR), loads .env and settings.yaml.

    No more Tasks::Base/Tasks::Player layer (removed in this step, along with
    the whole boukensha/tasks/ package) — provider/model/agent-limit lookups
    are now flat methods here instead of going through a per-task settings
    hash. The settings.yaml *schema* is unchanged (still tasks.player.*);
    only the Ruby/Python code path collapsed."""

    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable (explicit override)
    #   2. .boukensha in the current working directory, if it actually exists
    #   3. ~/.boukensha  (default)
    DEFAULT_DIR = Path.home() / ".boukensha"

    def __init__(self) -> None:
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()
        self.system_prompt = self._load_system_prompt()

    # ---------- provider -------------------------------------------------

    @property
    def provider_type(self) -> str:
        return self.dig("tasks", "player", "provider") or "anthropic"

    @property
    def model(self) -> str:
        return self.dig("tasks", "player", "model") or "claude-haiku-4-5"

    # ---------- system prompt ---------------------------------------------

    @property
    def system_override(self) -> bool:
        # Dead code, ported for parity: never called anywhere, and reads a
        # different settings key ("system.override") than the one
        # _load_system_prompt actually uses ("tasks.player.prompt_override.system").
        # Reads like an abandoned half-step toward flattening settings.yaml
        # further, left behind when this step's refactor happened.
        return self.dig("system", "override") is True

    # ---------- MUD connection ---------------------------------------------

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

    # ---------- agent limits -------------------------------------------------
    # Static per-turn circuit breakers, read where the agent is constructed.
    # A value of 0 or None means "disabled" (no ceiling) — useful for debugging.

    @property
    def agent_max_iterations(self) -> int:
        v = self.dig("agent", "max_iterations")
        return 25 if v is None else int(v)

    @property
    def agent_max_output_tokens(self) -> int:
        v = self.dig("agent", "max_output_tokens")
        return 1024 if v is None else int(v)

    @property
    def agent_max_turn_tokens(self) -> int:
        v = self.dig("agent", "max_turn_tokens")
        return 60_000 if v is None else int(v)

    @property
    def agent_compaction_threshold(self) -> float:
        v = self.dig("agent", "compaction_threshold")
        return 0.85 if v is None else float(v)

    # ---------- low-level helpers ----------------------------------------

    def dig(self, *keys: str):
        """Fetch a nested key path from settings, e.g. dig("provider", "model")."""
        node = self.settings
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node

    def __repr__(self) -> str:
        return f"<Boukensha::Config dir={self.dir} provider={self.provider_type} model={self.model}>"

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

    def _load_system_prompt(self) -> str | None:
        """Resolves the system prompt. When the player task opts into a
        prompt override (tasks.player.prompt_override.system: true), the
        task-scoped file prompts/player/system.md wins; otherwise (and as a
        fallback) the flat prompts/system.md is used. Returns None when
        neither exists. Unlike every step through 11, there is no
        package-shipped default to fall back to — only the user's own
        .boukensha/ directory is ever consulted."""
        if self.dig("tasks", "player", "prompt_override", "system") is True:
            task_file = self.dir / "prompts" / "player" / "system.md"
            if task_file.exists():
                return task_file.read_text().strip()

        system_file = self.dir / "prompts" / "system.md"
        return system_file.read_text().strip() if system_file.exists() else None
