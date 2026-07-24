# Step 11 · A Terminal UI

**Ruby reference:** `week1_baseline/ruby/11_tui/`
**Python port:** `week1_baseline/python/11_tui/`
**Status:** Planned

## Goal

A four-zone terminal UI (scrollable conversation, live progress line,
input box, always-on status bar) wrapping the same `Repl` every prior step
built — `Repl` keeps owning session logic (turns, slash commands, `Agent`
dispatch); the UI layer only replaces its I/O. `boukensha.repl(tui=True)`
(default) launches it; `tui=False` or `--no-tui` falls back to the plain
REPL.

This is a real architectural translation, not a mechanical port. Ruby's
`Tui` is built on `bubbletea` (Go's Elm-architecture TUI framework, via a
Ruby FFI gem with actual C-level patches in this repo) — a synchronous
Model/Update/View loop driven by an explicit message queue. Python's
`textual` (confirmed installable in this sandbox) is asyncio-based and
widget/CSS-driven. Same visual result, different runtime model underneath.

## Decisions already made with you

- **Esc-interrupt: cooperative cancellation, not a forced thread kill.**
  Ruby's `@turn_thread.raise(Interrupt)` forcibly injects an exception into
  a running thread — Python's standard library has no safe equivalent.
  `Agent` gains an optional `cancel_event: threading.Event | None`,
  checked at the top of each loop iteration (before every model
  round-trip). Esc sets the event; the turn stops at the next iteration
  boundary, not instantly mid-request. A currently-in-flight HTTP call
  still runs to completion — being upfront about what Python threading can
  actually guarantee here, rather than reaching for `ctypes`-level thread
  manipulation to fake Ruby's behavior.
- **Full fidelity**: all four zones, the spinner/progress line driven by
  `Logger.subscribe`, the status bar, and all 6 keyboard shortcuts.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/tui.rb` (`Tui`) | `boukensha/tui.py` | the big one — architectural translation, not 1:1 |
| `lib/boukensha/repl.rb` (composability refactor) | `boukensha/repl.py` | `on_output`, `handle_command`, `run_turn` become public; `banner` becomes public; `/quiet`/`/loud` **removed** |
| `lib/boukensha.rb` (`repl()` gains `tui:`) | `boukensha/__init__.py` | dispatch to `Tui` vs plain `Repl` |
| `lib/boukensha_loader.rb` (`--no-tui`, legacy `MUD_*` env vars) | `boukensha_loader.py` | two new behaviors |
| `lib/boukensha/agent.rb` | `boukensha/agent.py` | **new to the port, not Ruby**: optional cooperative `cancel_event` — see above |

`logger.py`, `context.py`, `errors.py`, `client.py`, `config.py` all have
**zero diff** from step 10 (confirmed by direct diff) — carried forward
unchanged. Notably `Logger.subscribe` already existed since step 07 in
this port; the Ruby README credits this step with adding it, which is
inaccurate — another README claim not to trust at face value, consistent
with what we've found in every step since 06.

## A real, deliberate removal — not drift this time

`/quiet` and `/loud` are genuinely gone in this step: dropped from
`repl.rb`'s command handling *and* `boukensha.rb`'s `quiet!`/`loud!`/
`quiet?`/`@quiet` state entirely, consistently, in the same diff. Unlike
the `mud_*`/`LoopError` flip-flopping in steps 05–07 (snapshot
inconsistency) or the client/config regression in step 09 (unexplained,
contradicted by the step's own stated scope), this one reads as an
intentional cleanup — plausibly because the TUI makes the old "verbose
JSONL scroll on your terminal" problem `/quiet` was solving moot (the TUI
never printed raw log output to begin with; the plain `Repl` didn't either
since step 06). Removing `set_quiet`/`set_loud`/`is_quiet` from
`state.py` and their `__init__.py` exports to match.

## Design decisions — the `Tui` translation

**Textual's `App.run_worker(thread=True)` is the direct equivalent of
Ruby's `Thread.new { @repl.run_turn(input) }`.** Our HTTP calls are all
blocking (`urllib`), so a turn genuinely needs an OS thread, not a
coroutine that would block the event loop — Textual's thread-mode worker
is built exactly for this, with lifecycle tracking Ruby's raw `Thread`
object lacks.

**The event queue design carries over almost exactly, not just the
concept.** Ruby polls a `Queue` fed by `Logger#subscribe` on every
`TickMsg` (60ms). Rather than reach for Textual's `call_from_thread`
(push events onto the UI thread immediately), this port keeps the same
`queue.Queue` + periodic-drain shape via `set_interval` — closer to what
Ruby actually does, and it means the progress line updates in
discrete ticks rather than instantly per event, matching the reference
UI's actual feel (a deliberate choice, not a limitation).

**Layout: a custom four-zone `Vertical` composition**, not a pre-built
Textual layout — `RichLog` (or a scrollable `Static`) for the
conversation viewport, a `Static` for the live progress line, an `Input`
for the input box, a `Static` for the status bar. Textual's CSS handles
sizing (`1fr` for the viewport, fixed heights for the other three) in
place of Ruby's manual `viewport_height = [@height - 5, 5].max` arithmetic
against `WindowSizeMessage`.

**Keyboard shortcuts map onto Textual's `BINDINGS`**, with one exception:
Textual's `Input` widget already owns most keystroke handling (text entry,
cursor movement) the way Ruby's `Bubbles::TextArea` does — bindings are
declared at the `App`/screen level for the 6 shortcuts that aren't plain
text entry (`enter` submit is `Input`'s own submit event, not a binding).

**Spinner + elapsed time + token counts**: same data, same formatting
(`fmt_tokens`'s `1000 → "1.0k"` rule ported exactly), driven by the same
periodic tick updating a reactive attribute that triggers a re-render of
just the progress `Static`, not the whole screen — Textual's reactive
system does the "only redraw what changed" work Ruby's `@dirty` flag +
manual `sync_viewport` does by hand.

## Design decisions — wiring

**`boukensha_loader.py` gains two behaviors**: `--no-tui` in `sys.argv`
(checked and stripped, mirroring Ruby's `ARGV.delete`) sets `tui=False`;
and legacy `MUD_NAME`/`MUD_HOST`/`MUD_PORT`/`MUD_PASSWORD` env vars, when
`MUD_NAME` is set, build a `mud=` dict directly (taking precedence over
`settings.yaml`) and force `working_dir=False` — aborting with a clear
message if `MUD_NAME` is set but `MUD_PASSWORD` isn't, matching Ruby's
`ENV.fetch("MUD_PASSWORD") { abort ... }`.

**`examples/demo.py` is carried forward completely unchanged**, same as
Ruby's own choice — it's still the step 10 MUD demo and doesn't exercise
the TUI at all (the README says as much). The TUI itself is tried via the
global `boukensha` command, same as Ruby.

## Verification plan

A real terminal UI can't be smoke-tested the way `Repl.start()` was
(scripted `io.StringIO` stdin) — Textual ships an official headless
testing harness (`App.run_test()` returning a `Pilot` that can simulate
key presses and inspect widget state) built exactly for this; using it
rather than inventing an ad hoc approach.

- `Repl`'s composability refactor in isolation first: `on_output` reroutes
  all output through a callback instead of `print`; `handle_command`
  returns the right sentinel (`"quit"`/`"command"`/`None`) for each
  command including confirming `/quiet`/`/loud` are no longer recognized
  (fall through to being sent to the agent, same as any unrecognized
  slash-prefixed input would); `banner` is callable publicly.
- `Agent`'s new `cancel_event`: a multi-iteration fake-client run
  (reusing the step-05-style harness) where the event is set mid-turn —
  confirm the loop stops at the next iteration boundary and a distinct
  "interrupted" signal is raised, not silently swallowed.
- Drive the actual `Tui` app via `run_test()`: type text + Enter triggers
  a turn (with a fake client so no real network happens); `/clear` via
  typed input resets turn count; `ctrl+l` does the same as a direct
  binding; `pgup`/`pgdown` scroll the conversation viewport; `ctrl+c`
  and `ctrl+d` both quit; `esc` during an in-flight fake turn sets the
  cancel event and the UI shows an interrupted state.
- The progress line's tick-driven updates: subscribe a fake `Logger`,
  push `iteration`/`tool_call`/`response`/`turn_complete` events through
  it, advance the interval timer, and confirm the rendered progress
  `Static` reflects each phase (including the idle→active→idle
  transition and the token-count accumulation).
- `boukensha_loader.py`'s two new behaviors: `--no-tui` strips itself from
  `sys.argv` and resolves to `tui=False`; the legacy `MUD_*` env var path
  builds the expected `mud=` dict and forces `working_dir=False`; missing
  `MUD_PASSWORD` with `MUD_NAME` set aborts with a clear message.

## Outcome

_(fill in after implementation)_
