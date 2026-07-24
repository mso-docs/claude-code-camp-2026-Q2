# Baseline Agent Architecture (Python port)

Living diagram for the `week1_baseline/python/` port, updated after each step
lands. Ruby reference: [`week1_baseline/ruby/ITERATIONS.md`](../week1_baseline/ruby/ITERATIONS.md).

## Step 00 · Configuration

```
┌─────────────┐
│   Config    │  dir resolution: $BOUKENSHA_DIR or ~/.boukensha
│             │  loads .env (python-dotenv) + settings.yaml (pyyaml)
└──────┬──────┘
       │ tasks("player") → settings dict
       ▼
┌─────────────┐
│ Tasks.Base  │  .provider() .model() .system_prompt()
│ Tasks.Player│  (task_name = "player")
└─────────────┘
```

## Step 01 · Struct Skeleton

```
┌─────────────┐        ┌──────────────┐
│   Config    │        │     Tool     │  name, description, parameters, block
└──────┬──────┘        └──────────────┘
       │ system_prompt        ▲
       ▼                      │ register_tool()
┌─────────────────────────────┴──────┐
│               Context               │  system, messages[], tools{}
│  add_message(role, content)         │
└──────────────┬───────────────────────┘
               │ append
               ▼
        ┌──────────────┐
        │   Message    │  role, content, tool_use_id
        └──────────────┘
```

## Step 02 · The Tool Registry

```
        ┌────────────┐  tool(name, desc, params)   ┌─────────────┐
Agent → │  Registry  │ ───────────────────────────▶ │   Context   │
(future)│            │  register_tool()             │  tools{}    │
        └─────┬──────┘                              └─────────────┘
              │ dispatch(name, args)
              ▼
     look up tools[name] → tool.block(**args)
              │
              ▼ (name not found)
     raise UnknownToolError
```

The agent never calls a tool directly — it will emit a `{name, args}`
request and the Registry resolves + runs it. No agent loop exists yet to
produce that request; step 02 still calls `registry.dispatch(...)` by hand.

Notes carried over from the port (not just a translation log — these are the
places Python's semantics genuinely differ from Ruby's, see each step's
README for detail):

- No string/symbol key duality in `Config`/`Base` — Python only has one
  string type, so the dual lookups in Ruby's `dig`/`fetch` collapse away.
- Ruby `Struct` → Python `@dataclass` for `Tool`/`Message`; `Context` stays a
  plain class in both languages (it has behavior, not just data).
- Ruby's `registry.tool(...) do |args| end` (block-as-argument) → Python's
  `@registry.tool(...)` decorator — same "register this callable" shape,
  different syntax for passing a function into a method call.
- Ruby's `dispatch` must convert JSON's string-keyed args to symbol keys
  before calling a block with keyword args; Python keyword args already
  accept string keys, so that translation step doesn't exist in the port.

## Step 03 · The Prompt Builder

```
                 ┌─────────────┐
                 │   Context    │  system, messages[], tools{}
                 └──────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │ PromptBuilder │  to_api_payload() / headers() / url()
                 └──────┬────────┘
                         │ delegates to whichever backend is configured
        ┌────────┬───────┼────────┬──────────────┐
        ▼        ▼       ▼        ▼              ▼
   Anthropic   OpenAI  Gemini   Ollama      OllamaCloud
   (backends/base.py: model validation, context_window, cost estimate — shared)
```

Each backend owns its own `MODELS` table and wire format (system prompt
placement, tool-result wrapping, role naming — see the step's README for the
full comparison). `PromptBuilder` never touches the network; it only builds
the payload dict.

Additional notes for this step:

- Ruby's dual `self.model_info(model)` (class method) / `model_info`
  (instance method) — legal in Ruby because class and instance methods
  don't share a namespace — became `lookup_model_info` (classmethod) +
  `model_info` (instance attribute) in Python, since Python doesn't have
  that separation.
- Carried a Ruby quirk forward rather than fixing it: `PromptBuilder.to_messages()`
  only works with backends whose `to_messages` takes one argument
  (Anthropic, Gemini). OpenAI/Ollama/OllamaCloud need `(system, messages)`.
  Never triggered in practice — `to_api_payload()` is the only method the
  example calls, and each backend's own `to_payload` invokes `to_messages`
  correctly internally.

## Step 04 · The API Client

```
┌───────────────┐
│ PromptBuilder │  to_api_payload() / headers() / url()
└──────┬────────┘
       │
       ▼
┌───────────────┐   POST (urllib.request, stdlib)   ┌─────────────┐
│    Client     │ ─────────────────────────────────▶ │  LLM API    │
│  retry loop   │ ◀───────────────────────────────── │ (any backend)│
└──────┬────────┘        HTTPError / URLError         └─────────────┘
       │ raises ApiError after MAX_RETRIES, else returns parsed JSON
       ▼
  raw response dict (shape differs per backend — see step README)
```

No tool-calling loop yet — this step proves the round trip works. That's
step 05.

Additional notes for this step:

- Ruby's `Net::HTTP` returns a response object for any status code; Python's
  `urllib.request.urlopen` raises `HTTPError` for non-2xx instead. The retry
  loop is restructured around `try/except HTTPError` (status-code-driven
  retry) plus `try/except` on connection-level errors (`URLError` and
  friends), rather than Ruby's single post-request status check.
- Ruby's `net/http` needed a documented SSL CA-file workaround for
  Linux/WSL2 portability. Python's `urllib.request` builds its default SSL
  context automatically per-request and needed no equivalent workaround.

## Step 05 · The Agent Loop

```
                     ┌─────────────┐
              ┌─────▶│    Agent    │  run(): loop until end_turn or
              │      │             │  max_iterations, then wind-down
              │      └──────┬──────┘
              │             │ client.call() → builder.parse_response()
              │             ▼
              │   {stop_reason, content[]}   ◀── normalized shape, same
              │             │                    for all 5 backends
              │   tool_use? │ end_turn?
              │     ┌───────┴───────┐
              │     ▼               ▼
              │  Registry      extract_text(content)
              │  .dispatch()   → return final answer
              │     │
              │     ▼
              │  context.add_message("tool_result", ...)
              └─────┘ (loop back for next client.call)
```

Every backend implements `parse_response()` (raw response → normalized
shape above) and, for 4 of 5, a reverse `_assistant_message`/`_assistant_parts`
(normalized shape → that provider's own wire format, used when replaying a
stored assistant `Message` whose `.content` is now a list of blocks instead
of a plain string). Anthropic's wire format already *is* the normalized
shape, so it skips the reverse step.

Additional notes for this step:

- OpenAI's tool-call `arguments` are a JSON string in both directions
  (`json.dumps`/`json.loads`); every other backend uses a plain dict.
- Tool call IDs aren't universal: Anthropic/OpenAI assign one, Ollama/
  OllamaCloud/Gemini reuse the tool name as the id on both the call and its
  matching result.
- A real Ruby-truthiness trap avoided on purpose: Ruby's
  `@max_output_tokens ? ... : ...` is a nil-check where `0` is truthy; a
  literal Python `if self.max_output_tokens:` would wrongly treat an
  explicit `0` as absent. Used `is not None` to match Ruby's actual
  behavior.
- `LoopError` is defined (for parity with the Ruby reference) but never
  raised in either language — the wind-down mechanism replaced it.
- The wind-down call runs *outside* the counted loop (can't re-trigger
  itself) and falls back to a deterministic message if it raises `ApiError`.

## Step 06 · The Logger

```
┌─────────────┐  session_start/iteration/prompt/tool_call/    ┌──────────────┐
│    Agent    │  tool_result/response/limit_reached/turn_end  │    Logger    │
│             │ ─────────────────────────────────────────────▶│              │
└─────────────┘                                                └──────┬───────┘
                                                                        │ one JSON
                                                                        │ object/line
                                                                        ▼
                                                     .boukensha/sessions/<id>.jsonl

┌──────────────┐   config() / is_debug() / is_quiet()   ┌──────────────┐
│ boukensha.   │◀─────────────────────────────────────── │   Logger     │
│ state        │   (memoized Config singleton; debug     │ (default dir,│
│ (new module) │    flag gates the raw() event)          │  raw gating) │
└──────────────┘                                          └──────────────┘
```

`state.py` exists only to break a circular import `__init__.py` would
otherwise have with `logger.py` (see the step's README) — Ruby's
single-file module doesn't have this problem because `require` doesn't
evaluate cross-references until call time.

Additional notes for this step:

- All of step 05's console `puts`/`print` output is gone from `Agent` in
  this step — replaced entirely by the JSONL log, not supplemented by it.
- New behavior, not just a port: a raised exception from a tool no longer
  crashes the agent — it becomes an `"ERROR: ..."` tool result fed back to
  the model, logged with `ok: false`.
- A real quirk carried forward: the logged `provider` field is derived
  from the backend's class name, and `OpenAI` → `open_ai` doesn't match
  the actual `settings.yaml` key `openai` — every other backend's derived
  name does match its config key.
- Python's default-argument trap avoided: `Agent`'s `logger` default is
  constructed inside `__init__`, not as `logger=Logger()` in the
  signature — the latter would share one `Logger` (and file) across every
  `Agent` that omits it.

## Step 07 · The `boukensha.run` DSL

```
caller ──▶ boukensha.run(task=, block=configure)
              │
              ├─ state.config()  ──▶  tasks.player.{provider,model,system,...}
              │                       (defaults; any kwarg overrides)
              ├─ Context + Registry
              ├─ block(RunDSL(registry))   ◀── caller's tool registrations
              │
              ├─ backend / PromptBuilder / Client / Logger / Agent
              │  (exactly the manual wiring from steps 02-06, assembled here)
              │
              ├─ ctx.add_message("user", task)
              └─ agent.run()  ──▶  return final text
                    finally: logger.close()   (logger may be None if setup
                                                failed before it was built)
```

One call replaces the ~20 lines of manual plumbing every prior step
required. Additional notes for this step:

- Ruby's `do...end` block with `instance_eval` (rebinding `self` to
  `RunDSL`) has no Python equivalent — `run()` takes a `block` callable
  that receives the `RunDSL` instance directly instead. Same shape
  ("describe tools, hand them to run"), different spelling.
- `run()` deliberately reuses the process-wide `state.config()` singleton
  rather than constructing a fresh `Config()`, matching Ruby's
  `Boukensha.config` — the same instance `Logger`'s default session
  directory reads from.
- `Logger` gains `turn()` and `subscribe()` in this step, unused by it —
  forward-looking for a later TUI step's live progress display.
- Two dead-code items (`Config.mud_*`, `errors.LoopError`) that were
  dropped in step 06's Ruby snapshot are back in step 07's — snapshot
  drift between the per-step reference directories, not a design change.
  Restored to match, still unused.

## Step 08 · The REPL Loop

```
caller ──▶ boukensha.repl(block=configure)
              │  (same setup as run(), deliberately duplicated not shared —
              │   Ruby doesn't factor it out either)
              ▼
        Repl(context, registry, builder, client, logger, ...).start()
              │
              ▼ loop, reading sys.stdin.readline()
     ┌────────┴─────────────────────────────────────┐
     │ /exit /quit /help /quiet /loud /clear         │  built-in commands,
     │ (handled by Repl, never reach the agent)      │  not sent to the model
     └────────┬───────────────────────────────────────┘
              │ anything else
              ▼
     context.add_message("user", input)
     agent = Agent(context, registry, builder, client, logger, ...)  ◀── fresh
     agent.run()                                                        each turn
              │
              ▼
     print(result)   (unconditional — Agent itself prints nothing)
              │
              └─▶ loop back to prompt (context carries history forward)
```

`Agent.run()` now also does `context.add_message("assistant", text)` right
before returning, in all three of its return paths (normal `end_turn`,
successful wind-down, `ApiError`-fallback wind-down) — the change that
actually makes cross-turn history possible; before this step the final
reply was returned but never stored.

Additional notes for this step:

- The Ruby README's claim that `Logger#turn` prints a `╔══ turn N ══╗`
  banner is simply false — `logger.rb` has zero diff from step 07 and
  `turn()` still only writes JSONL. The banner, if any, is `Repl`'s job.
  Caught by diffing rather than trusting the README — worth remembering.
- `Config`'s dir resolution gains a real third tier: a `.boukensha/` in
  the current working directory (if it exists) now outranks `~/.boukensha`,
  though `$BOUKENSHA_DIR` still overrides both.
- `/quiet`/`/loud` toggle real global state that nothing currently reads —
  ported faithfully, flagged so the no-visible-effect isn't mistaken for a
  bug.
- EOF handling needed `sys.stdin.readline()` (returns `""` at true EOF)
  rather than `input()` (raises `EOFError`), to match Ruby's
  `$stdin.gets` → `nil` pattern.

## Step 09 · Global Executable

```
$PATH  ──▶  boukensha  (console-script shim, from [project.scripts])
                │
                ▼
        boukensha_loader.main() → load_and_start_repl()
                │
                ▼ resolve():
     1. $BOUKENSHA_PATH env var  (explicit override)
     2. ~/.boukensharc file      (persistent default, one path)
     3. bundled step (this one)  (fallback)
                │
                ▼
     sys.path.insert(0, step_dir); sys.modules.pop("boukensha", None)
     boukensha = import_module("boukensha")
                │
        has `repl`?  ──no──▶  friendly abort: "run its examples directly"
                │yes
                ▼
          boukensha.repl()
```

Packaging plumbing, not agent-architecture logic — the only genuinely new
code is the loader's 3-tier resolution and the `pyproject.toml`
console-script entry point. Notes:

- This step's Ruby snapshot regresses three things step 08 added (friendly
  `401` message, CWD `.boukensha/` config tier, richer REPL banner) with
  no explanation and no stated scope touching those files — the Python
  port keeps step 08's versions rather than replicating the regression.
- `sys.modules.pop("boukensha", None)` before each import is what makes
  switching between step directories in one process actually work —
  without it, a second `import boukensha` would silently return whatever
  was cached from the first path.
- Verified against a real built-and-installed wheel (`uv build` +
  `uv tool install .`), not just library-level calls — including the
  hatchling packaging gotcha where a standalone top-level module needed
  `force-include`, not `include`, to actually end up in the wheel.

## Step 10 · A Standard Tool Library

```
boukensha.run(task=, working_dir=, allowed_commands=, shell_timeout=, mud=, block=)
     │
     ├─ working_dir (default: os.getcwd(), resolved per-call) ──▶ file_system.register()
     │                                                             shell.register()
     ├─ mud: False→skip │ None→Config.mud_* │ dict→as given ──▶ mud_tools.register()
     │                                                             │
     │                                                             ▼
     │                                                   mud_manager.Session (persistent,
     │                                                   auto-connects at registration)
     │                                                             │
     │                                                    threading.Thread reader ──▶
     │                                                    buffer (threading.Condition) ──▶
     │                                                    IAC-stripped text
     │
     └─ block(RunDSL(registry))   ◀── caller's own tools, registered last
```

`ITERATIONS.md` (this repo's own doc) claims steps 10–12 replace all this
with an MCP host — confirmed false by grepping every `.rb` file in
`week1_baseline/ruby/`, zero matches. What's actually here is the original
built-in tool modules; ported accordingly. `mud_manager` (threaded telnet
client + ~50 CircleMUD command builders) had no prior Python port and was
built from scratch from `week0_explore/mud_manager/`.

Notes:

- Ruby's `Mutex`+`ConditionVariable` → Python's single `threading.Condition`.
- Ruby's `:return`/`:enter` symbol sentinel ("send a bare Enter") → Python's
  `None` — no symbols in Python, and `None` is the natural "no value."
- A real naming collision: `run()`/`repl()`'s `mud=` parameter would shadow
  a bare `from .tools import mud` — aliased to `mud_tools` on import. Ruby
  never hits this since `Tools::Mud` (capitalized) and a local `mud`
  variable are different identifiers there.
- `working_dir`'s `os.getcwd()` default is resolved inside the function
  body, not as a signature default — same class of bug as step 06's
  `Agent(logger=Logger())` trap, since a signature default is evaluated
  once at definition time and would freeze the cwd.
- No live CircleMUD server in this sandbox — `mud_manager.Session` and
  `tools.mud` verified against fake TCP servers built for this step,
  including real IAC negotiation bytes mixed into a login sequence.
