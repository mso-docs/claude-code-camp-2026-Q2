# 02 · The Tool Registry (Python port)

Python port of [`ruby/02_the_registry`](../../ruby/02_the_registry) — same
two jobs: store tools, dispatch tool calls by name. See that README for the
agent/registry dialogue diagram, which is unchanged conceptually here.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/registry.py` | `Registry` — registers tools and dispatches calls |
| `boukensha/errors.py` | `UnknownToolError` |

## Notable differences from the Ruby version

- **Registration is a decorator, not a `do...end` block.** Ruby's
  `registry.tool(name, description:) do |direction:| ... end` passes a block
  as the last argument to a method call. Python has no block-as-argument
  syntax, so the idiomatic equivalent is a decorator:
  ```python
  @registry.tool("move", description="...", parameters={...})
  def move(direction):
      return f"You move {direction} into a torch-lit corridor."
  ```
  Same effect — register a callable against a name — spelled the way Python
  actually writes "wrap this function and register it somewhere."
- **The string/symbol dispatch gotcha disappears entirely.** The Ruby README
  calls out that `dispatch` must convert string-keyed JSON args to
  symbol-keyed args (`args.transform_keys(&:to_sym)`) before calling the
  block, because Ruby keyword arguments require symbol keys. Python keyword
  arguments *are* string keys — `tool.block(**args)` just works with the
  JSON-shaped `{"direction": "north"}` dict directly. This isn't a
  simplification we chose; it's a case where the two languages' keyword-arg
  models don't share the same problem.

## Run

```bash
uv sync
../bin/02_the_registry
```
