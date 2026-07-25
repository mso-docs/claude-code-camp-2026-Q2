# 05 · The Agent Loop (Python port)

Python port of [`ruby/05_agent_loop`](../../ruby/05_agent_loop). This is
where the agent actually does work: send messages, check whether the model
wants a tool, dispatch it, feed the result back, repeat until a final text
answer or an iteration ceiling.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/agent.py` | `Agent` — the loop, tool dispatch, and the wind-down mechanic |
| `boukensha/errors.py` | adds `LoopError` (unused — see below) |
| `boukensha/tasks/base.py` | adds `max_iterations`/`max_output_tokens` classmethods |
| `boukensha/client.py` | `call()` gains a `tools=` override (used once, by the wind-down call) |
| `boukensha/prompt_builder.py` | adds `parse_response()`, `to_api_payload` gains `tools=` passthrough |
| `boukensha/backends/*.py` | each gains `parse_response()`; 4 of 5 gain a reverse `_assistant_message`/`_assistant_parts` |

## The core idea: one normalized shape

Five providers, five raw response formats. Rather than teach `Agent` about
all of them, every backend's `parse_response()` converts to:

```python
{"stop_reason": "tool_use" | "end_turn", "content": [
    {"type": "text", "text": "..."},
    {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
]}
```

`Agent` only ever looks at this shape. The conversion runs in reverse too:
when history is replayed, a stored assistant `Message` can now have
`.content` as a *list of blocks* instead of a plain string, and
OpenAI/Ollama/OllamaCloud/Gemini each rebuild their own wire format from it
via a private `_assistant_message`/`_assistant_parts`. Anthropic's `content`
array is already both shapes at once, so it needs no reverse conversion —
same as Ruby.

## Notable differences from the Ruby version

- **OpenAI's function arguments are a JSON *string*, not a dict — both
  directions.** Building a request: `json.dumps(input_dict)`. Parsing a
  response: `json.loads(arguments_string)`. Every other backend passes
  arguments as a plain dict. Easy to invert by accident; called out
  explicitly in both backend methods.
- **Tool call IDs aren't universal.** Anthropic and OpenAI assign a real
  `id` per call. Ollama, OllamaCloud, and Gemini don't — they reuse the
  tool's `name` as the id on both the call and the matching result. A real
  API constraint, ported as-is.
- **A genuine Ruby truthiness gotcha, avoided on purpose.** Ruby's
  `@max_output_tokens ? {...} : {}` is really a nil-check (the value is
  always an int or `nil`, never `false`) — but `0` is truthy in Ruby. A
  literal Python translation using `if self.max_output_tokens:` would
  silently drop an explicit `max_output_tokens: 0` setting, since `0` is
  falsy in Python. Used `is not None` instead to match Ruby's actual
  behavior, not just its syntax.
- **`LoopError` is dead code in both languages.** The Ruby README says this
  step "added `LoopError` for runaway agents," but it's never raised
  anywhere — the wind-down mechanism replaced whatever hard-raise design
  that implied. Ported for structural parity; it's unreachable in both.
- **The Ruby README's `context.rb` changelog entry is stale.** It claims
  this step updated `Context` to "carry the active task object," but
  `context.rb` is byte-for-byte identical between steps 04 and 05 —
  `Context` has carried `task` since step 01. Nothing to port here; noted
  so it's clear this wasn't missed, not skipped.

## Verification

No live API key with real credentials in this sandbox, so:

- Unit-tested `parse_response` and the reverse `_assistant_message`/`_assistant_parts`
  for all 5 backends against representative response shapes (including
  OpenAI's JSON-string arguments round-trip).
- Drove `Agent.run()` against a fake client/builder through: a 2-tool-call
  turn ending in a final response (verified iteration count, call count,
  and — critically — that the assistant `tool_use` message is added to
  history *before* its `tool_result`, per Anthropic's ordering requirement).
- Exercised the `max_iterations` wind-down path three ways: a successful
  wind-down call, a wind-down call that raises `ApiError` (falls back to a
  deterministic message), and `max_iterations <= 0` (ceiling disabled
  entirely).
- Ran the real example against a scratch `settings.yaml` with a fake
  Anthropic key — it correctly reached `api.anthropic.com`, got a real
  `401 invalid x-api-key` response, and wrapped it into `ApiError` with the
  provider's actual error body. Strongest verification available without a
  real key: the full pipeline (config → registry → prompt builder → client)
  is proven to work end-to-end over a real network call.

## Run

```bash
uv sync
../bin/05_agent_loop
```

Requires `.boukensha/settings.yaml` with `tasks.player.provider`/`model`
(optionally `max_iterations`/`max_output_tokens`) and the matching API key.
