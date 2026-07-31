from __future__ import annotations

import threading

from opentelemetry import trace

from .errors import ApiError, TurnInterrupted
from .logger import Logger
from .tracing import tracer

# Default iteration ceiling. The *enforced* value comes from the
# max_iterations constructor arg (sourced from Config at the run/repl path),
# which falls back to this constant. 0 (or None) disables the ceiling.
MAX_ITERATIONS = 25

# The wind-down call is deliberately short and cheap.
WRAP_UP_OUTPUT_TOKENS = 400
WRAP_UP_DIRECTIVE = (
    "You have reached your action limit for this turn. Do not call any more tools.\n"
    "Briefly summarize what you accomplished, what is still unfinished, and the\n"
    "single next action you would take."
).strip()


class Agent:
    def __init__(
        self,
        *,
        context,
        registry,
        builder,
        client,
        logger: Logger | None = None,
        max_iterations: int | None = None,
        max_turn_tokens: int | None = None,
        max_output_tokens: int | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        # NOT `logger: Logger = Logger()` — a Python default argument value is
        # evaluated once at function-definition time, not per call, which
        # would give every Agent that omits logger= the *same* Logger
        # instance (and session file). Constructing it here instead gives
        # each Agent its own.
        self.logger = logger if logger is not None else Logger()
        # No more task_settings resolution (Tasks::Base/Player are gone this
        # step) — every limit is now a plain constructor arg the caller
        # (boukensha.run()/repl()) resolves from Config up front.
        self.max_iterations = int(max_iterations) if max_iterations is not None else MAX_ITERATIONS
        self.max_turn_tokens = int(max_turn_tokens or 0)  # 0 = disabled
        self.max_output_tokens = max_output_tokens
        # Not in the Ruby reference — see errors.TurnInterrupted. Optional and
        # None by default, so every non-Tui usage is unaffected.
        self.cancel_event = cancel_event
        self.iteration = 0

    def run(self) -> str:
        self.context.reset_turn_tokens()
        self._compact_if_needed()

        # One span per turn (a repl round-trip from user input to the agent's
        # reply), parenting every iteration/tool/LLM-call span below it — this
        # is the unit a trace viewer should let you expand to see the whole
        # decision path for a single player action.
        with tracer.start_as_current_span("agent.turn"):
            while True:
                # Cooperative cancellation (Tui's Esc key): checked at the top of
                # every iteration, before starting the next round-trip. Not
                # instant mid-request — an in-flight HTTP call still completes —
                # but Python has no safe way to do better than that from outside
                # a running thread.
                if self.cancel_event is not None and self.cancel_event.is_set():
                    raise TurnInterrupted("turn cancelled")

                # Two independent ceilings; stop at whichever trips first. Limits
                # are *trigger thresholds*, not hard caps: when one is reached we
                # stop starting new work iterations and make exactly one terminal
                # wind-down call (counted in tokens, but not as another iteration).
                if self._iteration_limit_reached():
                    self.logger.limit_reached(kind="max_iterations", n=self.iteration, max=self.max_iterations)
                    return self._wrap_up("max_iterations")
                if self._token_limit_reached():
                    self.logger.limit_reached(kind="max_tokens", n=self.context.turn_tokens, max=self.max_turn_tokens)
                    return self._wrap_up("max_tokens")

                self.iteration += 1
                with tracer.start_as_current_span(
                    "agent.iteration", attributes={"iteration": self.iteration}
                ):
                    self.logger.iteration(n=self.iteration, max=self.max_iterations)
                    self.logger.prompt(
                        messages=self.context.messages, tools=self.context.tools, context_window=self.context.context_window
                    )

                    response = self.client.call(**self._call_opts())
                    self.logger.raw(data=response)
                    parsed = self.builder.parse_response(response)
                    self._record_usage(response)
                    self._log_reasoning(parsed["content"])

                    if parsed["stop_reason"] == "tool_use":
                        self._handle_tool_calls(parsed["content"], response)
                    else:
                        text = self._extract_text(parsed["content"])
                        self.logger.response(text=text, usage=response.get("usage"), stop_reason=parsed["stop_reason"])
                        self.logger.turn_end(reason="completed", iterations=self.iteration, tokens=self.context.turn_tokens)
                        self.context.add_message("assistant", text)
                        return text

    # ---------- private ---------------------------------------------------

    def _iteration_limit_reached(self) -> bool:
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _token_limit_reached(self) -> bool:
        return self.max_turn_tokens > 0 and self.context.turn_tokens >= self.max_turn_tokens

    def _call_opts(self) -> dict:
        # Ruby's truthiness check is really a nil-check here (max_output_tokens
        # is always an int or nil, never false), so `is not None` is the exact
        # equivalent — a plain truthy check would wrongly drop an explicit 0.
        return {"max_output_tokens": self.max_output_tokens} if self.max_output_tokens is not None else {}

    def _record_usage(self, response: dict) -> None:
        """Add this call's input+output to the cumulative turn total (the
        spend budget) and refresh the known context size from input_tokens
        (compaction pressure — a replacement, not an addition: any given
        response's input_tokens already reflects the whole replayed history)."""
        usage = response.get("usage") or {}
        self.context.add_turn_tokens(usage.get("input_tokens"), usage.get("output_tokens"))
        self.context.update_tokens(usage.get("input_tokens") or 0)

    def _compact_if_needed(self) -> None:
        if not self.context.needs_compaction():
            return
        before = self.context.current_tokens
        dropped = self.context.compact_messages()
        self.logger.compaction(before=before, dropped=dropped, context_window=self.context.context_window)

    def _wrap_up(self, reason: str) -> str:
        """One final, tools-disabled model call so the agent ends the turn in
        character rather than aborting. Runs *outside* the counted loop: it
        never re-checks the limits (so it cannot re-trigger) and does not
        increment self.iteration, though its tokens still count toward the
        reported turn total. Falls back to a deterministic message if the
        call fails."""
        self.context.add_message("user", WRAP_UP_DIRECTIVE)
        try:
            response = self.client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
            parsed_wrap = self.builder.parse_response(response)
            text = self._extract_text(parsed_wrap["content"])
            if not text.strip():
                text = self._fallback_message(reason)
            self._record_usage(response)
            self.logger.response(text=text, usage=response.get("usage"), stop_reason=parsed_wrap["stop_reason"])
            self.logger.turn_end(reason=reason, iterations=self.iteration, tokens=self.context.turn_tokens)
            self.context.add_message("assistant", text)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self.logger.turn_end(reason=reason, iterations=self.iteration, tokens=self.context.turn_tokens)
            self.context.add_message("assistant", msg)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content) -> str:
        # "\n" join, not "" — a real behavior change from every step through
        # 11 (confirmed by diff, not assumed): multi-block text responses are
        # now newline-separated instead of concatenated directly.
        return "\n".join(b["text"] for b in content if b.get("type") == "text")

    def _log_reasoning(self, content) -> None:
        """Emit one `reasoning` event per reasoning block so the viewer can
        show the model's thinking as a first-class step. Empty, non-redacted
        blocks are skipped to avoid noise (a redacted/omitted block still
        renders, since it tells the viewer "the model thought here")."""
        for block in content:
            if block.get("type") != "reasoning":
                continue
            redacted = block.get("redacted") is True
            text = str(block.get("text") or "")
            if not text.strip() and not redacted:
                continue
            self.logger.reasoning(text=text, redacted=redacted)

    def _handle_tool_calls(self, content, response) -> None:
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        # Log any preamble text that accompanied the tool call (carries no
        # usage — the placeholder below owns the turn's usage chip), then the
        # placeholder.
        preamble = self._extract_text(content)
        if preamble.strip():
            self.logger.plan(text=preamble)
        suffix = "" if len(tool_calls) == 1 else "s"
        self.logger.response(
            text=f"(tool use — {len(tool_calls)} call{suffix})", usage=response.get("usage"), stop_reason="tool_use"
        )

        self.context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            self.logger.tool_call(name=name, args=args)
            with tracer.start_as_current_span(f"tool.{name}", attributes={"tool.name": name}) as span:
                try:
                    result = self.registry.dispatch(name, args)
                    self.logger.tool_result(name=name, result=result, ok=True)
                except Exception as e:
                    result = f"ERROR: {type(e).__name__}: {e}"
                    self.logger.tool_result(name=name, result=result, ok=False, error=str(e))
                    # Caught here (a bad tool call shouldn't kill the turn), so
                    # the span needs to be told explicitly — a swallowed
                    # exception never reaches start_as_current_span's own
                    # exception handling since nothing propagates out of this
                    # `with` block.
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

            self.context.add_message("tool_result", str(result), tool_use_id=use_id)
