# Step 08 · The REPL Loop

**Ruby reference:** `week1_baseline/ruby/08_the_repl_loop/`
**Python port:** `week1_baseline/python/08_the_repl_loop/`
**Status:** Planned

## Goal

`Boukensha.repl` — same shape as `run()`, minus `task:` — starts an
interactive session: register tools once in a block, then loop reading
from stdin, running the agent, and printing replies, with conversation
history accumulating across turns (shared `Context`) instead of being
thrown away after one call.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/repl.rb` (`Repl`) | `boukensha/repl.py` | new — the interactive loop |
| `lib/boukensha/version.rb` | `boukensha/version.py` | new — `VERSION = "0.8.0"` |
| `lib/boukensha.rb` (`Boukensha.repl`) | added to `boukensha/__init__.py` | mirrors where `run()` already lives |
| `lib/boukensha/agent.rb` (persists final reply) | `boukensha/agent.py` | 3 call sites now add the final text to `context.messages` before returning — see Design decisions |
| `lib/boukensha/context.rb` (+`clear_messages!`) | `boukensha/context.py` | one new method |
| `lib/boukensha/client.rb` (+401 handling) | `boukensha/client.py` | a friendlier message on auth failure |
| `lib/boukensha/config.rb` (dir resolution gains a 3rd tier) | `boukensha/config.py` | see Design decisions |

`logger.py`, `errors.py`, `run_dsl.py`, all 5 backends, `registry.py`,
`prompt_builder.py`, `message.py`, `tool.py`, `tasks/base.py` are all
byte-identical between Ruby's `07_the_run_dsl` and `08_the_repl_loop`
(diffed directly) — carried forward unchanged. **Notably `logger.rb` has
zero diff** — see below, this contradicts the README.

## Design decisions

**The README's headline claim about `Logger#turn` is wrong — verify
before trusting it.** The README says this step adds a `Logger#turn` "that
prints a `╔══ turn N ══╗` header." Diffing `logger.rb` directly shows
**zero changes** from step 07 — `turn(n:)` already existed there and still
only writes a JSONL line, exactly like every other `Logger` method. It
never calls `puts`. Any turn-boundary banner comes from `Repl` itself, not
`Logger`. This is the most misleading README inaccuracy we've hit so far
(previous ones were incomplete or stale; this one describes behavior the
code doesn't have at all) — worth double-checking claims like this against
a diff rather than trusting the prose, which is exactly what caught it.

**Agent now persists its own final reply — in three places, not one.**
Before this step, `Agent#run`'s `end_turn` branch returned text without
storing it (fine for one-shot `run()`, since the whole `Context` gets
discarded afterward). A REPL needs the transcript to survive between
turns, so `context.add_message("assistant", text)` now happens right
before every point `Agent` returns final text: the normal `end_turn`
branch, `_wrap_up`'s successful wind-down, **and** `_wrap_up`'s
`ApiError`-fallback branch. Easy to add it to the obvious first spot and
miss the other two — confirmed all three against the Ruby diff.

**A new `Agent` is constructed on every turn, sharing the same `Context`.**
`Repl.run_turn` doesn't reuse one long-lived `Agent` — it builds a fresh
one each turn (so `agent.iteration` correctly resets to 0 per turn) while
passing in the *same* `context`/`registry`/`builder`/`client`/`logger`
every time, which is what actually carries history and tool registrations
across turns.

**`/quiet` and `/loud` set real state that nothing currently reads.**
They call `state.set_quiet()`/`set_loud()`, and `Repl` prints a
confirmation message either way — but no code anywhere (`Logger`, `Agent`,
`Repl` itself) ever checks `state.is_quiet()`. The final response is
printed unconditionally, "outside of the logger," per a comment in the
Ruby source — but since `Agent` prints nothing at all as of step 06, that
comment's practical effect is currently zero. Porting the commands as-is
(they're real, user-facing, and harmless) while flagging that they're not
wired to any actual behavior yet.

**`Ctrl-C` handling maps directly.** Ruby's `rescue Interrupt` around the
whole `Boukensha.repl` call ↔ Python's `except KeyboardInterrupt` around
the `repl.start()` call in `repl()` — same signal, different exception
name.

**EOF detection needs `readline()`, not `input()`.** Ruby's `$stdin.gets`
returns `nil` on EOF (Ctrl-D). Python's builtin `input()` *raises*
`EOFError` instead of returning a sentinel; `sys.stdin.readline()` returns
`""` on true EOF and is used here instead, since `if not line: break` reads
naturally as the nil-check equivalent — and, importantly, a blank
user-entered line is `"\n"`, never `""`, so EOF and "user just pressed
Enter" stay distinguishable before stripping.

**Client's config-dir resolution gains a third tier.** Previously
`$BOUKENSHA_DIR` env var → `~/.boukensha`. Now: `$BOUKENSHA_DIR` →
**a `.boukensha/` directory in the current working directory, if one
actually exists** → `~/.boukensha`. This is a real behavior change (lets a
project-local `.boukensha/` override the home directory without setting an
env var) — ported as a genuine third branch, not folded into the existing
two.

**`Client` gets a friendlier 401 message.** Inside the existing
"not a successful response" branch, a `401` now raises
`ApiError("authentication failed (401) — check your API key")` instead of
falling through to the generic `"API request failed after N attempts
(401): <body>"` message — checked *after* retries are exhausted (401 was
never retryable to begin with; this only changes the message, not the
retry behavior).

## Verification plan

Genuinely different from every prior step: `Repl.start()` blocks on stdin,
so "run the example" isn't a valid smoke test here the way it was for
05–07. Verification has to drive `Repl` without going through real
terminal I/O:

- Feed `Repl.start()` scripted input via a fake stdin (an `io.StringIO` or
  a list-backed readline stub) covering: a normal turn, `/clear` resetting
  `context.messages` but not `context.tools`, `/quiet`/`/loud` (confirm
  they toggle `state.is_quiet()`), `/help`, and `/exit` terminating the
  loop cleanly.
- Confirm conversation history actually persists: two scripted turns where
  the second turn's fake client response depends on seeing the first
  turn's messages in the payload it's asked to build.
- Confirm a fresh `Agent` is constructed each turn (patch `Agent.__init__`
  or check `iteration` resets) while `context`/`registry` identity stays
  the same across turns.
- Unit-test `Context.clear_messages()` directly.
- Unit-test the `Client` 401 path against a local stub server, alongside
  the existing 503-retries/400-fails-immediately tests from step 04.
- Unit-test `Config`'s new middle resolution tier: a `.boukensha/` in a
  temp CWD gets picked up over `~/.boukensha` when `$BOUKENSHA_DIR` is
  unset.
- Confirm all three of `Agent`'s new `add_message` call sites actually
  persist text: normal end-turn, successful wind-down, and the
  `ApiError`-fallback wind-down path (reuse the step-05 fake-client
  harness for the latter two).

## Outcome

_(fill in after implementation)_
