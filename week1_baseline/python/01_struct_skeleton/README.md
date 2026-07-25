# 01 · Struct Skeleton (Python port)

Python port of [`ruby/01_struct_skeleton`](../../ruby/01_struct_skeleton) — see
that README for the field-by-field description of `Tool`, `Message`, and
`Context`. `boukensha/config.py` and `boukensha/tasks/` are carried forward
unchanged from [`../00_config`](../00_config).

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/tool.py` | `Tool` — name, description, parameters, callable |
| `boukensha/message.py` | `Message` — role, content, tool_use_id |
| `boukensha/context.py` | `Context` — system prompt, messages, registered tools |

## Notable differences from the Ruby version

- Ruby's `Struct.new(:a, :b) { def to_s ... end }` → Python's `@dataclass`.
  A dataclass auto-generates `__init__` and equality the same way `Struct`
  does; both `to_s`/`__repr__` are hand-written here to match the Ruby
  output format exactly.
- Ruby's `attr_reader` on `Context` → plain public attributes in Python
  (`self.messages`, `self.tools`); there's no meaningful "private with a
  reader" distinction to preserve, so this is a real simplification, not
  just a syntax swap.
- `Context.README` documents a `token_budget` field and `budget=`/`used=`
  output that **doesn't exist in the actual Ruby code yet** — that's the
  README describing a later, fuller state of `Context`, not this step. The
  port stays faithful to the *code*, not the README's forward-looking
  examples.
- The example intentionally omits `default_prompts_dir` when resolving the
  system prompt, same as the Ruby example — so `system_prompt` can come back
  `None` here. It's carried forward unused (only `Config`/`Context`/`Tool`/
  `Message` reprs are printed), so it's harmless, but worth knowing that's
  not this port's bug — it's already true of the Ruby source.

## Run

```bash
uv sync
../bin/01_struct_skeleton
```
