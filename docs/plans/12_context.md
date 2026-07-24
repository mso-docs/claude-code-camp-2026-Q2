# Step 12 · Context Management

**Ruby reference:** `week1_baseline/ruby/12_context/`
**Python port:** `week1_baseline/python/12_context/`
**Status:** Planned

## Goal

Proper token accounting: the model's real context-window ceiling
(`context_window`) tracked separately from actual usage (`current_tokens`,
from the last response's `input_tokens`); color-coded warnings in the
TUI/status bar at 70%/85% usage; automatic compaction when a turn starts
over threshold; a manual `/compact` command. Also (not mentioned in the
Ruby README, found only by diffing): normalized "reasoning" content
blocks across all 5 backends, a second circuit breaker (`max_turn_tokens`
alongside `max_iterations`), and the OpenAI backend's move from
`/v1/chat/completions` to `/v1/responses`.

This is the largest step in the whole port — larger than step 10. The
Ruby README (85 lines) covers maybe a third of what actually changed;
the rest was found only by diffing every file against step 11, which is
now the standing practice for every step in this port, not a one-off.

## The headline structural change: the Tasks abstraction is gone

`Tasks::Base`/`Tasks::Player` — which we've carried since step 00,
through all 12 prior Python steps — **do not exist in this step's Ruby
reference at all**. No `lib/boukensha/tasks/` directory, no requires for
it, confirmed by grepping the entire step for `Tasks::`/`task_settings`
(zero matches). `Config` now exposes flat, direct methods instead:
`provider_type`, `model`, `agent_max_iterations`, `agent_max_output_tokens`,
`agent_max_turn_tokens` (new), `agent_compaction_threshold` (new), and a
`system_prompt` computed once at construction and cached.

**The `settings.yaml` schema itself is unchanged** — `provider_type` still
reads `dig(:tasks, :player, :provider)`, `model` still reads
`dig(:tasks, :player, :model)`. Only the Ruby *code path* collapsed from
"look up the player task's settings, hand them to `Tasks::Player`" to
"`Config` answers directly." Every scratch `settings.yaml` used in prior
steps' verification remains valid here unchanged.

**Python-side consequence**: `boukensha/tasks/` (the whole directory —
`base.py`, `player.py`, `__init__.py`) is deleted in this step's port, not
carried forward. `Agent` and `Repl` both lose their `task_settings`
parameter; `Context` loses its `task` parameter entirely.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/models.rb` (`Models`) | `boukensha/models.py` | new — static model→context_window table |
| `lib/boukensha/context.rb` | `boukensha/context.py` | major rewrite — see below |
| `lib/boukensha/agent.rb` | `boukensha/agent.py` | major rewrite — dual circuit breakers, compaction, reasoning |
| `lib/boukensha/config.rb` | `boukensha/config.py` | major rewrite — Tasks abstraction collapsed into flat methods |
| `lib/boukensha/logger.rb` | `boukensha/logger.py` | major simplification (cost/task tracking **removed**) + 3 new event types |
| `lib/boukensha/repl.rb` | `boukensha/repl.py` | `/compact` command, `max_turn_tokens`, `task_settings` removed |
| `lib/boukensha/tui.rb` | `boukensha/tui.py` | color-coded context %, compaction event display |
| `lib/boukensha/backends/*.rb` (all 6) | `boukensha/backends/*.py` | reasoning-block normalization everywhere; OpenAI rewritten to `/v1/responses` |
| `lib/boukensha.rb` | `boukensha/__init__.py` | `context_window:` replaces nothing (new), Tasks removed, `mud_opts_from_config` unchanged |

`errors.rb`, `client.rb`, `run_dsl.rb`, `registry.rb`, `message.rb`,
`tool.rb`, `boukensha_loader.rb`, all 3 `tools/*.rb` have **zero diff**
from step 11 — carried forward unchanged. No `prompts/` directory is
shipped with this step at all (see below) — carried forward as *absent*,
not copied.

## Design decisions — `Context`

`Context.new(system:, context_window: 200_000, working_dir: nil,
compaction_threshold: 0.85)` — no `task:` param. New state:
`current_tokens` (mutable, window pressure from the last response),
`turn_tokens` (cumulative input+output spend *this turn*, distinct
concept — reset at turn start via `reset_turn_tokens`, accumulated via
`add_turn_tokens`). `usage_fraction`/`usage_pct`/`needs_compaction?` are
straightforward. `compact_messages!` drops the oldest 40% of messages
(keeping at least 2, matching Ruby's `[(size * 0.40).ceil, size - 2].min`
clamped to `>= 0`) and resets `current_tokens` to 0 — the next response
will report the real post-compaction size. `clear_messages!` also now
resets `current_tokens` (it didn't need to before, since nothing tracked
window pressure).

## Design decisions — `Agent`

**Two independent circuit breakers, evaluated in order at the top of the
loop**: `max_iterations` (as before) and new `max_turn_tokens` (checked
against `context.turn_tokens`, 0/None = disabled) — whichever trips first
triggers wind-down. `Agent.__init__` no longer resolves anything from
`task_settings` — every limit is now a plain constructor argument the
caller (`boukensha.run()`/`repl()`) resolves from `Config` up front and
passes in directly; `Agent` just does `int(max_iterations or
MAX_ITERATIONS)`.

**`run()` compacts *before* the loop starts**, not reactively mid-turn:
`context.reset_turn_tokens()` then `compact_if_needed()` (checks
`context.needs_compaction?()`, and if so calls `compact_messages!()` and
logs a `compaction` event) both happen once, up front.

**`record_usage(response)` updates two different things from one
response**: `context.add_turn_tokens(input, output)` (spend, cumulative)
*and* `context.update_tokens(input)` (window pressure, replaces — not
adds to — the previous value, since `input_tokens` on any given response
already reflects the *entire* replayed history, not a delta). Called after
every response, including the wind-down call (whose tokens still count
toward the turn total, unlike step 11 where the wind-down call was
untracked).

**`extract_text` now joins with `"\n"`, not `""`.** A real behavior
change from every prior step (`content.select { |b| b["type"] == "text"
}.map { |b| b["text"] }.join("\n")`) — multi-block text responses now get
newline-separated instead of concatenated directly. Easy to carry forward
silently as "no change" since the surrounding code looks identical;
confirmed by diffing character-by-character, not by assuming.

**Reasoning blocks get their own logging path**, separate from
`handle_tool_calls`'s existing preamble-text handling: `log_reasoning`
iterates normalized content for `{"type": "reasoning", ...}` blocks and
emits one `Logger.reasoning(text:, redacted:)` event each (skipping empty
non-redacted blocks — a redacted block still logs, since it tells the
viewer "thinking happened here" even with no visible text). Preamble text
accompanying a tool call now logs via a new `Logger.plan(text:)` event
instead of being folded into the `response` event's text — a real
restructuring of what gets logged where, not just an addition.

## Design decisions — `Config`

Flat methods replace the whole `Tasks` layer. `system_prompt` is computed
**once, eagerly, at `Config.__init__`** (not lazily per-call like every
prior step's `Tasks::Base.system_prompt`), and — real behavior change —
**there is no package-shipped default `prompts/system.md` fallback
anymore**. Every step 00–11 had one; this step's Ruby directory ships no
`prompts/` at all, and `Config#load_system_prompt` only ever looks inside
the user's own `.boukensha/` directory (`prompts/player/system.md` when
`tasks.player.prompt_override.system` is true, else `prompts/system.md`),
returning `None` if neither exists. Not shipping a `prompts/` directory in
this step's Python port either, to match — a scratch settings dir used for
testing without a custom system prompt will legitimately get `system=None`,
which `Context` already accepts fine.

**A genuine quirk, not just unused-but-consistent: `system_override?` is
dead *and* checks the wrong key.** It reads `dig(:system, :override)`,
but `load_system_prompt` (the method that actually resolves the prompt)
independently checks `dig(:tasks, :player, :prompt_override, :system)` —
a different path entirely. `system_override?` is never called anywhere.
Reads like an abandoned half-step toward flattening settings.yaml further
that was never finished, left behind when the surrounding refactor
happened. Porting `system_override?` for structural parity (matching the
pattern for every other dead method this port has kept, e.g. `LoopError`)
while documenting that it's not just unused but *inconsistent* with the
code path that actually matters.

## Design decisions — `Logger`

**Cost/task/provider tracking is removed, not just simplified.**
`response()` drops `task:`/`backend:` entirely — no more
`execution_metadata`, `task_name`, `provider_name` (the very method whose
`OpenAI → open_ai` mismatch we documented as a quirk in step 06), 
`usage_tokens`, `first_integer`, or `estimate_cost`. This deletes the
OpenAI provider-name quirk's only call site along with it — noting this
so a reader of the step 06 README isn't confused about where that logic
went. Three new event methods: `compaction(before:, dropped:,
context_window:)`, `reasoning(text:, redacted:)`, `plan(text:)`.
`prompt()` gains a `context_window:` field.

## Design decisions — backends

**All 6 backend files touched** (`base.rb` only gains a doc comment — no
functional change). Every parser now normalizes provider-specific
"thinking" output into `{"type": "reasoning", "text":, "signature":?,
"redacted":?}` blocks, ordered first in `content` (matching Anthropic's
native ordering): Anthropic's `thinking`/`redacted_thinking` blocks
(signature preserved for round-tripping — the API rejects a modified
thinking block on continuation), Gemini's `part["thought"]` parts
(`thoughtSignature` preserved the same way), Ollama/OllamaCloud's flat
`message["thinking"]` string (no signature concept — dropped, not
echoed back, when rebuilding assistant turns). OpenAI's Responses API has
its own `"reasoning"` output-item type with a `summary[]` array joined
into text, also dropped (not echoed back) on reassembly since gpt-5.x with
`reasoning: {effort: "none"}` doesn't need it round-tripped.

**Anthropic's `content` array is no longer a pure passthrough.** Every
step through 11 noted "Anthropic's content array doubles as both the
normalized shape and the wire format, so it needs no reverse conversion"
— that's no longer fully true. Text/tool_use blocks still pass through
unchanged, but a stored `reasoning` block now needs converting back to
Anthropic's native `thinking`/`redacted_thinking` shape via a new
`assistant_content`/`denormalize_block`, since a plain "reasoning" block
isn't valid to send back as-is.

**OpenAI: a genuine full rewrite, not a modification** — `/v1/chat/completions`
→ `/v1/responses`. Messages become `input` items (`flat_map`, since a
`tool_result` now expands to one `function_call_output` item and an
assistant turn can expand to multiple items); the system prompt moves
from an injected `{role: "system"}` message to a top-level `instructions`
string; tool defs drop the `function:` wrapper (flat, not nested); tool
results match by `call_id` instead of `tool_call_id`; the response is
parsed from an `output[]` array of typed items (`"reasoning"` /
`"message"` / `"function_call"`) instead of `choices[0].message`.
`reasoning: {effort: "none"}` is sent explicitly in every payload.

**Gemini and Ollama-family MODELS tables were trimmed** to 2–3 entries
each (from 5 and 9 respectively) — Ollama down to a single model
(`gemma4:e4b`). A commented-out, currently-unreachable
`gemini-3.1-pro-preview-customtools` entry left a dead branch in
`thinking_config`'s `case` statement (unreachable since model validation
would reject that model id before `thinking_config` is ever called).
Porting the trimmed tables and the dead branch faithfully — not
expanding the tables back out with entries the reference dropped, and not
pruning the unreachable branch either, matching this port's standing
practice of preserving quirks rather than "helpfully" cleaning them up.

## Design decisions — `Repl`/`Tui`

**`/compact`** — new REPL command, calls `context.compact_messages!()`
directly and reports the drop count. Notably does **not** emit a
`Logger.compaction` event the way the *automatic* pre-turn compaction
does (only `Agent.compact_if_needed` logs) — an asymmetry in the Ruby
reference, ported as-is rather than "fixed" to be consistent, since
there's no way to know whether that's deliberate (manual compaction is a
user-initiated action already visible in the transcript) or an oversight.

**Tui's idle progress line and status bar now read `context.current_tokens`/
`context.context_window`/`context.usage_pct` directly**, replacing the
`@session_input_tokens`/`@session_output_tokens` running sums Tui tracked
itself in step 11 — a real shift in what "ctx" means on screen (window
pressure now, not a cumulative session total). The *active* (mid-turn)
progress line's `turn_input_tokens`/`turn_output_tokens` accumulation is
unchanged. Color coding: grey/dim under 70%, yellow 70–84%, red ≥85%
(both progress line and status bar), plus a `⚠` in the status bar at
≥85%. **Continuing this port's step-11 decision to show the real
configured `max_iterations`, not Ruby's hardcoded `Agent::MAX_ITERATIONS`
constant** — the *active* progress line in Ruby's step 12 `tui.rb` still
has this same latent bug (confirmed by diff — unchanged from step 11),
so the same fix carries forward for the same reason.

## Verification plan

- `Models.context_window`: known models return their table value, unknown
  models fall back to `DEFAULT_CONTEXT_WINDOW`.
- `Context`: `usage_fraction`/`usage_pct`/`needs_compaction?` at the 70/85%
  boundaries; `compact_messages!`'s drop-count formula against several
  message-count sizes (including the "keep at least 2" floor); confirm
  `current_tokens` resets to 0 after both `compact_messages!` and
  `clear_messages!`.
- `Agent`: both circuit breakers independently (max_iterations trips
  without max_turn_tokens configured, and vice versa — reusing the
  step-05-style fake-client harness); pre-turn auto-compaction firing
  when a fake context starts over threshold, confirmed via the logged
  `compaction` event; `record_usage` updating both `turn_tokens` (additive)
  and `current_tokens` (replacement, not additive) correctly, including
  during the wind-down call; `log_reasoning` emitting one event per
  reasoning block and skipping empty non-redacted ones.
- Each backend's reasoning-block round trip: Anthropic
  `thinking`/`redacted_thinking` ↔ `reasoning` (signature preserved both
  ways), Gemini `thought`/`thoughtSignature` ↔ `reasoning`, Ollama's flat
  `message.thinking` → `reasoning` (one-way — confirm it's correctly
  *not* echoed back), OpenAI's `output[].reasoning.summary[]` → `reasoning`
  (also one-way).
- OpenAI backend specifically: the full `/v1/responses` payload shape
  (`instructions`, flat `input` items, `function_call_output` by
  `call_id`, flat tool defs, `reasoning: {effort: "none"}`), and
  `parse_response` against a captured-shape `output[]` array covering all
  three item types in one response.
- `Config`: `provider_type`/`model` reading the same nested
  `tasks.player.*` keys as every prior step (confirming settings.yaml
  compatibility); `system_prompt` resolution (override file present,
  fallback file present, neither present → `None`) computed once at
  construction; all four `agent_*` methods' defaults and override values;
  confirm `system_override?` is importable but reads a different key path
  than what's actually used, matching the documented quirk.
- `Repl`: `/compact` drops messages and reports the count, with no
  `Logger.compaction` event (confirming the asymmetry against automatic
  compaction, not just assuming it).
- `Tui`: color transitions at the 70%/85% boundaries on both the idle
  progress line and the status bar, the `⚠` indicator's threshold, and the
  `compaction` event rendering `[context compacted — N messages dropped
  to free space]` in the conversation view.
- End-to-end: the same live-API sanity check as every step since 05 (a
  real request against `api.anthropic.com` with a fake key), this time
  also confirming `context_window` gets sized via `Models.context_window`
  *before* the backend is constructed (the actual reason `Models` exists
  as a separate static table instead of just asking the backend).

## Outcome

_(fill in after implementation)_
