# Step 05 · The Agent Loop

**Ruby reference:** `week1_baseline/ruby/05_agent_loop/`
**Python port:** `week1_baseline/python/05_agent_loop/`
**Status:** Planned

## Goal

The actual agent loop: send messages, check if the model wants to call a
tool, dispatch it via `Registry`, feed the result back, repeat until the
model returns a final text answer or an iteration ceiling is hit. Everything
before this step was setup; this is where the agent does work.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/agent.rb` | `boukensha/agent.py` | the loop itself — new |
| `lib/boukensha/errors.rb` (+`LoopError`) | `boukensha/errors.py` | add `LoopError` (see note below — it's unused) |
| `lib/boukensha/tasks/base.rb` (+`max_iterations`/`max_output_tokens`) | `boukensha/tasks/base.py` | two new classmethods |
| `lib/boukensha/client.rb` (+`tools:` kwarg) | `boukensha/client.py` | `call()` gains a `tools=` override, passed through to the payload |
| `lib/boukensha/prompt_builder.rb` (+`parse_response`, `tools:` passthrough) | `boukensha/prompt_builder.py` | |
| `lib/boukensha/backends/*.py` (+`parse_response`, `tools:` passthrough, `assistant_message`/`assistant_parts`) | all 5 backends | the big one — see Design decisions |

`config.py` and `context.py` need **no changes** — the Ruby README claims
`context.rb` was updated to "carry the active task object," but diffing
`04_api_client`'s `context.rb` against `05_agent_loop`'s shows they're
identical; that line in the Ruby README is stale (`Context` has carried
`task` since step 01). Not porting a change that doesn't exist.

## Design decisions

**The core idea: every backend normalizes to one shape.** Five providers,
five raw response formats (Anthropic nests tool calls in `content`, Ollama
puts them in `message.tool_calls`, OpenAI in `choices[0].message.tool_calls`,
Gemini calls them `functionCall` parts). Rather than teach `Agent` about
all four shapes, every backend gets a `parse_response(response)` that
converts to:

```python
{"stop_reason": "tool_use" | "end_turn", "content": [
    {"type": "text", "text": "..."},
    {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
]}
```

`Agent` only ever looks at this normalized shape via
`builder.parse_response(response)` — it never touches a raw provider
response.

**The conversion has to run in reverse too.** When conversation history is
replayed on the next request, a `Message` with `role="assistant"` now has
`.content` that's a *list of blocks* (the normalized shape), not a plain
string — because that's exactly what got stored after a tool-calling turn.
OpenAI/Ollama/OllamaCloud/Gemini each need a private `assistant_message`
(or `assistant_parts`) method to rebuild their own wire format from that
list — the inverse of `parse_response`. Anthropic's `content` array *is*
already both the normalized shape and its wire format, so it needs no
extra conversion — same as in Ruby.

**`Message.content` widens.** It was `str` through step 04; from this step
on it can be `str | list[dict]`. The dataclass repr (`content[:61]` slice
etc.) already works on `str(self.content)` either way, so no repr changes
needed — but this is a real type-widening worth calling out, not just
translation noise.

**Tool call IDs aren't universal.** Anthropic and OpenAI assign a real
`id` per call, echoed back in the tool result. Ollama, OllamaCloud, and
Gemini don't assign call ids — those three backends reuse the tool's
`name` as the id and match results back by name. Porting this as-is (it's
a real API constraint, not a Ruby idiom).

**OpenAI's function arguments are a JSON *string*, not a dict — both ways.**
Building a request: `arguments` is `json.dumps(input_dict)`. Parsing a
response: `arguments` comes back as a JSON string, needs `json.loads(...)`.
Every other backend (Anthropic, Ollama, OllamaCloud, Gemini) passes
arguments as a plain dict/object in both directions. Easy to get backwards
if not careful — flagging it up front.

**`Client.call` gains a `tools=` override.** Used exactly once: the
wind-down call passes `tools=[]` to force a tools-disabled final response.
`None` (the default) means "let the backend build tools from
`context.tools`, as before."

**The wind-down mechanic (`Agent.MAX_ITERATIONS` / `wrap_up`).** Limits are
trigger thresholds, not hard caps. Once `max_iterations` is reached, the
loop stops starting new tool-calling rounds and makes exactly one
tools-disabled call with a short "wrap up" directive appended to the
conversation, asking the model to summarize progress instead of just
cutting it off mid-task. That wind-down call runs *outside* the counted
loop — it can't re-trigger itself, and a failed wind-down call
(`ApiError`) falls back to a deterministic message rather than propagating.
`max_iterations <= 0` disables the ceiling entirely (matches Ruby's
`@max_iterations.positive?` guard).

**`LoopError` is dead code, ported for parity but flagged.** The Ruby
README says step 05 "added `LoopError` for runaway agents," but it's never
raised anywhere in `agent.rb` or elsewhere — the wind-down mechanism
replaced whatever hard-raise design that error class implies. Adding it to
`errors.py` for structural parity with the Ruby reference, but it's
unreachable code in both languages.

**Message ordering constraint carried forward.** The assistant's
`tool_use` blocks must be added to history *before* the corresponding
`tool_result` — required by Anthropic's API, enforced by call order in
`handle_tool_calls` (append the assistant message first, then dispatch and
append each tool result). Get this backwards and Anthropic rejects the
request.

## Verification plan

- No live API key in this sandbox (same gap as step 04) — build a fake/mock
  backend + client to drive `Agent.run()` through: a tool-call round, a
  final text response, and the `max_iterations` wind-down path, without
  hitting a network.
- Directly unit-test each backend's `parse_response` against a captured
  example response shape from that provider's own README section (Anthropic
  `tool_use` content, Ollama `message.tool_calls`, OpenAI
  `choices[0].message.tool_calls` with string `arguments`, Gemini
  `functionCall` parts).
- Directly unit-test the reverse `assistant_message`/`assistant_parts` on
  each of the 4 backends that need it, confirming a normalized
  tool-use block round-trips correctly back into that provider's wire
  format.
- Confirm `LoopError` importable but intentionally unused (parity, not
  dead-code cleanup).

## Outcome

_(fill in after implementation)_

## Ruby build checklist (reference)

The course's checklist for building `ruby/05_agent_loop` itself (not a
Python-port checklist). Checked retrospectively — same two recurring gaps
as steps 02–04.

**1. Add the Agent Loop Iteration**
- [x] 1.1 `week1_baseline/ruby/05_agent_loop` exists with content
- [~] 1.2 Review the changes in README.md — done while writing this plan
- [x] 1.3 No unwanted `Zone.Identifier` files

**2. Review the Agent Loop** / **3. Review the Example** — understanding
checks, covered by this plan's Design decisions section (the normalized
`parse_response` shape, the reverse `assistant_message` conversion, the
wind-down mechanic, and the tool-call-before-tool-result ordering
constraint).

**4. Add the Ruby Runner**
- [ ] 4.1–4.3 Runner at `week1_baseline/bin/ruby/05_agent_loop` — **doesn't exist**; actual runner is `week1_baseline/ruby/bin/05_agent_loop` (confirmed present, correct content). Same deviation as steps 02–04 — leaving as-is per your earlier call
- [ ] 4.4 Run the example — **not verified**, Ruby isn't installed in this sandbox

**5. Verify the Agent Loop**
- [ ] 5.1–5.3 Confirm the example runs, iterates, dispatches tools, returns a final response — **not verified**, no Ruby and no live API key available here
- [x] 5.4 Reviewed git status
- [ ] 5.5 Commit separately — **not how it happened** (single `Initial commit` for all of `ruby/`)
