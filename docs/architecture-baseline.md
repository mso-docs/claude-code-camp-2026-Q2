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
