# Porting Log: Ruby → Python, Step by Step

Thirteen steps (`00_config` through `12_context`), each with the same
rhythm: write a plan doc in [`docs/plans/`](../../plans/README.md) before
touching code (steps 00–03 were reconstructed retroactively — see each
plan's `Status`), port against the Ruby reference, verify, then fill in
the plan's `Outcome` section. One commit per step from `02_the_registry`
onward. Full detail for any step lives in its plan doc, linked below —
this is the condensed version.

## 00 · Configuration

`Config` resolves `.boukensha/` (`$BOUKENSHA_DIR` → `~/.boukensha`), loads
`.env` and `settings.yaml`. Ruby's string/symbol key duality for hash
lookups just doesn't exist in Python — one string type collapses it, a
real simplification rather than a translation. Verified against the Ruby
README's documented output, field-for-field. → [plan](../../plans/00_config.md)

## 01 · Struct Skeleton

Three core data shapes: `Tool`, `Message`, `Context`. Ruby's `Struct.new`
became `@dataclass` with a hand-written `__repr__` to match Ruby's output
string exactly. Deliberately ported what the Ruby *code* does, not what
the Ruby *README* describes (the README documents a `token_budget` field
that doesn't exist yet at this step). → [plan](../../plans/01_struct_skeleton.md)

## 02 · The Tool Registry

`Registry` stores tools and dispatches `{name, args}` calls by name,
raising `UnknownToolError` on an unrecognized one. Ruby's
block-as-trailing-argument tool registration (`registry.tool(name) do
|direction:| ... end`) became a decorator (`@registry.tool(name)`) — no
literal Python equivalent, same shape. → [plan](../../plans/02_the_registry.md)

## 03 · The Prompt Builder

`PromptBuilder` serializes `Context` for five pluggable backends
(Anthropic, OpenAI, Gemini, Ollama, OllamaCloud) without ever calling the
network itself. Found and preserved a real leaky-interface quirk in Ruby:
`to_messages` is called with one argument, which only works for
Anthropic/Gemini — OpenAI/Ollama/OllamaCloud need two. Never triggered in
practice because each backend calls its own `to_messages` internally with
the right arity — ported as-is rather than smoothed over.
→ [plan](../../plans/03_prompt_builder.md)

## 04 · The API Client

One HTTP call, no tool loop yet. Ruby's stdlib-only `net/http` maps to
Python's stdlib `urllib.request` — kept dependency-free on purpose, same
intent as the Ruby reference. The two languages diverge on control flow:
Ruby inspects the response object after the fact, Python's `urlopen`
*raises* on non-2xx, so the retry loop had to be restructured around
`try/except HTTPError`/`URLError` rather than a post-hoc status check.
Retry policy (codes, `MAX_RETRIES = 3`, backoff formula) ported 1:1.
Verified against local throwaway HTTP servers, since no live API key was
available. → [plan](../../plans/04_api_client.md)

## 05 · The Agent Loop

Where the agent actually does work: call, check for tool use, dispatch,
feed the result back, repeat until a final answer or an iteration
ceiling. The core design idea — every one of the five backends normalizes
its raw response into one shared shape (`{"stop_reason", "content": [...]}`)
so `Agent` itself never touches a provider-specific format, and the
reverse conversion has to work too when replaying history. Caught a real
Ruby-truthiness gotcha porting `max_output_tokens`: Ruby's nil-check would
have become a Python falsy-check, silently breaking an explicit `0`
setting — fixed with `is not None`. Verified via unit tests on all five
backends plus a real request against `api.anthropic.com` with a fake key,
confirming the 401 gets wrapped as `ApiError`. → [plan](../../plans/05_agent_loop.md)

## 06 · The Logger

Structured JSONL, one file per session, one phase per line. The trickiest
part wasn't the logger itself but where Ruby's module-level global state
(`Boukensha.config`/`.debug?`) could live in Python without a circular
import — solved with a dependency-free `boukensha/state.py` that both
`logger.py` and `__init__.py` import from. Also caught, only by re-reading
the Ruby diff after an initial pass: step 06 deletes *all* of step 05's
console output outright, relying on the JSONL file as the sole detailed
record — an easy thing to miss if you assume logging is purely additive.
→ [plan](../../plans/06_the_logger.md)

## 07 · The `Boukensha.run` DSL

One entry point hides all the manual wiring behind `Boukensha.run(task:) {
tool ... }`. Ruby's `instance_eval`'d block has no Python equivalent, so
tool registration became a callback function that receives the `RunDSL`
instance directly. Caught a subtle ordering bug before it shipped: the
`ensure`-equivalent (`logger = None` before the `try`, not just around the
final call) has to guard against a failure *before* the logger even
exists. → [plan](../../plans/07_the_run_dsl.md)

## 08 · The REPL Loop

`Boukensha.repl` — same shape as `run()`, but an interactive loop with
history that survives across turns. Notable finding: the Ruby README's
claim that this step adds a `Logger#turn` banner print is simply false —
diffing `logger.rb` shows zero changes; the banner comes from `Repl`
itself. `Agent` now persists its final reply in three separate places
(normal end-turn, successful wind-down, and the wind-down error-fallback
path) — easy to add to the first and miss the other two.
→ [plan](../../plans/08_the_repl_loop.md)

## 09 · Global Executable

Packages Boukensha so a `boukensha` command resolves which step's code to
run (`$BOUKENSHA_PATH` → `~/.boukensharc` → bundled default) — orthogonal
to `$BOUKENSHA_DIR`, which resolves *config*, not *code*. This step's
Ruby snapshot quietly regresses three things step 08 had fixed (the
friendly 401 message, the project-local `.boukensha/` config tier, the
rich REPL banner), with nothing in the README explaining why. Decision:
carry step 08's working versions forward instead of reproducing the
regression — flagged prominently rather than silently diverging.
→ [plan](../../plans/09_global_executable.md)

## 10 · A Standard Tool Library

Built-in tools out of the box: `Tools::FileSystem` (6 sandboxed tools),
`Tools::Shell` (1, with an allow-list and timeout), and `Tools::Mud` (26
CircleMUD gameplay tools) — the last of which required porting
`mud_manager` first, a threaded telnet client with its own login state
machine and IAC byte-stripping, ported byte-for-byte rather than
rewritten. The biggest step in the port up to this point. Verified
against fake TCP servers, since no live MUD server was reachable from the
sandbox. → [plan](../../plans/10_standard_tool_library.md)

## 11 · A Terminal UI

A real architectural translation, not a mechanical port: Ruby's `Tui` runs
on `bubbletea` (Go, via FFI); the Python port uses `textual`
(asyncio/widget-based) to the same visual effect. Esc-to-interrupt became
cooperative cancellation (a `threading.Event` checked at each loop
iteration boundary) rather than Ruby's forced thread-kill, since Python
has no safe equivalent. Caught a real bug via Textual's headless test
harness: the conversation log had `markup=True`, so literal
`"[interrupted]"` text was parsed as an unmatched Rich style tag and
silently vanished. → [plan](../../plans/11_tui.md)

## 12 · Context Management

The largest step in the whole port. Headline change: Ruby drops the
`Tasks::Base`/`Tasks::Player` abstraction entirely in favor of flat
`Config` methods — so this step deletes `boukensha/tasks/` from the
Python port too, after carrying it since step 00. Adds real token
accounting (`context_window` vs. actual usage), color-coded 70%/85%
warnings, automatic pre-turn compaction, a manual `/compact`, a second
circuit breaker (`max_turn_tokens`), normalized "reasoning" blocks across
all five backends, and a full OpenAI rewrite from `/v1/chat/completions`
to `/v1/responses`. The Ruby README covers roughly a third of what
actually changed; the rest surfaced only by diffing every file against
step 11. Closes out with all of `ruby/00`–`12` now having an independently
verified `python/` counterpart. → [plan](../../plans/12_context.md)

## Working Method

Plan before porting, diff before trusting a README claim or an
"unchanged" label, and when the reference and the pedagogically better
choice disagree without explanation (see [reference-quirks](reference-quirks.md)),
say so in the plan rather than silently picking one.
