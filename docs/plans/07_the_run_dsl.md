# Step 07 · The `Boukensha.run` DSL

**Ruby reference:** `week1_baseline/ruby/07_the_run_dsl/`
**Python port:** `week1_baseline/python/07_the_run_dsl/`
**Status:** Done

## Goal

One entry point — `Boukensha.run(task:, ...) { tool ... }` — that hides all
the manual `Context`/`Registry`/backend/`PromptBuilder`/`Client`/`Logger`/
`Agent` wiring behind a single call plus a small tool-registration block.
Defaults for `system`/`model`/`backend` come from `.boukensha/settings.yaml`
via the same task-config path every prior step used; every default is
still overridable as a keyword argument.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/run_dsl.rb` (`RunDSL`) | `boukensha/run_dsl.py` | tiny host object, exposes only `tool` |
| `lib/boukensha.rb` (`Boukensha.run`) | added to `boukensha/__init__.py` | mirrors Ruby's placement — `run` is defined in the same top-level file as `config`/`debug!`, not a submodule |
| `lib/boukensha/logger.rb` (+`turn`, +`subscribe`) | `boukensha/logger.py` | two additions, both unused *in this step* — see Design decisions |

`agent.rb` and **every** backend file are byte-identical between Ruby's
`06_the_logger` and `07_the_run_dsl` (diffed directly, zero output) —
carried forward with no changes. `context.rb`/`prompt_builder.rb`/etc. only
differ in whitespace.

**Snapshot inconsistency, not a design change:** `config.rb`'s `mud_*`
accessors and `errors.rb`'s `LoopError` — both dropped in step 06's
snapshot — are back in step 07's, unchanged from step 05. This is the same
kind of drift we've seen in READMEs, just showing up in code this time:
these per-step reference directories aren't strict incremental diffs of
each other, so a method can disappear and reappear between steps with no
functional meaning behind it. Restoring both in this step's `config.py`/
`errors.py` to match what's actually here now, not because they're used
(they still aren't).

**README is stale in three places** — noted so a manual test against it
doesn't cause confusion: it's headed "Step 6" (should be 7); its options
table lists a `token_budget: 8192` parameter that doesn't exist anywhere in
`run_dsl.rb`/`boukensha.rb` (the real, similar-sounding parameter is
`max_output_tokens:`); and it claims only `:anthropic`/`:ollama` are
supported backends, when the actual `case backend` in `Boukensha.run`
handles all 5. Also claims "the logger prints each phase to stdout" — it
doesn't; `Logger` only ever writes to its `.jsonl` file (`@log_io.puts`
writes to a `File` handle, not the console), and we confirmed in step 06
that `Agent` itself prints nothing anymore either.

## Design decisions

**Ruby's block/`instance_eval` has no Python equivalent — used a callback
function instead.** `Boukensha.run(task: ...) do tool "x", ... end`
executes the block with `self` rebound to a `RunDSL` instance
(`instance_eval`), so bare `tool "name", ...` inside the block resolves to
`RunDSL#tool`. Python has no block-with-rebound-self construct. The
natural equivalent: `run()` takes an optional `block` parameter — a plain
callable that receives the `RunDSL` instance as an argument, and registers
tools by calling `.tool(...)` (still our existing decorator) on it:

```python
def configure(dsl):
    @dsl.tool("read_file", description="...", parameters={"path": {"type": "string"}})
    def read_file(path):
        return Path(path).read_text()

result = run(task="...", block=configure)
```

Same shape (describe tools, hand them to `run`), Python's actual spelling
of "pass a chunk of registration code in."

**`run()` uses the *global* `Config` singleton, not a fresh instance.**
Every earlier example built its own `Config()` locally. `Boukensha.run`
specifically calls the module-level `Boukensha.config` (the memoized
singleton also used by `Logger`'s default session directory) — the whole
point of the DSL is "config is loaded automatically," so it deliberately
reuses the shared instance rather than constructing its own. Ported as
`state.config()`.

**`ensure logger&.close` covers the *whole* method, including failures
before the logger exists.** If backend construction raises (e.g., an
unsupported model), Ruby's `logger` local is still `nil` at that point, and
`&.close` on `nil` is a no-op — the `ensure` block never assumes `logger`
was successfully created. The Python `try/finally` needs the same
`logger = None` sentinel initialized *before* the try, not just wrapping
the final `agent.run()` call, or a failure earlier in setup would raise a
`NameError` from the `finally` block referencing an undefined `logger`
instead of propagating the original error cleanly.

**Two `Logger` additions land in this step, neither used by it.**
`turn(n:)` (a bare `{"phase": "turn", "n": n}` event) and
`subscribe(&block)` (register a callback invoked with every logged event)
are both new to `logger.rb` here but never called anywhere in this step's
`lib/` or `examples/` (confirmed by grep). Per `ITERATIONS.md`, `subscribe`
is what a later TUI step uses to drive a live progress line without
polling the log file — forward-looking infrastructure, not dead code like
`LoopError`. Porting both now since they're part of this step's actual
`Logger` class.

**`subscribe`'s callback receives the *pre-merge* event dict.** Ruby's
`write_log(event)` does `event.merge(session_id:, at:)` — `.merge` returns
a new hash, so the original `event` parameter is unchanged — and then
calls each subscriber with that original `event`, not the merged one
written to the file. Subscribers never see `session_id`/`at`. Easy to get
backwards if `_write_log` builds the merged dict as its working variable
first and passes *that* everywhere.

**No `symbol`/string conversion needed for `backend`.** Ruby does
`backend ||= task_class.provider(task_settings).to_sym` and matches it with
`case backend when :anthropic ...`. Python keeps `backend` a plain string
throughout and compares against string literals — the same
symbol-vs-string duality collapse we've noted in every step since 00.

## Verification plan

- Unit-test `RunDSL.tool` delegates correctly to the underlying `Registry`
  (a tool registered through the DSL is dispatchable afterward).
- Unit-test `run()`'s defaulting logic directly (without a real network
  call) by monkeypatching/stubbing `Client.call` — confirm `system`/
  `model`/`backend` are correctly pulled from a stub `Config`/task
  settings when omitted, and correctly overridden when passed explicitly.
- Confirm the `ensure`-equivalent: force a failure *before* `Logger` is
  constructed (e.g., an unsupported model) and confirm `run()` doesn't
  raise a secondary error trying to close a nonexistent logger.
- Unit-test `Logger.subscribe`: register a callback, log an event, confirm
  the callback fired with the pre-merge dict (no `session_id`/`at` keys).
- Run the real example against a scratch `settings.yaml` with a fake key,
  same as steps 05/06 — confirm it reaches the live API and the session
  log is written, this time via the one-call DSL instead of manual wiring.

## Outcome

Matched the plan on every anticipated design decision. All verification-plan
items passed: `RunDSL.tool` delegation, `run()`'s defaulting logic against a
real scratch `settings.yaml` (model pulled from config when omitted,
explicit override wins), an unsupported model failing cleanly before
`Logger` exists with no secondary error from the `finally`, `subscribe()`
receiving pre-merge event dicts, and a real request against
`api.anthropic.com` with a fake key that both hit the live API (401, as
expected) and correctly wrote all 5 snapshot fields
(`task`/`max_iterations`/`max_output_tokens`/`model`/`provider`) to the
session's `session_start` line. See
[`python/07_the_run_dsl/README.md`](../../week1_baseline/python/07_the_run_dsl/README.md).
