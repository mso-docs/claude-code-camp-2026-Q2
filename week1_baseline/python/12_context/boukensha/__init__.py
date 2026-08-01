from __future__ import annotations

import os
from typing import Callable

from . import backends, models, state
from .agent import Agent
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .repl import Repl
from .run_dsl import RunDSL
from .state import config, is_debug, set_debug
from .tool import Tool
from . import tracing
# Aliased: run()/repl() have a `mud=` keyword parameter, which would shadow
# a bare `from .tools import mud` at call time. Ruby doesn't hit this
# (Tools::Mud, capitalized, is a different identifier from a local `mud`
# variable); Python has no such built-in distinction, so the import itself
# is renamed instead.
from .tools import file_system, shell
from .tools import mud as mud_tools
from .tui import Tui
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


def _make_backend(backend: str, *, api_key: str | None, model: str, ollama_host: str):
    if backend == "anthropic":
        return backends.Anthropic(api_key=api_key, model=model)
    if backend == "openai":
        return backends.OpenAI(api_key=api_key, model=model)
    if backend == "gemini":
        return backends.Gemini(api_key=api_key, model=model)
    if backend == "ollama":
        return backends.Ollama(host=ollama_host, model=model)
    if backend == "ollama_cloud":
        return backends.OllamaCloud(api_key=api_key, model=model)
    raise ValueError(f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'.")


def run(
    *,
    task: str,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str | None = None,
    log: str | None = None,
    max_output_tokens: int | None = None,
    context_window: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    block: Callable[[RunDSL], None] | None = None,
) -> str:
    """One-shot run: send a single task, get a response, return.
    See boukensha.repl for the interactive equivalent.

    No more Tasks::Base/Tasks::Player layer this step (see config.py) —
    system/model/backend/agent-limits are resolved straight off Config's flat
    methods instead of going through a per-task settings hash.

    context_window:    overrides the model's known context window (looked up
                       from models.py by default). Rarely needed — mainly for
                       testing against a model models.py doesn't know about.

    ollama_host:       base URL for the "ollama" backend (default
                       http://localhost:11434). None (default) resolves to
                       config.ollama_host, settable via settings.yaml's
                       ollama.host — not in the Ruby reference, added for
                       testing against a custom local server.

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
    tracing.configure()  # no-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set

    if system is None:
        system = cfg.system_prompt
    if model is None:
        model = cfg.model
    if backend is None:
        backend = cfg.provider_type
    if ollama_host is None:
        ollama_host = cfg.ollama_host
    if api_key is None:
        env_var = _API_KEY_ENV_VARS.get(backend)
        api_key = os.environ.get(env_var) if env_var else None
    if working_dir is None:
        working_dir = os.getcwd()
    if context_window is None:
        context_window = models.context_window(model)

    ctx = Context(
        system=system,
        context_window=context_window,
        working_dir=working_dir or None,
        compaction_threshold=cfg.agent_compaction_threshold,
    )
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
        be = _make_backend(backend, api_key=api_key, model=model, ollama_host=ollama_host)

        builder = PromptBuilder(ctx, be)
        client = Client(builder)
        effective_max_iterations = cfg.agent_max_iterations
        effective_max_turn_tokens = cfg.agent_max_turn_tokens
        effective_max_output_tokens = max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens
        logger = Logger(
            log=log,
            snapshot={
                "max_iterations": effective_max_iterations,
                "max_turn_tokens": effective_max_turn_tokens,
                "max_output_tokens": effective_max_output_tokens,
                "context_window": context_window,
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
            max_iterations=effective_max_iterations,
            max_turn_tokens=effective_max_turn_tokens,
            max_output_tokens=effective_max_output_tokens,
        )

        ctx.add_message("user", task)
        return agent.run()
    finally:
        if logger is not None:
            logger.close()


DEFAULT_REPROMPT_MESSAGE = (
    "You have not finished the task and ran out of actions for this turn. "
    "Continue working from where you left off."
).strip()


def run_reprompted(
    *,
    task: str,
    max_reprompts: int = 0,
    reprompt_message: str = DEFAULT_REPROMPT_MESSAGE,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str | None = None,
    log: str | None = None,
    max_output_tokens: int | None = None,
    context_window: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    block: Callable[[RunDSL], None] | None = None,
) -> list[dict]:
    """Like run(), but reprompts the agent when — and only when — it
    exhausts its iteration budget without voluntarily ending the turn.

    Setup here intentionally duplicates run()'s (see repl()'s own docstring
    for why this codebase does that rather than sharing a helper). What's
    different is the loop at the bottom: instead of one Agent.run() call,
    each pass builds a *fresh* Agent — same pattern repl.run_turn() already
    uses for every interactive turn, iteration counter reset to 0 while
    context/registry/client/logger (and so the live MUD session) persist —
    and reprompts up to max_reprompts times, stopping the first turn that
    doesn't hit its own iteration ceiling. A turn ending early because the
    model gave a final answer (finished or gave up on its own) is not
    reprompted — reprompting is only for "ran out of runway."

    Returns one dict per turn actually run (1 + however many reprompts were
    used, which may be fewer than max_reprompts): {"text", "hit_limit",
    "iterations", "max_iterations"}.
    """
    cfg = config()
    tracing.configure()

    if system is None:
        system = cfg.system_prompt
    if model is None:
        model = cfg.model
    if backend is None:
        backend = cfg.provider_type
    if ollama_host is None:
        ollama_host = cfg.ollama_host
    if api_key is None:
        env_var = _API_KEY_ENV_VARS.get(backend)
        api_key = os.environ.get(env_var) if env_var else None
    if working_dir is None:
        working_dir = os.getcwd()
    if context_window is None:
        context_window = models.context_window(model)

    ctx = Context(
        system=system,
        context_window=context_window,
        working_dir=working_dir or None,
        compaction_threshold=cfg.agent_compaction_threshold,
    )
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
    turns: list[dict] = []
    try:
        be = _make_backend(backend, api_key=api_key, model=model, ollama_host=ollama_host)

        builder = PromptBuilder(ctx, be)
        client = Client(builder)
        effective_max_iterations = cfg.agent_max_iterations
        effective_max_turn_tokens = cfg.agent_max_turn_tokens
        effective_max_output_tokens = max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens
        logger = Logger(
            log=log,
            snapshot={
                "max_iterations": effective_max_iterations,
                "max_turn_tokens": effective_max_turn_tokens,
                "max_output_tokens": effective_max_output_tokens,
                "context_window": context_window,
                "model": model,
                "provider": backend,
            },
        )

        ctx.add_message("user", task)
        attempt = 0
        while True:
            agent = Agent(
                context=ctx,
                registry=registry,
                builder=builder,
                client=client,
                logger=logger,
                max_iterations=effective_max_iterations,
                max_turn_tokens=effective_max_turn_tokens,
                max_output_tokens=effective_max_output_tokens,
            )
            text = agent.run()
            # Two independent ceilings can end a turn (agent.py's
            # _iteration_limit_reached/_token_limit_reached) — max_turn_tokens
            # routinely fires well under max_iterations (a MUD room/tool
            # result-heavy turn can burn 60k tokens in half the iteration
            # budget), so checking iteration count alone here missed most
            # real "ran out of runway" cases and under-reprompted. stop_reason
            # is the exact signal agent.py already computes for this.
            hit_limit = agent.stop_reason in ("max_iterations", "max_tokens")
            turns.append(
                {
                    "text": text,
                    "hit_limit": hit_limit,
                    "stop_reason": agent.stop_reason,
                    "iterations": agent.iteration,
                    "max_iterations": effective_max_iterations,
                }
            )
            if not hit_limit or attempt >= max_reprompts:
                return turns
            attempt += 1
            ctx.add_message("user", reprompt_message)
    finally:
        if logger is not None:
            logger.close()


def repl(
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str | None = None,
    log: str | None = None,
    max_output_tokens: int | None = None,
    context_window: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    tui: bool = True,
    block: Callable[[RunDSL], None] | None = None,
) -> None:
    """Interactive REPL — see boukensha.run for full option documentation.

    tui: True (default) wraps the REPL in a textual TUI (in place of
    Ruby's charm-ruby TUI). Pass tui=False or the --no-tui CLI flag to fall
    back to the plain terminal REPL.

    This setup logic intentionally duplicates run()'s rather than sharing a
    helper — that's how the Ruby reference does it too (self.run and
    self.repl are independent, copy-pasted method bodies), and refactoring
    it away would be a change this step's Ruby source didn't make.
    """
    cfg = config()  # loads .env; populates os.environ
    tracing.configure()  # no-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set

    if system is None:
        system = cfg.system_prompt
    if model is None:
        model = cfg.model
    if backend is None:
        backend = cfg.provider_type
    if ollama_host is None:
        ollama_host = cfg.ollama_host
    if api_key is None:
        env_var = _API_KEY_ENV_VARS.get(backend)
        api_key = os.environ.get(env_var) if env_var else None
    if working_dir is None:
        working_dir = os.getcwd()
    if context_window is None:
        context_window = models.context_window(model)

    ctx = Context(
        system=system,
        context_window=context_window,
        working_dir=working_dir or None,
        compaction_threshold=cfg.agent_compaction_threshold,
    )
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
        be = _make_backend(backend, api_key=api_key, model=model, ollama_host=ollama_host)

        builder = PromptBuilder(ctx, be)
        client = Client(builder)
        effective_max_iterations = cfg.agent_max_iterations
        effective_max_turn_tokens = cfg.agent_max_turn_tokens
        effective_max_output_tokens = max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens
        logger = Logger(
            log=log,
            snapshot={
                "max_iterations": effective_max_iterations,
                "max_turn_tokens": effective_max_turn_tokens,
                "max_output_tokens": effective_max_output_tokens,
                "context_window": context_window,
                "model": model,
                "provider": backend,
            },
        )

        repl_instance = Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            max_iterations=effective_max_iterations,
            max_turn_tokens=effective_max_turn_tokens,
            max_output_tokens=effective_max_output_tokens,
            config_dir=cfg.dir,
            provider=backend,
            model=model,
            version=VERSION,
            api_key=api_key,
            mud=resolved_mud,
        )

        try:
            if tui:
                Tui(repl_instance).run()
            else:
                repl_instance.start()
        except KeyboardInterrupt:
            print("\nInterrupted.")
    finally:
        if logger is not None:
            logger.close()


__all__ = [
    "Config",
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
    "Tui",
    "VERSION",
    "run",
    "repl",
    "backends",
    "models",
    "state",
    "tracing",
    "config",
    "set_debug",
    "is_debug",
    "file_system",
    "shell",
    "mud_tools",
]
