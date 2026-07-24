# Step 02 · The Tool Registry

**Ruby reference:** `week1_baseline/ruby/02_the_registry/`
**Python port:** `week1_baseline/python/02_the_registry/`
**Status:** Done

## Goal

A `Registry` that does two things: store tools against a `Context`, and
dispatch a `{name, args}` call to the right tool by name. Raises
`UnknownToolError` on an unrecognized name — no silent failures.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/registry.rb` | `boukensha/registry.py` | block-as-argument → decorator |
| `lib/boukensha/errors.rb` | `boukensha/errors.py` | `UnknownToolError` |
| everything from step 01 | carried forward unchanged |

## Design decisions

- Ruby's `registry.tool(name, description:) do |direction:| ... end` passes
  a block as the trailing argument — Python has no equivalent call syntax,
  so registration became a decorator: `@registry.tool("move", description=...)`
  above `def move(direction): ...`. Same "register this callable" shape,
  Python's actual spelling for it.
- Ruby's `dispatch` must convert string-keyed JSON args to symbol keys
  before calling a block with keyword args (`args.transform_keys(&:to_sym)`)
  — a documented gotcha in the Ruby README. Python keyword arguments already
  accept string keys, so `tool.block(**args)` just works on the JSON-shaped
  dict directly. Not a design choice — the two languages don't share this
  problem.

## Verification

Ran `examples/example.py` end to end (register `move`/`shout`, dispatch
both, dispatch an unregistered `flee`) — output matches the Ruby README's
"Expected Output" block exactly, including the caught `UnknownToolError`
message text.

## Outcome

Matches plan. See [`python/02_the_registry/README.md`](../../week1_baseline/python/02_the_registry/README.md).
