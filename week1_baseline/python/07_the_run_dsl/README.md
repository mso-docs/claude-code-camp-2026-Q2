# 07 · The `boukensha.run` DSL (Python port)

Python port of [`ruby/07_the_run_dsl`](../../ruby/07_the_run_dsl). One
entry point that hides all the manual `Context`/`Registry`/backend/
`PromptBuilder`/`Client`/`Logger`/`Agent` wiring:

```python
def configure(dsl):
    @dsl.tool(
        "read_file",
        description="Read a file from disk",
        parameters={"path": {"type": "string", "description": "File path"}},
    )
    def read_file(path):
        return Path(path).read_text()

result = boukensha.run(task="Summarise boukensha/__init__.py", block=configure)
```

`system`/`model`/`backend` all default from `.boukensha/settings.yaml` via
the same `tasks.player` config every prior step used, and are still
overridable as keyword arguments.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/run_dsl.py` | `RunDSL` — tiny host object, exposes only `.tool()` |
| `boukensha/__init__.py` | adds `run()` — mirrors Ruby's placement (defined in the same top-level file as `config()`/`set_debug()`, not a submodule) |
| `boukensha/logger.py` | adds `turn(n=)` and `subscribe(callback)` — both unused *in this step*, see below |

`agent.py` and every backend are unchanged from step 06 — confirmed by
diffing the Ruby reference directly, zero output.

## Notable differences from the Ruby version

- **Ruby's block/`instance_eval` has no Python equivalent — a callback
  parameter instead.** `Boukensha.run(task: ...) do tool "x", ... end`
  executes the block with `self` rebound to a `RunDSL` (`instance_eval`),
  so bare `tool "name", ...` resolves to `RunDSL#tool`. Python has no
  rebind-self-inside-a-block construct, so `run()` takes an optional
  `block` parameter — a plain callable receiving the `RunDSL` instance —
  and the caller registers tools by calling `.tool(...)` (the same
  decorator from step 02) on it. Same shape, Python's actual spelling.
- **`run()` reuses the global `Config` singleton**, not a fresh instance
  like every earlier example built locally — matches Ruby's `Boukensha.run`
  calling module-level `Boukensha.config`, the same memoized instance
  `Logger`'s default session directory uses. Ported as `state.config()`.
- **The `finally`-equivalent covers failures before `Logger` exists.**
  If backend construction raises (e.g. an unsupported model), Ruby's
  `logger` local is still `nil` and `logger&.close` no-ops. `logger = None`
  is initialized before the `try`, so a `finally: if logger is not None:
  logger.close()` never raises trying to close something that was never
  created — verified directly (see below).
- **Two `Logger` additions ship in this step, neither called by it.**
  `turn(n=)` and `subscribe(callback)` are new to `logger.py` here but
  unused in this step's own code (confirmed by grep on the Ruby side) —
  per `ITERATIONS.md`, `subscribe` is what a later TUI step uses to drive a
  live progress line without polling the log file. Ported now since
  they're part of this step's actual `Logger` class, not because this step
  exercises them.
- **`subscribe`'s callback gets the pre-merge event.** `_write_log` builds
  a separate `full_event` dict (with `session_id`/`at` added) for the file
  write, and calls subscribers with the original `event` — they never see
  `session_id`/`at`. Verified directly.
- **Snapshot drift, restored rather than re-dropped:** `config.py`'s
  `mud_*` accessors and `errors.py`'s `LoopError` — both dropped in step
  06's Ruby snapshot — are back in step 07's, unchanged from step 05. Not
  a design decision on Ruby's part; these per-step reference snapshots
  aren't strict incremental diffs of each other. Restored here to match
  what's actually in this step's code, still unused everywhere.
- **README accuracy note (Ruby side, not this port):** the Ruby README for
  this step is headed "Step 6" (should be 7), documents a `token_budget:
  8192` parameter that doesn't exist anywhere in the actual code (the real,
  similarly-named one is `max_output_tokens:`), claims only `:anthropic`/
  `:ollama` are supported when the code handles all 5, and says "the
  logger prints each phase to stdout" — it doesn't; `Logger` only ever
  writes to its `.jsonl` file, and `Agent` itself prints nothing as of
  step 06.

## Verification

- `RunDSL.tool` delegates correctly to the underlying `Registry` (a tool
  registered through the DSL is dispatchable afterward).
- `run()`'s defaulting logic against a real scratch `settings.yaml`
  (patching `Client.call` to avoid a network call): confirmed `model` is
  pulled from `tasks.player.model` when omitted, and an explicit
  `model=` override wins over the settings default.
- An unsupported `model=` fails during backend construction, before
  `Logger` is created — confirmed `run()` propagates the original
  `UnsupportedModelError` cleanly, no secondary error from `finally`.
- `Logger.subscribe`: registered a callback, logged two events, confirmed
  it fired with the pre-merge dicts (no `session_id`/`at` keys).
- Ran the real example against a scratch `settings.yaml` with a fake
  Anthropic key — reached `api.anthropic.com`, got the expected `401`, and
  the session's `.jsonl` correctly recorded all 5 snapshot fields
  (`task`, `max_iterations`, `max_output_tokens`, `model`, `provider`) on
  its `session_start` line.

## Run

```bash
uv sync
../bin/07_the_run_dsl
```
