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
