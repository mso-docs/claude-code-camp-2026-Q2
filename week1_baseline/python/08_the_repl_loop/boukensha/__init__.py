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
from .version import VERSION

_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
    # "ollama" deliberately absent: local Ollama needs no API key.
}


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
    block: Callable[[RunDSL], None] | None = None,
) -> str:
    """One-shot run: send a single task, get a response, return.
    See boukensha.repl for the interactive equivalent."""
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

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

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
    block: Callable[[RunDSL], None] | None = None,
) -> None:
    """Interactive REPL: register tools once, then loop — reading tasks from
    stdin, running the agent, and printing replies — until the user types
    /exit or sends EOF.

    Conversation history accumulates across every turn so the agent always
    sees the full transcript.

    Options are the same as boukensha.run, minus `task` (the user supplies
    tasks interactively). system/model/backend/api_key all default to
    config values.

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

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

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
]
