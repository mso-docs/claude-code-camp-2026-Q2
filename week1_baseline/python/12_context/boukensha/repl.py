from __future__ import annotations

import socket
import sys
from pathlib import Path

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
      /help     print the command list
      /clear    wipe conversation history (tools stay registered)
      /compact  manually drop the oldest messages to free up context space
      /exit     leave the REPL
      /quit     alias for /exit

    No longer hard-codes stdout/stdin — on_output(), handle_command(), and
    run_turn() are public so a front end (Tui) can drive it instead.
    """

    PROMPT = "boukensha> "

    HELP = (
        "Commands:\n"
        "  /clear    wipe conversation history (tools stay)\n"
        "  /compact  drop the oldest messages to free up context space\n"
        "  /exit     leave the REPL\n"
        "  /help     show this message"
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
        mud=None,
        max_iterations=None,
        max_turn_tokens=None,
        max_output_tokens=None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.max_iterations = max_iterations
        self.max_turn_tokens = max_turn_tokens
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.mud = mud
        self.turn = 0
        self._output_cb = None

    def on_output(self, callback) -> None:
        """Register a callback that receives every string the REPL would
        otherwise print to stdout. When set, print() is suppressed entirely
        and all output is routed through the callback instead. Used by Tui."""
        self._output_cb = callback

    def banner(self) -> str:
        key_status = "✓ API key set" if self.api_key and self.api_key.strip() else "✗ API key not set"
        provider_line = f"{self.provider or 'default'} ({self.model or 'default'})  {key_status}"
        config_exists = bool(self.config_dir) and Path(self.config_dir).is_dir()
        config_line = (
            str(self.config_dir) if config_exists else f"{self.config_dir or '(default)'}  ✗ directory not found"
        )
        ver = self.version or "?.?.?"
        pad = " " * (9 - len(ver))
        mud_stat = self._mud_status_string()

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){pad}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            f"  mud:       {mud_stat}\n"
            "\n"
            "  /clear           reset conversation history\n"
            "  /compact         drop oldest messages to free up context space\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def handle_command(self, input_text: str) -> str | None:
        """Handle a slash command. Returns "quit", "command", or None (not a
        command). Output is routed through the registered on_output callback
        if present."""
        if input_text in ("/exit", "/quit"):
            self._output("Goodbye.")
            return "quit"
        elif input_text == "/help":
            self._output(self.HELP)
            return "command"
        elif input_text == "/clear":
            self.context.clear_messages()
            self.turn = 0
            self._output("(conversation history cleared)")
            return "command"
        elif input_text == "/compact":
            dropped = self.context.compact_messages()
            self._output(f"(compacted context — {dropped} messages dropped)")
            return "command"
        return None

    def run_turn(self, input_text: str, *, cancel_event=None) -> None:
        self.turn += 1
        self.logger.turn(n=self.turn)

        self.context.add_message("user", input_text)

        # A fresh Agent every turn (so its iteration counter starts at 0),
        # sharing the same context/registry/builder/client/logger — that
        # sharing is what actually carries history and tools across turns.
        # cancel_event: not in the Ruby reference (see errors.TurnInterrupted)
        # — Tui passes one so Esc can cooperatively cancel; the plain Repl
        # never does, so this is a no-op for every use before this step.
        agent = Agent(
            context=self.context,
            registry=self.registry,
            builder=self.builder,
            client=self.client,
            logger=self.logger,
            max_iterations=self.max_iterations,
            max_turn_tokens=self.max_turn_tokens,
            max_output_tokens=self.max_output_tokens,
            cancel_event=cancel_event,
        )
        try:
            result = agent.run()
        except LoopError as e:
            self._output(f"\n[error] {e}")
            return
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")
            return

        self._output("")
        self._output(result)

    def start(self) -> None:
        self._output(self.banner())

        while True:
            if not self._output_cb:
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

            result = self.handle_command(text)
            if result == "quit":
                break
            if result:
                continue

            self.run_turn(text)

    # ---------- private -----------------------------------------------

    def _output(self, s: str) -> None:
        if self._output_cb:
            self._output_cb(str(s))
        else:
            print(s)

    def _mud_status_string(self) -> str:
        """Build the mud status string shown in the banner. Only checks TCP
        reachability — the tool session auto-connects at startup (in
        tools.mud.register), so probing login here would cause a double-login."""
        if not self.mud:
            return "(not configured)"

        host = self.mud.get("host") or "localhost"
        port = self.mud.get("port") or 4000
        name = self.mud.get("name")

        return f"{host}:{port}  {self._probe_mud(host, port, name)}"

    @staticmethod
    def _probe_mud(host, port, name) -> str:
        # TCP reachability only — the tool session auto-connects at startup,
        # so we don't probe login here (that would cause a double-login on boot).
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except OSError:
            return "✗ not reachable"

        return "(Reachable)" if name and str(name).strip() else "(Reachable, no credentials)"
