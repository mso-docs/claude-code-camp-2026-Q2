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

## Ruby build checklist (reference)

This is the course's checklist for building `ruby/02_the_registry` itself
(not a Python-port checklist — this repo had no Python-track checklist for
02). Checked retrospectively against the pre-existing `ruby/` tree, since it
was already fully built before this port started.

**1. Add the Registry Iteration**
- [x] 1.1 `week1_baseline/ruby/02_the_registry` exists with content
- [~] 1.2 Review the changes in README.md — can't verify a past action; the README exists and documents the changes, and I read it while planning the Python port
- [x] 1.3 No unwanted `Zone.Identifier` files anywhere in `week1_baseline/ruby`

**2. Review the Registry** — understanding checks, not artifacts; the code and its behavior were reviewed while writing the Python port (see this plan's Design decisions)

**3. Run the Example**
- [ ] 3.1 Runner at `week1_baseline/bin/ruby/02_the_registry` — **doesn't exist**. No top-level `week1_baseline/bin/` exists at all; the actual runner lives at `week1_baseline/ruby/bin/02_the_registry` instead. Decision: leave as-is, don't restructure pre-existing Ruby reference material to match this path
- [~] 3.2 N/A given the above — the existing runner already targets `02_the_registry` correctly
- [ ] 3.3 Run the example — **not verified**: Ruby isn't installed in this sandbox

**4. Verify the Iteration**
- [ ] 4.1 Confirm the example runs successfully — unverified, no Ruby available
- [x] 4.2 Reviewed git status (as part of this investigation)
- [ ] 4.3 Commit the completed Registry iteration separately — **not how it happened**: all of `ruby/00`–`12` landed in one `Initial commit`, not one commit per iteration
