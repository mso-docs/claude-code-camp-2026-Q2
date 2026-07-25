# 11 · A Terminal UI (Python port)

Python port of [`ruby/11_tui`](../../ruby/11_tui). `boukensha.repl(tui=True)`
(the default) wraps `Repl` in a four-zone terminal UI — scrollable
conversation, live progress line, input box, always-on status bar —
instead of the plain print/stdin REPL. `tui=False` or `--no-tui` falls
back to the plain REPL.

This is a real architectural translation, not a mechanical port. Ruby's
`Tui` is built on `bubbletea` (Go's Elm-architecture TUI framework, via a
Ruby FFI gem with actual C-level patches in this repo — see
`ruby/11_tui/patches/bubbletea/`) — a synchronous Model/Update/View loop
driven by an explicit message queue. This port uses
[`textual`](https://textual.textualize.io/) (asyncio-based, widget/CSS-driven).

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/tui.py` | `Tui` — new, the architectural translation |
| `boukensha/repl.py` | composability refactor: `on_output`/`handle_command`/`run_turn`/`banner` all public; `/quiet`/`/loud` **removed** |
| `boukensha/agent.py` | **new to the port, not in Ruby**: optional cooperative `cancel_event` |
| `boukensha/errors.py` | adds `TurnInterrupted` |
| `boukensha/state.py` | `set_quiet`/`set_loud`/`is_quiet` **removed** |
| `boukensha/__init__.py` | `repl()` gains `tui=True` |
| `boukensha_loader.py` | `--no-tui` flag; legacy `MUD_NAME`/`MUD_HOST`/`MUD_PORT`/`MUD_PASSWORD` env vars |

`logger.py`, `context.py`, `errors.py` (aside from the addition),
`client.py`, `config.py` all have zero diff from step 10's Ruby reference.
`Logger.subscribe` already existed in this port since step 07 — the Ruby
README credits this step with adding it, which is inaccurate.

## Decisions made with you before implementation

- **Esc-interrupt uses cooperative cancellation, not a forced thread
  kill.** Ruby's `@turn_thread.raise(Interrupt)` forcibly injects an
  exception into a running thread — Python's standard library has no safe
  equivalent. `Agent` gained an optional `cancel_event: threading.Event`,
  checked at the top of every loop iteration (before each model
  round-trip). Esc sets the event; the turn stops at the next iteration
  boundary — an in-flight HTTP call still completes. Verified directly:
  a fake client looping tool calls, cancelled mid-turn, confirmed to stop
  and never call again afterward.
- **Full fidelity**: all four zones, all 6 keyboard shortcuts.

## A real, deliberate removal — not drift

`/quiet`/`/loud` are genuinely gone in this step: dropped from `repl.rb`'s
command handling *and* `boukensha.rb`'s `quiet!`/`loud!`/`quiet?`/`@quiet`
state, consistently, in the same diff — unlike the `mud_*`/`LoopError`
flip-flopping in earlier steps (snapshot inconsistency) or the step 09
client/config regression (unexplained, contradicted by that step's stated
scope). Removed from `state.py` and `__init__.py`'s exports to match.

## Two real bugs found only by writing real tests

**Rich markup vs. literal bracket text.** The conversation `RichLog` was
initially created with `markup=True`. Ruby's conversation strings include
literal text like `"[interrupted]"` and `"[error] ..."` — under Rich
markup parsing, `[interrupted]` looks like an unmatched style tag and gets
silently swallowed instead of displayed. A first test run showed the Esc
key correctly stopping the turn but the `"[interrupted]"` message missing
entirely from the conversation. Fixed with `markup=False` on the
`RichLog` (conversation content should never be markup-interpreted) and
`rich.markup.escape()` at the render boundary for the progress/status
`Static` widgets, which also build strings containing literal brackets
(`"[ready]"`) or user-controlled values (model name, version) that could
theoretically contain them.

**Ruby's progress line shows a hardcoded constant, not the real ceiling.**
`render_progress` in Ruby uses `Agent::MAX_ITERATIONS` (the class
constant, always 25) rather than the REPL's actual configured
`max_iterations` — so if a task overrides it in `settings.yaml`, Ruby's
progress line still displays "25", not the real value. This port
deliberately uses `self.repl.max_iterations` (the value actually resolved
and passed through from `boukensha.repl()`) instead, showing the correct
ceiling. A conscious fix, not an oversight — documented inline in
`tui.py` in case it looks like a discrepancy against the Ruby source.

## Notable differences from the Ruby version

- **`textual`'s `run_worker(thread=True)`** is the direct equivalent of
  Ruby's `Thread.new { @repl.run_turn(input) }` — our HTTP calls are all
  blocking, so a turn genuinely needs an OS thread, not a coroutine that
  would freeze the UI.
- **The event queue design mirrors Ruby's architecture directly**, not
  just the concept: a `queue.Queue` fed by `Logger.subscribe` (thread-safe
  `put()` from the worker thread), drained on a periodic tick
  (`set_interval`) rather than pushed immediately via `call_from_thread` —
  matching Ruby's own poll-a-`Queue`-every-`TickMsg` design, including the
  same "the progress line updates in discrete ticks, not instantly per
  event" feel.
- **Layout is a custom four-zone `Vertical`/`Horizontal` composition**
  with Textual CSS handling sizing (`1fr` for the viewport, fixed heights
  elsewhere) in place of Ruby's manual `[@height - 5, 5].max` arithmetic
  against `WindowSizeMessage`.
- **`fmt_tokens`'s `1000 → "1.0k"` rule ported exactly** (as `_fmt_tokens`).

## Verification

A real terminal UI can't be smoke-tested the way `Repl.start()` was
(scripted `io.StringIO` stdin) — used Textual's official headless testing
harness (`App.run_test()` / `Pilot`) instead.

- `Repl`'s composability refactor in isolation: `on_output` reroutes
  output, `handle_command` returns the right sentinel for each command
  (confirming `/quiet`/`/loud` are no longer recognized), `banner()` is
  public.
- `Agent`'s `cancel_event`: a multi-iteration fake-client run, cancelled
  mid-turn from a background thread — confirmed `TurnInterrupted` raises
  after the in-flight call count stabilizes, and an `Agent` without
  `cancel_event` behaves exactly as every prior step.
- Drove the real `Tui` app: typed input + Enter triggers a turn and shows
  the reply; `/clear` (typed) and `ctrl+l` (binding) both reset turn count
  and history; `pageup`/`pagedown` scroll the conversation viewport;
  `ctrl+c` and `ctrl+d` both quit; `escape` during an in-flight fake turn
  interrupts it and shows `[interrupted]`, with no further client calls
  afterward.
- The progress line through idle → active → idle, including the
  intermediate "Calling tool: X" action text and the final turn-count
  update — this is what caught the Rich-markup bug.
- `boukensha_loader.py`'s `--no-tui` and legacy `MUD_*` env var logic
  tested in isolation (stubbing the imported `boukensha` module) — the
  `tui=` resolution, the built `mud=` dict with correct defaults, and the
  `MUD_NAME`-without-`MUD_PASSWORD` abort path.
- Re-ran the carried-forward `examples/demo.py` end-to-end against a
  scratch `settings.yaml` with a fake key — same live `api.anthropic.com`
  401 boundary as every step since 05, confirming `run()` (which never
  touches `Repl`/`Tui`) is unaffected by any of this step's changes.

## Run

```bash
uv sync
../bin/11_tui           # launches the textual TUI
../bin/11_tui --no-tui  # plain REPL, no textual dependency exercised
```
