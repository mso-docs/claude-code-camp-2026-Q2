# 06 · The Logger (Python port)

Python port of [`ruby/06_the_logger`](../../ruby/06_the_logger). `Logger`
records each agent run as structured JSON Lines — one file per session at
`.boukensha/sessions/<session-id>.jsonl` — a file logger, not display
output.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/logger.py` | `Logger` — new |
| `boukensha/state.py` | module-level global state (`config()`, `set_debug()`, etc.) — new, see below |
| `boukensha/agent.py` | gains logging calls at every phase, **and** tool-dispatch error handling (new) |
| `boukensha/config.py` | drops `mud_host`/`mud_port`/`mud_username`/`mud_password` (matches this step's Ruby snapshot — unused, and this step's `settings.yaml` example has no `mud:` block) |
| `boukensha/errors.py` | drops `LoopError` (matches this step's Ruby snapshot — it was already dead code) |

## Notable differences from the Ruby version

- **Module-level global state needed its own module, not `__init__.py`.**
  Ruby's `boukensha.rb` defines `Boukensha.config`/`.debug!`/`.debug?`
  directly on the top-level module, and `logger.rb` (loaded later in the
  same file) freely calls back into them — safe in Ruby because `require`
  doesn't evaluate those calls until they actually run. A literal Python
  translation (state living in `boukensha/__init__.py`, `logger.py` doing
  `import boukensha` to reach it) is a circular import: `__init__.py`
  hasn't finished defining that state by the time it's importing `Logger`
  from `.logger`. Fixed by giving the state its own `boukensha/state.py`
  with no sibling dependencies; `logger.py` imports directly from `.state`
  (no circularity), and `__init__.py` re-exports `state`'s functions.
- **Naming Ruby's `!`/`?` methods.** Python identifiers can't end in `!`/`?`.
  `Boukensha.quiet!` → `state.set_quiet()`, `.loud!` → `set_loud()`,
  `.quiet?` → `is_quiet()`, `.debug!` → `set_debug()`, `.debug?` →
  `is_debug()`. `quiet`/`set_loud` are ported for parity even though —
  like `LoopError` before it — nothing in this step reads `_quiet` anywhere;
  only `debug` is wired to real behavior (gating `Logger.raw`).
- **A real Python gotcha avoided: an instantiated default argument.** Ruby's
  `Agent#initialize(..., logger: Logger.new, ...)` evaluates `Logger.new`
  fresh on every call that omits it. Python default argument values are
  evaluated **once, at function-definition time** — `def __init__(self,
  ..., logger=Logger()):` would construct a single `Logger` (opening one
  file) when the class is defined, and every `Agent` that didn't pass its
  own logger would share that one instance and file. Used
  `logger: Logger | None = None`, constructing the real default inside the
  method body instead.
- **New behavior, not just translation: tool-call errors no longer crash
  the agent.** `registry.dispatch(...)` is now wrapped in a
  try/except; a raised exception becomes an `"ERROR: {type}: {message}"`
  string fed back to the model as the tool result, and gets logged as
  `tool_result(..., ok=False, error=...)`.
- **All of step 05's console `puts` output is gone in this step's Ruby.**
  Confirmed by grep — zero `puts` calls in `06_the_logger/lib/boukensha/agent.rb`.
  The `[iteration N/M]`, `tool call →`, `tool result →` console lines from
  step 05 are deleted outright, not supplemented — the JSONL file is now
  the only detailed record of a run. (Missed this on the first pass and had
  to remove `print()` calls that shouldn't have carried forward.)
- **A genuine quirk in the Ruby reference, carried forward as-is:**
  `_provider_name` derives a backend's logged provider name from its class
  name via CamelCase→snake_case (`OllamaCloud` → `ollama_cloud`, matching
  the `settings.yaml` key exactly) — except `OpenAI` → `open_ai` (the
  regex splits on the lowercase-then-uppercase boundary in `nA`), while the
  actual config key is `openai`. Every other backend's derived name happens
  to match its config key; OpenAI's doesn't. Reproduced, not fixed —
  verified in tests.
- **`Logger.response`'s metadata filtering is asymmetric on purpose.**
  `usage`/`stop_reason` stay as explicit `null` in the JSONL when `None`;
  the derived metadata dict (`task`/`provider`/`model`/`cost_usd`/etc.) has
  its own `None` entries dropped before merging. A single blanket "drop all
  `None`s" would quietly change the logged schema.
- **Token-count key lookup returns `None` on the first bad value, not the
  next candidate key.** `_first_integer` tries several provider-specific
  key names (`input_tokens`, `prompt_tokens`, `promptTokenCount`,
  `prompt_eval_count`, ...) but if the first matching key's value can't
  convert to `int`, it returns `None` immediately — matching Ruby's
  method-level `rescue`, not a per-key catch-and-continue.

## Verification

- `Logger` against a temp dir: one file per session, correct
  `session_id`/`at` on every line, `raw()` gated by `state.is_debug()`.
- `response()`'s metadata filtering: explicit `null` `usage`/`stop_reason`
  vs. fully-dropped metadata keys when `task`/`backend`/`usage` are all
  `None`.
- `_provider_name` across all 5 backends, confirming the `OpenAI` →
  `open_ai` mismatch reproduces exactly.
- Drove `Agent.run()` with a tool that raises `RuntimeError` — confirmed
  the agent didn't crash, the model got an `"ERROR: RuntimeError: ..."`
  tool result, and the logged event has `ok: false` with the message.
- Confirmed two `Agent`s constructed without `logger=` get distinct
  `Logger` instances and session files, not a shared one.
- Ran the real example against a scratch `settings.yaml` with a fake
  Anthropic key — reached `api.anthropic.com`, got a real `401`, and the
  session's `.jsonl` file correctly recorded `session_start`, `iteration`,
  and `prompt` before the request failed.

## Run

```bash
uv sync
../bin/06_the_logger
```

Session logs land in `.boukensha/sessions/<session-id>.jsonl`.
