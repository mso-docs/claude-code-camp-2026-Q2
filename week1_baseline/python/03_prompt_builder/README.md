# 03 · The Prompt Builder (Python port)

Python port of [`ruby/03_prompt_builder`](../../ruby/03_prompt_builder) — see
that README for the full per-provider payload/message/tool-schema
comparison tables (system prompt placement, tool-result wrapping, role
naming). None of that changes by language; it's a wire-format spec, not a
Ruby-vs-Python thing.

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/prompt_builder.py` | Delegates serialization to the active backend |
| `boukensha/backends/base.py` | Shared backend contract: model validation, metadata, cost |
| `boukensha/backends/anthropic.py` | Anthropic Messages API format |
| `boukensha/backends/openai.py` | OpenAI Chat Completions format |
| `boukensha/backends/ollama.py` | Local Ollama `/api/chat` format |
| `boukensha/backends/ollama_cloud.py` | Ollama Cloud format |
| `boukensha/backends/gemini.py` | Gemini `generateContent` format |

`PromptBuilder` never calls the network — it only assembles the payload.

## Notable differences from the Ruby version

- **Ruby's symbol keys inside `MODELS` (`context_window:`, `usage_unit: :tokens`)
  become plain string keys/values** (`"context_window"`, `"usage_unit": "tokens"`)
  — same "no symbol/string duality" simplification as earlier steps, just
  showing up in nested data now instead of top-level config.
- **A real naming collision, resolved differently.** Ruby's `Backends::Base`
  has *both* a class method `self.model_info(model)` (look up by name) and
  an instance method `model_info` (the resolved dict for this instance) —
  legal in Ruby because class methods and instance methods live in separate
  lookup tables. Python doesn't have that separation, so the classmethod is
  named `lookup_model_info` here and `model_info` is a genuine instance
  attribute. (Python *can* replicate Ruby's trick — instance `__dict__`
  shadows non-data descriptors like classmethods — but relying on that is
  the kind of implicit-precedence magic Python style avoids, not something
  to reach for.)
- **A known-inert quirk carried forward from Ruby, not fixed:**
  `PromptBuilder.to_messages()` delegates as `backend.to_messages(self.context.messages)`
  — one argument. That matches `Anthropic`/`Gemini`'s `to_messages(messages)`
  signature, but `OpenAI`/`Ollama`/`OllamaCloud` need `to_messages(system, messages)`
  (they inline the system prompt as a `role: system` message). Calling
  `PromptBuilder.to_messages()` directly with one of those three backends
  would raise a `TypeError`. It's harmless in practice because `to_api_payload()`
  — the only method the example ever calls — goes through each backend's own
  `to_payload`, which calls `to_messages` with the correct arity internally.
  Ported as-is rather than papering over it, since it's a good illustration
  of why a shared interface across genuinely different backends is leaky.

## Run

```bash
uv sync
../bin/03_prompt_builder
```

Requires `.boukensha/settings.yaml` with a `tasks.player.provider`/`model`,
and the matching API key env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GEMINI_API_KEY`, or `OLLAMA_API_KEY`) — `ollama` needs neither, just a local
`ollama serve`.
