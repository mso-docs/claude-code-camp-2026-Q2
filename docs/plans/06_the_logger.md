# Step 06 · The Logger

**Ruby reference:** `week1_baseline/ruby/06_the_logger/`
**Python port:** `week1_baseline/python/06_the_logger/`
**Status:** Done

## Goal

`Logger` records each agent run as structured JSON Lines — one file per
session at `.boukensha/sessions/<session-id>.jsonl`, one JSON object per
line, each phase (`session_start`, `iteration`, `prompt`, `tool_call`,
`tool_result`, `response`, `limit_reached`, `turn_end`, `raw`) carrying its
own fields plus a shared `session_id`/`at`. It's a file logger, not
display output — `Agent` gets threaded through with logging calls at every
phase.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/logger.rb` | `boukensha/logger.py` | new — the big one |
| `lib/boukensha.rb` (module-level `@config`/`@quiet`/`@debug`) | `boukensha/state.py` (new) + re-exported from `boukensha/__init__.py` | see Design decisions — can't live directly in `__init__.py` |
| `lib/boukensha/agent.rb` | `boukensha/agent.py` | gains a `logger` param + logging calls at every phase, **and** tool-dispatch error handling (new) |
| `lib/boukensha/prompt_builder.rb` (adds `attr_reader :backend`) | `boukensha/prompt_builder.py` | no-op — `self.backend` was already accessible in Python |
| `lib/boukensha/config.rb` (drops `mud_*` accessors) | `boukensha/config.py` | drop `mud_host`/`mud_port`/`mud_username`/`mud_password` — this step's `settings.yaml` example has no `mud:` block, and they were unused everywhere already |
| `lib/boukensha/errors.rb` (drops `LoopError`) | `boukensha/errors.py` | drop `LoopError` — matches this step's Ruby snapshot; it was flagged dead code in step 05 anyway |

`backends/*.py`, `client.py`, `registry.py`, `tasks/base.py`, `context.py`,
`message.py`, `tool.py` are all byte-identical between Ruby's `05_agent_loop`
and `06_the_logger` (diffed directly) — carried forward with no changes.

## Design decisions

**Module-level global state needs its own module, not `__init__.py`.**
Ruby's `boukensha.rb` defines `Boukensha.config`/`.quiet!`/`.loud!`/
`.quiet?`/`.debug!`/`.debug?` directly on the top-level module, and
`logger.rb` (required later in the same file) freely calls back into
`Boukensha.config`/`Boukensha.debug?` — this works in Ruby because
`require` doesn't evaluate those calls until they actually run. A literal
Python translation (putting this state in `boukensha/__init__.py` and
having `logger.py` do `import boukensha` to reach it) would be a circular
import: `__init__.py` imports `Logger` from `.logger` before it's finished
defining the very state `logger.py` needs to reach back for. Fix: the
global state lives in a new `boukensha/state.py` with no dependencies on
sibling modules; `logger.py` imports directly from `.state` (no
circularity), and `boukensha/__init__.py` re-exports `state`'s functions
for the public `boukensha.config()` / `boukensha.set_debug()` API.

**Naming Ruby's `!`/`?` methods.** Python identifiers can't end in `!` or
`?`. Using verb-prefix naming instead: `Boukensha.quiet!` → `set_quiet()`,
`.loud!` → `set_loud()`, `.quiet?` → `is_quiet()`, `.debug!` → `set_debug()`,
`.debug?` → `is_debug()`. `quiet`/`loud` are ported for structural parity
even though — like `LoopError` before them — nothing in this step's code
actually reads `@quiet` anywhere; only `debug?` is wired to real behavior
(gating `Logger#raw`).

**A real Python gotcha to avoid: mutable/instantiated default arguments.**
Ruby's `Agent#initialize(..., logger: Logger.new, ...)` evaluates
`Logger.new` fresh on *every call* that doesn't pass its own logger — each
default is a new instance, a new session file. Python default argument
values are evaluated **once, at function-definition time** — a literal
`def __init__(self, ..., logger=Logger()):` would construct a single
`Logger` (opening one file) when the class is *defined*, and every `Agent`
that didn't pass its own logger would share that one instance and file.
Using `logger: Logger | None = None` and constructing
`self.logger = logger if logger is not None else Logger()` inside the
method body instead — the standard fix for this well-known Python trap.

**All of step 05's console `puts` output is gone, replaced entirely by the
JSONL logger.** Confirmed by grepping `06_the_logger/lib/boukensha/agent.rb`
for `puts` — zero matches. Step 05's `[iteration N/M]`, `tool call →`, and
`tool result →` console lines don't just get logger calls added alongside
them; they're deleted outright. Missed this on first read and had to fix it
after writing the initial port — `Agent` in this step produces almost no
stdout of its own; the file log is now the only detailed record of a run.

**New in this step: tool-call errors no longer crash the agent.** Step 05's
`handle_tool_calls` let a tool exception propagate straight up through
`Agent.run()`. This step wraps each `registry.dispatch(...)` call in a
rescue (`except Exception` in Python — matches Ruby's broad
`rescue StandardError`), turns a raised exception into a
`f"ERROR: {type(e).__name__}: {e}"` string tool result fed back to the
model, and logs `tool_result(..., ok=False, error=str(e))`. This is a real
behavior change, not translation noise — flagging it because it's easy to
port the *shape* of `handle_tool_calls` without noticing the try/except is
new.

**`handle_tool_calls` also logs a synthetic "reasoning" response.** Before
dispatching any tool calls, it logs a `response` phase using whatever text
the model included alongside the tool_use blocks — or, if there was none,
a placeholder like `"(tool use — 2 calls)"` (correct pluralization, em dash
literal). This is purely a logging enrichment; it doesn't change what gets
added to `context.messages`.

**`Logger#response` builds its metadata dict then filters `None`s — but
only *that* sub-dict.** Ruby's `write_log({phase:, text:, usage:, stop_reason:}.merge(execution_metadata(...)))` — `execution_metadata` internally
`.compact`s itself (drops its own nil entries: `task`, `provider`, `model`,
`usage_unit`, `usage_level`, `input_tokens`, `output_tokens`, `cost_usd`),
but `usage`/`stop_reason` on the *outer* hash are never compacted — they
can appear as explicit `null` in the JSONL even when `nil`. Porting this
distinction exactly (filter the metadata dict only, not the whole event)
rather than "helpfully" dropping all `None`s, which would silently change
the JSONL schema.

**A genuine quirk in the Ruby reference, carried forward: `provider_name`
doesn't match the `settings.yaml` provider key for OpenAI.** It's derived
from the backend's *class name* via a CamelCase→snake_case regex
(`OllamaCloud` → `ollama_cloud`, matches the config key `ollama_cloud`
exactly) — except `OpenAI` → `open_ai` (the regex inserts an underscore
between the lowercase `n` and the uppercase `A` in `OpenAI`), while the
actual `settings.yaml` provider key is `openai` (no underscore). Every
other backend's derived name happens to match its config key; OpenAI's
doesn't. Not fixing it — it's what the Ruby logs actually say.

**Token-count field names vary by provider; `first_integer` tries several
and returns `None` on the first bad value, not the next candidate key.**
Ruby's `rescue` wraps the *whole method*, so if the first matching key's
value can't convert to an integer, the method returns `nil` immediately
rather than falling through to try the next key name. A per-key
try/except that only catches-and-continues would silently change this to
"try the next key on a bad value," which is a different (arguably nicer,
but not faithful) behavior.

## Verification plan

- Unit-test `Logger` directly against a temp directory: confirm one JSONL
  file per session, correct `session_id`/`at` on every line, and that
  `raw()` only writes when `state.is_debug()` is true.
- Unit-test the metadata-filtering behavior of `Logger.response` (a
  `None` `task`/`backend` should drop those keys; `usage`/`stop_reason`
  should stay as explicit `null` when `None`).
- Unit-test `_provider_name` against all 5 backend classes, confirming the
  `OpenAI` → `open_ai` mismatch reproduces.
- Drive `Agent.run()` with a fake client (as in step 05) but this time
  have a registered tool *raise* — confirm the agent doesn't crash, the
  model gets an `"ERROR: ..."` tool result, and the logged `tool_result`
  event has `ok: false` with the error message.
- Confirm `Agent()` constructed twice without an explicit `logger=` gets
  two distinct `Logger` instances (two distinct session files), not one
  shared instance.

## Outcome

Matched the plan on every anticipated design decision (state module,
default-argument gotcha, metadata filtering, `first_integer` bail-on-first-
bad-value, the OpenAI provider-name quirk). One thing the plan missed and
had to be caught mid-implementation: I initially carried step 05's console
`print()` calls forward into the logging-enriched `Agent`, assuming logging
was purely additive. Re-grepping the actual `06_the_logger/lib/boukensha/agent.rb`
for `puts` turned up zero matches — step 06 deletes all of step 05's console
output outright, relying on the JSONL file as the sole detailed record.
Fixed before verification, and added as an explicit design-decision note
so it doesn't get missed again in a later step. All verification-plan items
passed: session file structure, debug-gated `raw()`, response metadata
filtering (explicit `null` vs. dropped keys), the `OpenAI`→`open_ai`
provider-name mismatch, a raising tool surviving the loop and getting
logged with `ok: false`, two `Agent`s without explicit `logger=` getting
distinct instances/files, and a real run against `api.anthropic.com` with
a fake key that both hit the live API (401, as expected) and correctly
wrote `session_start`/`iteration`/`prompt` to its session log before
failing. See [`python/06_the_logger/README.md`](../../week1_baseline/python/06_the_logger/README.md).
