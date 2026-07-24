from __future__ import annotations

import sys
from pathlib import Path

from . import state
from .agent import Agent
from .errors import ApiError, LoopError


class Repl:
    """The interactive session loop.

    Wraps the same primitives as a single run() call, but instead of running
    once it stays alive: it reads a task from the user, runs the agent,
    prints the reply, and loops back to the prompt.

    The Context is shared across every turn so conversation history
    accumulates naturally — the agent sees the full transcript each time it
    is called.

    Built-in commands (not sent to the agent):
      /help    print the command list
      /quiet   suppress detailed logging
      /loud    re-enable logging
      /clear   wipe conversation history (tools stay registered)
      /exit    leave the REPL
      /quit    alias for /exit
    """

    PROMPT = "boukensha> "

    HELP = (
        "Commands:\n"
        "  /quiet   suppress logging output\n"
        "  /loud    re-enable logging output\n"
        "  /clear   wipe conversation history (tools stay)\n"
        "  /exit    leave the REPL\n"
        "  /help    show this message"
    )

    def __init__(
        self,
        *,
        context,
        registry,
        builder,
        client,
        logger,
        config_dir=None,
        provider=None,
        model=None,
        version=None,
        api_key=None,
        task_settings=None,
        max_iterations=None,
        max_output_tokens=None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.task_settings = task_settings
        self.max_iterations = max_iterations
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.turn = 0

    def start(self) -> None:
        print(self._banner())

        while True:
            print(self.PROMPT, end="")
            sys.stdout.flush()

            # Ruby's $stdin.gets returns nil on EOF; readline() returns ""
            # instead — a blank user-entered line is "\n", never "", so EOF
            # stays distinguishable from "user just pressed Enter" before
            # stripping.
            line = sys.stdin.readline()
            if not line:
                break  # EOF / Ctrl-D

            text = line.strip()
            if not text:
                continue

            if text in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif text == "/help":
                print(self.HELP)
                continue
            elif text == "/quiet":
                state.set_quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            elif text == "/loud":
                state.set_loud()
                print("(logging enabled)")
                continue
            elif text == "/clear":
                self.context.clear_messages()
                self.turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(text)

    # ---------- private -----------------------------------------------

    def _banner(self) -> str:
        key_status = "✓ API key set" if self.api_key and self.api_key.strip() else "✗ API key not set"
        provider_line = f"{self.provider or 'default'} ({self.model or 'default'})  {key_status}"
        config_exists = bool(self.config_dir) and Path(self.config_dir).is_dir()
        config_line = (
            str(self.config_dir) if config_exists else f"{self.config_dir or '(default)'}  ✗ directory not found"
        )
        ver = self.version or "?.?.?"
        pad = " " * (9 - len(ver))

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, input_text: str) -> None:
        self.turn += 1
        self.logger.turn(n=self.turn)

        self.context.add_message("user", input_text)

        # A fresh Agent every turn (so its iteration counter starts at 0),
        # sharing the same context/registry/builder/client/logger — that
        # sharing is what actually carries history and tools across turns.
        agent = Agent(
            context=self.context,
            registry=self.registry,
            builder=self.builder,
            client=self.client,
            logger=self.logger,
            task_settings=self.task_settings,
            max_iterations=self.max_iterations,
            max_output_tokens=self.max_output_tokens,
        )
        try:
            result = agent.run()
        except LoopError as e:
            print(f"\n[error] {e}")
            return
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
            return

        # Print the final response outside of the logger so it is always
        # visible, even when state.set_quiet() is active.
        print()
        print(result)
