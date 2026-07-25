"""Tui wraps a Repl instance and replaces its raw print()/stdin I/O with a
structured four-zone display, built on textual (Python's terminal-UI
framework) in place of Ruby's bubbletea+lipgloss+bubbles (a Go-based Elm-
architecture TUI framework via a Ruby FFI gem).

The Repl continues to own session logic (turn counting, /commands, Agent
dispatch). Tui registers output/event callbacks on the Repl and drives a
textual App instead of bubbletea's synchronous Model/Update/View loop.

Layout (top → bottom):
  ┌──────────────────────────────────────────────┐
  │  conversation viewport (scrollable)           │
  ├──────────────────────────────────────────────┤
  │  ⟳ live progress line (hidden when idle)     │
  ├──────────────────────────────────────────────┤
  │  boukensha> input box                         │
  ├──────────────────────────────────────────────┤
  │  status line (always-on)                      │
  └──────────────────────────────────────────────┘
"""

from __future__ import annotations

import queue
import threading
import time

from rich.markup import escape
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

from .errors import TurnInterrupted
from .repl import Repl
from .version import VERSION

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
# input_timeout/tick equivalent: textual's own event loop already only wakes
# on real input or the interval timer, so there's no separate "idle poll
# rate" knob to tune here the way bubbletea's Runner(input_timeout:) needed.
TICK_SECONDS = 0.06

# Context-usage thresholds for progress-line color coding (percent of
# context_window consumed).
CTX_WARN_PCT = 70
CTX_ALERT_PCT = 85


def _fmt_tokens(n: int) -> str:
    n = int(n or 0)
    return f"{n / 1000.0:.1f}k" if n >= 1000 else str(n)


def _truncate(s: str, limit: int = 280) -> str:
    s = str(s or "").strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _fmt_args(args: dict) -> str:
    if not args:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


class Tui(App):
    """Wraps a Repl and drives it through a textual four-zone display."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #conversation {
        height: 1fr;
        border: none;
    }
    #progress {
        height: 1;
        padding: 0 1;
    }
    #input-row {
        height: 1;
    }
    #prompt {
        width: auto;
        color: $success;
        text-style: bold;
    }
    #input-box {
        border: none;
        background: transparent;
    }
    #status {
        height: 1;
        background: $panel;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+d", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear", "Clear", show=False),
        Binding("escape", "interrupt", "Interrupt", show=False),
        Binding("pageup", "scroll_up", "Scroll up", show=False),
        Binding("pagedown", "scroll_down", "Scroll down", show=False),
    ]

    def __init__(self, repl: Repl) -> None:
        super().__init__()
        self.repl = repl
        self.context = repl.context

        self._events: queue.Queue = queue.Queue()
        self._turn_count = 0
        self._cancel_event: threading.Event | None = None
        self._turn_running = False

        # Plain-text mirrors of the last-rendered progress/status content —
        # not needed by Textual itself, kept for tests to assert against
        # without reaching into Static's private internals.
        self._progress_text = ""
        self._status_text = ""

        self._live = self._idle_live()

    @staticmethod
    def _idle_live() -> dict:
        return {
            "active": False,
            "spinner_idx": 0,
            "start_time": None,
            "elapsed": 0.0,
            "current_action": "idle",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }

    # ---------- textual App interface --------------------------------------

    def compose(self) -> ComposeResult:
        # markup=False: conversation content is arbitrary agent/user/log text
        # (e.g. the literal strings "[interrupted]", "[error] ...") and must
        # never be interpreted as Rich markup — a literal "[interrupted]"
        # would otherwise be parsed as an unmatched style tag and silently
        # vanish. Only the progress/status Static widgets use markup.
        yield RichLog(id="conversation", wrap=True, markup=False)
        yield Static(id="progress")
        with Horizontal(id="input-row"):
            yield Static(Repl.PROMPT, id="prompt")
            yield Input(placeholder="Type a message…", id="input-box")
        yield Static(id="status")

    def on_mount(self) -> None:
        self.query_one("#conversation", RichLog).write(self.repl.banner())

        self.repl.on_output(self._on_repl_output)
        self.repl.logger.subscribe(self._events.put)

        self.set_interval(TICK_SECONDS, self._tick)
        self.query_one("#input-box", Input).focus()
        self._render_progress()
        self._render_status()

    def on_input_submitted(self, message: Input.Submitted) -> None:
        input_box = self.query_one("#input-box", Input)
        text = message.value.strip()
        input_box.value = ""
        if not text:
            return

        if text.startswith("/"):
            result = self.repl.handle_command(text)
            if result == "quit":
                self.exit()
            elif text == "/clear":
                self._turn_count = 0
                self._render_status()
            elif text == "/compact":
                self._render_progress()
                self._render_status()
        else:
            self.query_one("#conversation", RichLog).write(f"> {text}")
            self._launch_turn(text)

    # ---------- actions (keyboard shortcuts) --------------------------------

    def action_quit(self) -> None:
        self.exit()

    def action_clear(self) -> None:
        self.repl.handle_command("/clear")
        self._turn_count = 0
        self._render_status()

    def action_interrupt(self) -> None:
        if self._turn_running and self._cancel_event is not None:
            self._cancel_event.set()

    def action_scroll_up(self) -> None:
        self.query_one("#conversation", RichLog).scroll_relative(y=-5, animate=False)

    def action_scroll_down(self) -> None:
        self.query_one("#conversation", RichLog).scroll_relative(y=5, animate=False)

    # ---------- agent turn worker --------------------------------------------

    def _launch_turn(self, input_text: str) -> None:
        self._cancel_event = threading.Event()
        self._turn_running = True
        self._live = {
            **self._idle_live(),
            "active": True,
            "start_time": time.monotonic(),
            "current_action": "Thinking…",
        }
        self._render_progress()

        cancel_event = self._cancel_event
        self.run_worker(
            lambda: self._run_turn_worker(input_text, cancel_event), thread=True, exclusive=True
        )

    def _run_turn_worker(self, input_text: str, cancel_event: threading.Event) -> None:
        # Runs on a real OS thread (textual's thread-mode worker) — our HTTP
        # calls are all blocking, so this can't be a plain coroutine without
        # freezing the UI. Only self._events.put() (thread-safe) and plain
        # attribute/list mutation happen here; no widget is touched directly
        # from this thread — that's the tick callback's job, on the main loop.
        try:
            self.repl.run_turn(input_text, cancel_event=cancel_event)
        except TurnInterrupted:
            self._events.put({"phase": "turn_interrupted"})
        except Exception as e:  # noqa: BLE001 - mirrors Ruby's rescue => e
            self._events.put({"phase": "turn_error", "error": str(e)})
        finally:
            self._events.put({"phase": "turn_complete"})

    def _on_repl_output(self, text: str) -> None:
        # Called synchronously from run_turn — on the worker thread during a
        # turn, on the main thread during setup (e.g. the initial banner).
        # queue.Queue.put is thread-safe; the actual RichLog.write() happens
        # on the tick, on the main thread.
        self._events.put({"phase": "_output", "text": text})

    # ---------- tick: drain events, animate spinner, re-render -------------

    def _tick(self) -> None:
        self._drain_events()
        if self._live["active"]:
            self._live["spinner_idx"] = (self._live["spinner_idx"] + 1) % len(SPINNER_FRAMES)
            if self._live["start_time"] is not None:
                self._live["elapsed"] = time.monotonic() - self._live["start_time"]
        self._render_progress()
        self._render_status()

    def _drain_events(self) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)

    def _handle_event(self, event: dict) -> None:
        phase = str(event.get("phase", ""))

        if phase == "_output":
            self.query_one("#conversation", RichLog).write(event["text"])

        elif phase == "iteration":
            self._live["iteration"] = int(event.get("n") or 0)
            self._live["current_action"] = "Thinking…"

        elif phase == "plan":
            text = _truncate(event.get("text"), 500)
            if text:
                self.query_one("#conversation", RichLog).write(text)

        elif phase == "reasoning":
            if event.get("redacted"):
                line = Text("  ⋯ (reasoning redacted)", style="dim italic")
            else:
                text = _truncate(event.get("text"), 300)
                if not text:
                    return
                line = Text(f"  ⋯ {text}", style="dim italic")
            self.query_one("#conversation", RichLog).write(line)

        elif phase == "tool_call":
            name = event.get("name")
            self._live["current_action"] = f"Calling tool: {name}"
            self._live["tool_call_count"] += 1
            args = _fmt_args(event.get("args") or {})
            line = Text(f"  → {name}({args})", style="dim cyan")
            self.query_one("#conversation", RichLog).write(line)

        elif phase == "tool_result":
            self._live["current_action"] = "Awaiting result…"
            ok = event.get("ok", True)
            result = _truncate(event.get("result"), 280)
            style = "dim" if ok else "bold red"
            line = Text(f"  ← {result}", style=style)
            self.query_one("#conversation", RichLog).write(line)

        elif phase == "response":
            usage = event.get("usage")
            if usage:
                self._live["turn_input_tokens"] += int(usage.get("input_tokens") or 0)
                self._live["turn_output_tokens"] += int(usage.get("output_tokens") or 0)

        elif phase == "compaction":
            dropped = event.get("dropped")
            self.query_one("#conversation", RichLog).write(
                f"[context compacted — {dropped} messages dropped to free space]"
            )

        elif phase == "turn_complete":
            self._live["active"] = False
            self._turn_count += 1
            self._turn_running = False
            self._cancel_event = None

        elif phase == "turn_interrupted":
            self.query_one("#conversation", RichLog).write("[interrupted]")

        elif phase == "turn_error":
            self._live["active"] = False
            self.query_one("#conversation", RichLog).write(f"[error] {event.get('error')}")

    # ---------- rendering ---------------------------------------------------

    def _render_progress(self) -> None:
        progress = self.query_one("#progress", Static)
        if self._live["active"]:
            frame = SPINNER_FRAMES[self._live["spinner_idx"]]
            action = self._live["current_action"]
            iteration = self._live["iteration"]
            # Deliberately NOT Ruby's `Agent::MAX_ITERATIONS` (the class
            # constant, always 25) — Ruby's progress line shows that hardcoded
            # default even when a task overrides max_iterations in
            # settings.yaml, a latent display bug there. self.repl.max_iterations
            # is the actual configured value (resolved once in boukensha.repl()
            # before Repl is built), so this shows the real ceiling instead.
            max_iter = self.repl.max_iterations
            secs = int(self._live["elapsed"])
            itok = _fmt_tokens(self._live["turn_input_tokens"])
            otok = _fmt_tokens(self._live["turn_output_tokens"])
            calls = self._live["tool_call_count"]
            text = (
                f"{frame} {action}  "
                f"(iter {iteration}/{max_iter} · {secs}s · ↑ {itok} · ↓ {otok} · {calls} calls)"
            )
            self._progress_text = text
            # action can contain a tool name with arbitrary characters
            # (including brackets) — escape() only at the render boundary, so
            # self._progress_text keeps the plain semantic text (what tests
            # assert against) while the widget gets the Rich-safe form.
            progress.update(f"[cyan]{escape(text)}[/cyan]")
        else:
            pct = self.context.usage_pct
            color = self._ctx_color(pct)
            used = _fmt_tokens(self.context.current_tokens)
            maxt = _fmt_tokens(self.context.context_window)
            text = f"  [ready]   ctx {used} / {maxt} ({pct}%)   {self._turn_count} turns"
            self._progress_text = text
            # "[ready]" is literal text, not a markup tag — escaped only at
            # the render boundary, same reasoning as above.
            progress.update(f"[{color}]{escape(text)}[/{color}]")

    def _render_status(self) -> None:
        status = self.query_one("#status", Static)
        ver = self.repl.version or VERSION
        model = self.repl.model or "(model)"
        pct = self.context.usage_pct
        used = _fmt_tokens(self.context.current_tokens)
        maxt = _fmt_tokens(self.context.context_window)
        ctx_indicator = " ⚠ " if pct >= CTX_ALERT_PCT else " "
        tools = self.context.tool_count
        clock = time.strftime("%H:%M:%S")
        text = f" boukensha v{ver} · {model}  ·  ctx {used}/{maxt} ({pct}%){ctx_indicator}·  {tools} tools  ·  {clock} "
        self._status_text = text
        # ver/model come from user config (settings.yaml) — escaped only at
        # the render boundary, same reasoning as _render_progress, in case
        # either ever contains a literal bracket.
        status.update(escape(text))

    @staticmethod
    def _ctx_color(pct: float) -> str:
        if pct >= CTX_ALERT_PCT:
            return "red"
        if pct >= CTX_WARN_PCT:
            return "yellow"
        return "bright_black"
