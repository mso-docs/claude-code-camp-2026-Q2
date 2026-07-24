# 12 · Context Management (Python port)

Python port of [`ruby/12_context`](../../ruby/12_context) — the final step
of the port. Two independent threads of change land in this step: real
context-window accounting (token tracking, colour-coded warnings, automatic
+ manual compaction) and a full removal of the `Tasks::Base`/`Tasks::Player`
abstraction layer that every prior step carried since step 00. `settings.yaml`'s
schema (`tasks.player.*`) is untouched — only the Ruby/Python code path
collapsed to flat `Config` methods.

Ruby's own `README.md` for this step documents only the context-management
half — verified by diff, not assumed. It says nothing about the Tasks
removal, the reasoning-block normalization across all five backends, or
OpenAI's full `/v1/responses` rewrite, all of which are real, substantial
changes in `lib/boukensha/**/*.rb` this step. This port implements and
documents all of it.

## The headline architectural change: Tasks are gone

`boukensha/tasks/` (`base.py`, `player.py`) is deleted, along with
`prompts/system.md`'s package-shipped fallback. Every place that used to go
`task_class.model(task_settings)` now reads a flat `Config` property
directly: `cfg.provider_type`, `cfg.model`, `cfg.system_prompt`,
`cfg.agent_max_iterations`, `cfg.agent_max_output_tokens`,
`cfg.agent_max_turn_tokens`, `cfg.agent_compaction_threshold`. `Config`
resolves `system_prompt` once, eagerly, at construction — there is no
package default to fall back to anymore; only the user's own
`.boukensha/prompts/` files are ever consulted, and the result is `None` if
neither exists.

`Config.system_override` survives as **dead code**, ported for parity: it's
never called anywhere, and it reads a different settings key
(`system.override`) than the one `_load_system_prompt` actually uses
(`tasks.player.prompt_override.system`) — confirmed independently in both
the Ruby source and this port's own tests (`system_override` can be `True`
while `system_prompt` still resolves the flat, non-overridden file, because
the two properties read unrelated keys).

## Context management

`Context` now tracks three distinct numbers instead of one:

| Attribute | Meaning |
|-----------|---------|
| `context_window` | The model's real ceiling (looked up per-model via the new `models.py`, not a guess) |
| `current_tokens` | Actual usage from the last response's `input_tokens` — **replaced**, not accumulated, each call |
| `turn_tokens` | This turn's cumulative input+output spend — **accumulated** across every call in the turn, reset at the top of the next turn |

`current_tokens` answers "how close am I to the window?" (compaction
pressure); `turn_tokens` answers "how much has this turn cost so far?"
(the second circuit breaker, see below). Conflating them was the old bug:
`token_budget` (an unrelated output-length constant) used to be shown as
if it were the window size, and the on-screen usage number grew forever
even after `/clear`.

- `Context.needs_compaction()` — `current_tokens / context_window >=
  compaction_threshold` (default 0.85).
- `Context.compact_messages()` — drops the oldest `ceil(len(messages) *
  0.40)` messages, clamped to `len(messages) - 2` (never below 0), and
  resets `current_tokens` to 0 (the next response's `input_tokens`
  supplies the true post-compaction size). Returns the number dropped.
- `Agent.run()` checks `needs_compaction()` once, before the loop starts
  — not mid-turn — and logs a `Logger.compaction` event when it fires.
- `/compact` (Repl and Tui) calls `compact_messages()` directly, on
  demand, with **no** `Logger.compaction` event — an asymmetry versus the
  automatic path, ported as-is from Ruby rather than "fixed."

### `models.py`

New this step: a static model → `context_window` lookup table
(`claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5`, all 200,000),
with a `DEFAULT_CONTEXT_WINDOW = 32_000` fallback for anything unlisted.
`boukensha.run()`/`repl()` use it to resolve `context_window` from
`model` when the caller doesn't pass one explicitly.

### Colour-coded context usage

`Tui`'s idle progress line and status bar both read `context.usage_pct`
directly and colour it:

| Usage | Colour | Meaning |
|-------|--------|---------|
| < 70% | `bright_black` | Normal |
| 70–84% | `yellow` | Approaching limit |
| ≥ 85% | `red` | Compaction imminent |

The status bar also shows a `⚠` indicator at ≥ 85%. `Tui._session_input_tokens`/
`_session_output_tokens` (the old, unbounded cumulative counters) are gone;
the idle progress/status lines now show real window pressure instead.

## Two independent circuit breakers

`Agent` now stops for either of two reasons, whichever trips first:

- `max_iterations` — unchanged from prior steps, a count of loop
  iterations.
- `max_turn_tokens` — new: `context.turn_tokens >= max_turn_tokens`
  (0/`None` disables it). Config default: 60,000.

Either one triggers the same wind-down path: one final, tools-disabled
call asking the model to summarize and stop, run *outside* the counted
loop (it cannot re-trigger either limit, and doesn't increment
`iteration`, though its tokens still count toward the reported turn
total).

## Reasoning-block normalization (all five backends)

Every backend's `parse_response()` now normalizes provider-specific
"thinking" output into a common block shape, documented in
`backends/base.py`:

```python
{"type": "reasoning", "text": "...", "signature": "...", "redacted": True}
```

placed first in `content`, ahead of `text`/`tool_use` blocks (matching
Anthropic's native ordering). `Agent._log_reasoning` emits one
`Logger.reasoning` event per non-empty (or redacted) block.

- **Anthropic**: native `thinking`/`redacted_thinking` blocks map to
  `reasoning` (signature/redacted preserved for round-tripping — the API
  rejects a modified thinking block on continuation). New
  `_assistant_content`/`_denormalize_block` convert stored `reasoning`
  blocks back to native shape when rebuilding an assistant turn. MODELS
  trimmed to 3 entries (`claude-opus-4-8`, `claude-sonnet-4-6`,
  `claude-haiku-4-5`).
- **OpenAI**: **full rewrite**, not incremental — moved from
  `/v1/chat/completions` to `/v1/responses` entirely. Different message
  shape (`to_input`, not `to_messages`; assistant items and
  `function_call`/`function_call_output` are separate input array
  entries, not one message with `tool_calls`), different tool shape (flat
  `{type, name, description, parameters}`, no `function:` wrapper), and a
  `reasoning: {"effort": "none"}` payload field. `parse_response` reads
  the interleaved `output` array (`reasoning`/`message`/`function_call`
  items) via a single pass. Reasoning blocks are dropped when rebuilding
  assistant turns — this API doesn't accept them back. MODELS: `gpt-5.5`,
  `gpt-5.4-mini`, `gpt-5.4-nano` (`gpt-5.4` dropped).
- **Gemini**: `thoughtSignature` round-trips on both `reasoning` and
  `tool_use` blocks. New `_thinking_config()` — `{"thinkingBudget": 0}` by
  default; a `{"thinkingLevel": "LOW"}` branch for
  `gemini-3.1-pro-preview-customtools` is **dead code**, ported exactly:
  that model is commented out of `MODELS`, so the branch is unreachable
  through normal use, matching the Ruby source precisely rather than
  simplifying it away. MODELS trimmed to 2 entries.
- **Ollama / OllamaCloud**: `think: false` in the request payload;
  `message["thinking"]` (when non-empty) becomes a `reasoning` block,
  dropped again when rebuilding the assistant message (Ollama doesn't
  accept `thinking` back in a request). `Ollama.MODELS` trimmed to a
  single entry (`gemma4:e4b`); `OllamaCloud.MODELS` keeps its 3 entries,
  reordered.

## A quieter real change: two file-system tools disabled

Found only by diffing `tools/file_system.rb` — not mentioned in the Ruby
README at all. `list_directory` and `search_files` are commented out
(not deleted) in both the Ruby source and this port, described in both as
"leftover from when this app was a coding harness; the player agent has no
use for them yet." `pwd`/`read_file`/`write_file`/`delete_file` are
unaffected.

## Logger changes

Cost/task/provider tracking — `_execution_metadata`, `_task_name`,
`_provider_name`, `_usage_tokens`, `_first_integer`, `_estimate_cost` (and
the `re` import they needed) — is **removed**, not simplified.
`response()` no longer takes `task=`/`backend=` at all; this also deletes
the OpenAI `provider_name` quirk's only remaining call site (from step 06).
New: `compaction(before, dropped, context_window)`, `reasoning(text,
redacted)`, `plan(text)` (logs tool-call preamble text separately from the
tool-use placeholder). `prompt()` gains a `context_window:` field.

## Code map

| File | Change |
|------|--------|
| `boukensha/models.py` | new — static model → `context_window` table |
| `boukensha/context.py` | rewrite — `current_tokens`/`turn_tokens` split, `usage_pct`, `needs_compaction`, `compact_messages` |
| `boukensha/config.py` | rewrite — flat methods replace `Tasks::Base`/`Tasks::Player`; `system_override` dead code documented inline |
| `boukensha/logger.py` | rewrite — cost/task/provider tracking removed; `compaction`/`reasoning`/`plan` added |
| `boukensha/agent.py` | rewrite — dual circuit breakers, compaction-before-loop, reasoning logging, `\n`-joined `_extract_text` |
| `boukensha/backends/*.py` | reasoning normalization everywhere; `openai.py` is a full `/v1/responses` rewrite; MODELS tables trimmed per-backend |
| `boukensha/backends/base.py` | doc-only — normalized response contract documented at module level |
| `boukensha/tools/file_system.py` | `list_directory`/`search_files` disabled (commented out), matching Ruby |
| `boukensha/repl.py` | `/compact` command; `task_settings:` removed, `max_turn_tokens:` added |
| `boukensha/tui.py` | context colour coding (`CTX_WARN_PCT`/`CTX_ALERT_PCT`), reads `context.current_tokens`/`context_window`/`usage_pct` directly, `compaction` event rendering |
| `boukensha/__init__.py` | rewrite — no more Tasks lookups; `context_window:` param on `run()`/`repl()`, resolved via `models.py` when omitted |
| `boukensha/version.py` | `0.11.0` → `0.12.0` |
| `boukensha/tasks/`, `prompts/system.md` | **deleted** — match Ruby, which ships neither this step |

`tool.py`, `message.py`, `registry.py`, `run_dsl.py`, `client.py`,
`errors.py`, `state.py`, `tools/shell.py`, `tools/mud.py`, `mud_manager/`,
`boukensha_loader.py`, `pyproject.toml` — zero diff from step 11's Ruby
reference, carried forward unchanged.

## Continuing decisions from step 11

- **Cooperative cancellation** (`cancel_event`/`TurnInterrupted`) is still
  our own addition, not in Ruby — kept exactly as step 11 built it, now
  also checked before the (also new) compaction step at the top of
  `Agent.run()`.
- **`Tui`'s active progress line still shows `self.repl.max_iterations`**,
  the real configured ceiling, not Ruby's hardcoded `Agent::MAX_ITERATIONS`
  constant — confirmed by diff that this Ruby display bug persists
  unchanged into step 12's `tui.rb`; this port continues deliberately
  diverging from it, per step 11's decision.

## Verification

No live API keys or MUD servers are available in this sandbox, so
verification uses fake in-process clients/registries and Textual's
official headless test harness (`App.run_test()`/`Pilot`), finishing with
a real network round-trip against `api.anthropic.com` using a fake key.

- **`models.py`**: known models resolve their context window; unknown
  models fall back to `DEFAULT_CONTEXT_WINDOW`.
- **`Context`**: `update_tokens` replaces vs. `add_turn_tokens`
  accumulates; `needs_compaction` boundary at exactly the threshold
  (849/1000 false, 850/1000 true); `compact_messages`'s drop formula at
  three boundaries (10 messages → drops 4; 3 messages → drops 1, clamped
  by `len-2`; 2 messages → drops 0, clamped at 0); `clear_messages` now
  also resets `current_tokens`.
- **`Agent`**: `max_iterations` alone trips the wrap-up path and makes
  exactly one extra (uncounted) call; `max_turn_tokens` alone trips after
  the cumulative spend crosses the ceiling; a pre-set `cancel_event`
  raises `TurnInterrupted` before any call is made; `_record_usage`
  accumulates `turn_tokens` but replaces `current_tokens`; compaction
  fires once at the top of `run()` when the context starts over
  threshold; multi-block text responses join with `"\n"`, not `""`.
- **Backends**: for each of the five, the reasoning round-trip
  (provider-native shape → normalized `reasoning` block → back to
  provider-native shape, or dropped where the API doesn't accept it back)
  and the trimmed `MODELS` tables. OpenAI additionally: `to_payload`'s
  full `/v1/responses` shape, `parse_response`'s three-way `output` item
  handling, and `to_input`'s `function_call_output`/`function_call` item
  shapes.
- **`Config`**: flat method defaults and `settings.yaml` overrides;
  `prompt_override.system` correctly selects the player-scoped prompt
  file; and directly proved the `system_override` quirk — flipping
  `tasks.player.prompt_override.system` to `false` while leaving
  `system.override: true` in place still falls back to the flat prompt,
  confirming the two properties read genuinely independent keys.
- **`Repl`**: `/compact` drops messages via `Context.compact_messages`,
  prints a confirmation, and does **not** emit a `Logger.compaction`
  event; `HELP` and `banner()` both mention it.
- **`Tui`**: `_ctx_color` boundaries at 70%/85% exactly; idle progress
  and status text reflect `usage_pct`/`current_tokens`/`context_window`
  live as the context changes; the `⚠` indicator appears only at ≥ 85%;
  a `compaction` event renders into the conversation log without the
  Rich-markup bracket-swallowing bug (step 11's `markup=False` fix on
  `RichLog` still holds); `/compact` submitted through the TUI's input
  box doesn't crash.
- **Loader integration**: built a `Tui` through the exact same
  construction path `boukensha.repl()` uses (`Config` → `Context` →
  `Registry` → backend → `PromptBuilder` → `Client` → `Logger` → `Repl` →
  `Tui`) and booted it headlessly; separately ran the real
  `bin/12_context --no-tui` launcher end-to-end against a scratch
  `BOUKENSHA_DIR`, confirming the banner shows `v0.12.0` and the new
  `/compact` line.
- **Live sanity check**: `boukensha.run()` with a fake Anthropic key,
  `working_dir=False`, `mud=False` — confirmed the request reaches
  `api.anthropic.com` for real and comes back as a `401`-driven
  `ApiError`, proving the full `Config`/`models.py`/`Context`/`Registry`/
  backend/`PromptBuilder`/`Client`/`Agent` pipeline is wired correctly
  end to end.

## Run

```bash
uv sync
../bin/12_context           # launches the textual TUI
../bin/12_context --no-tui  # plain REPL, no textual dependency exercised
```
