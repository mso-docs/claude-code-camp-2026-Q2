# 08 · The REPL Loop (Python port)

Python port of [`ruby/08_the_repl_loop`](../../ruby/08_the_repl_loop).
`boukensha.repl` — same shape as `run()`, minus `task=` — starts an
interactive session: register tools once, then loop reading from stdin,
running the agent, and printing replies, with conversation history
accumulating across turns instead of being discarded after one call.

```python
def configure(dsl):
    @dsl.tool("read_file", description="Read a file from disk",
              parameters={"path": {"type": "string", "description": "File path"}})
    def read_file(path):
        return Path(path).read_text()

boukensha.repl(block=configure)
```

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/repl.py` | `Repl` — the interactive loop, new |
| `boukensha/version.py` | `VERSION = "0.8.0"`, new |
| `boukensha/__init__.py` | adds `repl()` alongside `run()` |
| `boukensha/agent.py` | final reply now persisted to `context.messages` (3 call sites) |
| `boukensha/context.py` | adds `clear_messages()` |
| `boukensha/client.py` | friendlier message on a `401` |
| `boukensha/config.py` | dir resolution gains a project-local `.boukensha/` tier |

`logger.py`, `errors.py`, `run_dsl.py`, all 5 backends, `registry.py`,
`prompt_builder.py`, `message.py`, `tool.py`, `tasks/base.py` are all
unchanged from step 07 — confirmed by diffing the Ruby reference directly.

## The README claim that turned out to be false

The Ruby README says this step adds a `Logger#turn` "that prints a
`╔══ turn N ══╗` header." **It doesn't.** Diffing `logger.rb` against step
07 shows zero changes — `turn(n:)` already existed and still only writes a
JSONL line, exactly like every other `Logger` method; it never calls
`puts`. Any turn-boundary banner is `Repl`'s own job, not `Logger`'s. This
is the most flatly wrong README claim found in this port so far (earlier
ones were stale or incomplete, not simply untrue) — caught by diffing
instead of trusting the prose, worth remembering as a habit.

## Notable differences from the Ruby version

- **`Agent` now persists its final reply — in three places.** Before this
  step, returning final text without storing it was fine (a one-shot
  `run()` throws the whole `Context` away afterward). A REPL needs the
  transcript to survive between turns, so `context.add_message("assistant",
  text)` now happens right before every point `Agent` returns final text:
  the normal `end_turn` branch, `_wrap_up`'s successful wind-down, *and*
  `_wrap_up`'s `ApiError`-fallback branch. All three verified independently.
- **A new `Agent` is built every turn**, sharing the same `context`/
  `registry`/`builder`/`client`/`logger` — so `agent.iteration` correctly
  resets to 0 per turn while history and tool registrations persist via the
  shared objects. Verified by spying on `Agent.__init__`.
- **`/quiet`/`/loud` set real state nothing currently reads.** They call
  `state.set_quiet()`/`set_loud()` and the REPL prints a confirmation
  either way, but no code — `Logger`, `Agent`, or `Repl` itself — ever
  checks `state.is_quiet()`. Ported as-is; flagged so it isn't mistaken for
  a bug when nothing visibly changes after `/quiet`.
- **`KeyboardInterrupt` ↔ Ruby's `Interrupt`.** Ctrl-C during `repl()` is
  caught around the `Repl(...).start()` call, same placement as Ruby's
  `rescue Interrupt` around the whole `Boukensha.repl` method body.
- **EOF detection uses `readline()`, not `input()`.** Python's `input()`
  raises `EOFError` instead of returning a sentinel on EOF; `sys.stdin.readline()`
  returns `""` only at true EOF (a blank user line is `"\n"`, never `""`),
  which is what lets `if not line: break` read as the direct equivalent of
  Ruby's `$stdin.gets` returning `nil`.
- **`Config`'s dir resolution gained a real third tier**, not just
  cosmetic: `$BOUKENSHA_DIR` → **a `.boukensha/` in the current working
  directory, if one actually exists** → `~/.boukensha`. Lets a
  project-local config override the home default without setting an env
  var. Verified directly against a temp CWD.
- **`run()` and `repl()`'s setup logic are deliberately duplicated, not
  refactored into a shared helper** — matching the Ruby reference, where
  `self.run` and `self.repl` are independent, copy-pasted method bodies
  rather than sharing one. Since this step's Ruby source didn't factor
  that out, the port doesn't either, even though Python easily could.

## Verification

Genuinely different from steps 05–07: `Repl.start()` blocks on stdin, so
"run the example and see what happens" isn't a valid smoke test by itself.

- Drove `Repl.start()` with scripted stdin (an `io.StringIO`) covering:
  two normal turns (confirming history accumulates — the fake client sees
  more messages in context on the second call), `/quiet`/`/loud`
  (confirmed `state.is_quiet()` reflects the last command), `/help`,
  `/clear` (wipes `context.messages`, tools survive), a blank line
  (re-prompts, doesn't count as a turn), and `/exit`.
- Spied on `Agent.__init__` to confirm a distinct `Agent` per turn, each
  ending with `iteration == 1` (no cross-turn carryover), while
  `context`/`registry` stayed the same objects throughout.
- EOF (empty stdin) terminates `start()` cleanly.
- An `ApiError` raised mid-turn is caught, printed, and the REPL
  continues to the next prompt rather than crashing.
- `Context.clear_messages()` unit-tested directly.
- `Config`'s new middle tier: a `.boukensha/` in a temp CWD is picked up
  over `~/.boukensha` when `$BOUKENSHA_DIR` is unset.
- `Client`'s 401 path against a local stub server, alongside the existing
  step-04 retry/failure tests.
- All three of `Agent`'s new `add_message` sites verified independently
  with the step-05-style fake-client harness.
- Ran the real example via piped stdin (`"list the files here\n/exit\n"`)
  against a scratch `settings.yaml` with a fake Anthropic key — the real
  banner rendered, the request reached `api.anthropic.com`, the new
  friendly 401 message printed, and the REPL recovered and processed
  `/exit` normally afterward. Session log correctly recorded
  `session_start`/`turn`/`iteration`/`prompt`.

## Run

```bash
uv sync
../bin/08_the_repl_loop
```

Interactive — type a task, or `/help` for commands, `/exit` to quit.
