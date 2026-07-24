# Step 01 · Struct Skeleton

**Ruby reference:** `week1_baseline/ruby/01_struct_skeleton/`
**Python port:** `week1_baseline/python/01_struct_skeleton/`
**Status:** Done

## Goal

Define the three data structures passed around constantly: `Tool` (name,
description, parameters, callable), `Message` (role, content, tool_use_id),
`Context` (system prompt, messages, registered tools).

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/tool.rb` | `boukensha/tool.py` | `Struct.new` → `@dataclass` |
| `lib/boukensha/message.rb` | `boukensha/message.py` | `Struct.new` → `@dataclass` |
| `lib/boukensha/context.rb` | `boukensha/context.py` | plain class in both languages |
| `boukensha/config.py`, `tasks/` | carried forward unchanged from step 00 |

## Design decisions

- Ruby `Struct.new(:a, :b) { def to_s ... end }` → Python `@dataclass` with a
  hand-written `__repr__` to match the Ruby output string exactly.
- Ruby's `attr_reader` on `Context` → plain public attributes in Python;
  there's no "private with a reader" distinction worth preserving.
- Carry forward, don't fix: the Ruby README documents a `token_budget` field
  and `budget=`/`used=` output on `Context` that doesn't exist in the actual
  Ruby code at this step (or in any step ported so far) — that's the README
  describing a later, fuller state of `Context`. The port matches the code,
  not the README's forward-looking examples.
- The example omits `default_prompts_dir` when resolving the system prompt
  (matches Ruby's example exactly), so `system_prompt` can resolve to `None`
  here — harmless since it's never printed in this step.

## Verification

Ran `examples/example.py` against a scratch settings file; output (`Tool`,
`Message`, `Context` reprs) matches the Ruby example's format.

## Outcome

Matches plan. See [`python/01_struct_skeleton/README.md`](../../week1_baseline/python/01_struct_skeleton/README.md).

## Course checklist

Retrofitted from the course's step task list; checked against what was
actually done (see caveats).

**1. Duplicate the previous Python iteration**
- [x] 1.1 Copy the previous iteration into `week1_baseline/python/01_struct_skeleton`
- [x] 1.2 Review the Ruby `01_struct_skeleton` implementation to identify what's new
- [ ] 1.3 Generate a port plan *before* making changes — **not satisfied as ordered**: this plan document was written retroactively, after steps 00–04 were already implemented, not before 01's changes were made. Confirmed port only the new functionality (Tool/Message/Context), building on the already-ported 00_config — that scoping was followed even without a prior written plan.

**2. Port the Struct Skeleton**
- [x] 2.1 New data structures ported (`Tool`, `Message`, `Context`)
- [x] 2.2 Naming and structure kept consistent with the Ruby implementation
- [x] 2.3 Lightweight dataclasses used where appropriate (`Tool`, `Message`; `Context` stayed a plain class, matching Ruby's own class-not-struct choice for it)

**3. Verify the Python port**
- [~] 3.1 Activate the Python virtual environment — N/A as literally stated; `uv sync`/`uv run` manage an ephemeral venv without a manual `source .venv/bin/activate` step
- [x] 3.2 Run the example via the provided runner (`bin/01_struct_skeleton`)
- [x] 3.3 Confirmed it executes without errors; output matches the Ruby example's format
- [~] 3.4 Review the generated code before committing — reviewed inline while writing (documented as the README's differences section); the actual git commit (`8525e5d`) and any human review of it happened outside this conversation
