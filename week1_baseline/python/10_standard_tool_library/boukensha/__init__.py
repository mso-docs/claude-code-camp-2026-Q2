from __future__ import annotations

import os
from typing import Callable

from . import backends, state
from .agent import Agent
from .client import Client
from .config import PROMPTS_DIR, Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .repl import Repl
from .run_dsl import RunDSL
from .state import config, is_debug, is_quiet, set_debug, set_loud, set_quiet
from .tasks.player import Player
from .tool import Tool
# Aliased: run()/repl() have a `mud=` keyword parameter, which would shadow
# a bare `from .tools import mud` at call time. Ruby doesn't hit this
# (Tools::Mud, capitalized, is a different identifier from a local `mud`
# variable); Python has no such built-in distinction, so the import itself
# is renamed instead.
from .tools import file_system, shell
from .tools import mud as mud_tools
from .version import VERSION

_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
    # "ollama" deliberately absent: local Ollama needs no API key.
}


def _mud_opts_from_config(cfg: Config) -> dict | None:
    """Build a mud options dict from config (used when mud=None is passed to
    run()/repl()). Returns None if no MUD host is configured."""
    if not (cfg.mud_host and cfg.mud_username):
        return None
    return {"host": cfg.mud_host, "port": cfg.mud_port, "name": cfg.mud_username, "password": cfg.mud_password}


def run(
    *,
    task: str,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    block: Callable[[RunDSL], None] | None = None,
) -> str:
    """One-shot run: send a single task, get a response, return.
    See boukensha.repl for the interactive equivalent.

    working_dir:      roots all tool calls to this directory (default: the
                       current working directory, resolved fresh on every
                       call — not baked in as a function-definition-time
                       default, since the cwd can change between calls).
                       Registers tools.file_system (pwd, list_directory,
                       read_file, write_file, delete_file, search_files) and
                       tools.shell (run_command) automatically.
                       Pass working_dir=False to opt out entirely.

    allowed_commands:  list of shell-executable names the agent is allowed to
                       run via run_command (e.g. ["python", "git"]).
                       None (default) permits everything — useful for demos.
                       Pass an empty list to disable run_command entirely.

    shell_timeout:     Seconds before a run_command is killed (default 30).

    mud:               dict of MUD connection options — registers all MUD
                       gameplay tools and keeps a single session alive
                       across every tool call. When None (default),
                       config.mud_* values are used if mud_host is set in
                       settings.yaml. Pass mud=False to disable entirely.
    """
    cfg = config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name)

    if system is None:
        system = task_class.system_prompt(
            task_settings, user_prompts_dir=cfg.user_prompts_dir, default_prompts_dir=PROMPTS_DIR
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None:
        env_var = _API_KEY_ENV_VARS.get(backend)
        api_key = os.environ.get(env_var) if env_var else None
    if working_dir is None:
        working_dir = os.getcwd()

    ctx = Context(task=task_class, system=system, working_dir=working_dir or None)
    registry = Registry(ctx)

    if working_dir:
        file_system.register(registry, working_dir=working_dir)
        shell.register(registry, working_dir=working_dir, timeout=shell_timeout, allowed_commands=allowed_commands)

    # mud=None means "use config if host is set"; mud=False means "skip entirely"
    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        mud_tools.register(registry, **resolved_mud)

    if block is not None:
        block(RunDSL(registry))

    logger = None
    try:
        if backend == "anthropic":
            be = backends.Anthropic(api_key=api_key, model=model)
        elif backend == "openai":
            be = backends.OpenAI(api_key=api_key, model=model)
        elif backend == "gemini":
            be = backends.Gemini(api_key=api_key, model=model)
        elif backend == "ollama":
            be = backends.Ollama(host=ollama_host, model=model)
        elif backend == "ollama_cloud":
            be = backends.OllamaCloud(api_key=api_key, model=model)
        else:
            raise ValueError(
                f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
            )

        builder = PromptBuilder(ctx, be)
        client = Client(builder)
        effective_max_iterations = task_class.max_iterations(task_settings)
        effective_max_output_tokens = (
            max_output_tokens if max_output_tokens is not None else task_class.max_output_tokens(task_settings)
        )
        logger = Logger(
            log=log,
            snapshot={
                "task": task_class.task_name,
                "max_iterations": effective_max_iterations,
                "max_output_tokens": effective_max_output_tokens,
                "model": model,
                "provider": backend,
            },
        )
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
        )

        ctx.add_message("user", task)
        return agent.run()
    finally:
        if logger is not None:
            logger.close()


def repl(
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    block: Callable[[RunDSL], None] | None = None,
) -> None:
    """Interactive REPL — see boukensha.run for full option documentation.

    This setup logic intentionally duplicates run()'s rather than sharing a
    helper — that's how the Ruby reference does it too (self.run and
    self.repl are independent, copy-pasted method bodies), and refactoring
    it away would be a change this step's Ruby source didn't make.
    """
    cfg = config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name)

    if system is None:
        system = task_class.system_prompt(
            task_settings, user_prompts_dir=cfg.user_prompts_dir, default_prompts_dir=PROMPTS_DIR
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None:
        env_var = _API_KEY_ENV_VARS.get(backend)
        api_key = os.environ.get(env_var) if env_var else None
    if working_dir is None:
        working_dir = os.getcwd()

    ctx = Context(task=task_class, system=system, working_dir=working_dir or None)
    registry = Registry(ctx)

    if working_dir:
        file_system.register(registry, working_dir=working_dir)
        shell.register(registry, working_dir=working_dir, timeout=shell_timeout, allowed_commands=allowed_commands)

    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        mud_tools.register(registry, **resolved_mud)

    if block is not None:
        block(RunDSL(registry))

    logger = None
    try:
        if backend == "anthropic":
            be = backends.Anthropic(api_key=api_key, model=model)
        elif backend == "openai":
            be = backends.OpenAI(api_key=api_key, model=model)
        elif backend == "gemini":
            be = backends.Gemini(api_key=api_key, model=model)
        elif backend == "ollama":
            be = backends.Ollama(host=ollama_host, model=model)
        elif backend == "ollama_cloud":
            be = backends.OllamaCloud(api_key=api_key, model=model)
        else:
            raise ValueError(
                f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
            )

        builder = PromptBuilder(ctx, be)
        client = Client(builder)
        effective_max_iterations = task_class.max_iterations(task_settings)
        effective_max_output_tokens = (
            max_output_tokens if max_output_tokens is not None else task_class.max_output_tokens(task_settings)
        )
        logger = Logger(
            log=log,
            snapshot={
                "task": task_class.task_name,
                "max_iterations": effective_max_iterations,
                "max_output_tokens": effective_max_output_tokens,
                "model": model,
                "provider": backend,
            },
        )

        try:
            Repl(
                context=ctx,
                registry=registry,
                builder=builder,
                client=client,
                logger=logger,
                task_settings=task_settings,
                max_iterations=effective_max_iterations,
                max_output_tokens=effective_max_output_tokens,
                config_dir=cfg.dir,
                provider=backend,
                model=model,
                version=VERSION,
                api_key=api_key,
                mud=resolved_mud,
            ).start()
        except KeyboardInterrupt:
            print("\nInterrupted.")
    finally:
        if logger is not None:
            logger.close()


__all__ = [
    "Config",
    "PROMPTS_DIR",
    "Player",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "RunDSL",
    "Repl",
    "VERSION",
    "run",
    "repl",
    "backends",
    "state",
    "config",
    "set_quiet",
    "set_loud",
    "is_quiet",
    "set_debug",
    "is_debug",
    "file_system",
    "shell",
    "mud_tools",
]
