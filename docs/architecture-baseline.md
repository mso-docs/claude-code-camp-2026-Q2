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

Notes carried over from the port (not just a translation log — these are the
places Python's semantics genuinely differ from Ruby's, see each step's
README for detail):

- No string/symbol key duality in `Config`/`Base` — Python only has one
  string type, so the dual lookups in Ruby's `dig`/`fetch` collapse away.
- Ruby `Struct` → Python `@dataclass` for `Tool`/`Message`; `Context` stays a
  plain class in both languages (it has behavior, not just data).
