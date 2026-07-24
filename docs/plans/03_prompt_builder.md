# Step 03 · The Prompt Builder

**Ruby reference:** `week1_baseline/ruby/03_prompt_builder/`
**Python port:** `week1_baseline/python/03_prompt_builder/`
**Status:** Done

## Goal

Serialize `Context` into whatever wire format a given LLM API expects.
`PromptBuilder` delegates to a pluggable backend (Anthropic, OpenAI, Gemini,
Ollama, OllamaCloud) — it never calls the network itself, just assembles the
payload dict.

## Scope — files to port

| Ruby | Python | Notes |
|---|---|---|
| `lib/boukensha/prompt_builder.rb` | `boukensha/prompt_builder.py` | thin delegator, 1:1 |
| `lib/boukensha/backends/base.rb` | `boukensha/backends/base.py` | model validation + cost metadata contract |
| `lib/boukensha/backends/anthropic.rb` | `boukensha/backends/anthropic.py` | |
| `lib/boukensha/backends/openai.rb` | `boukensha/backends/openai.py` | |
| `lib/boukensha/backends/ollama.rb` | `boukensha/backends/ollama.py` | |
| `lib/boukensha/backends/ollama_cloud.rb` | `boukensha/backends/ollama_cloud.py` | |
| `lib/boukensha/backends/gemini.rb` | `boukensha/backends/gemini.py` | |

## Design decisions

- `MODELS` tables: Ruby symbol keys/values (`usage_unit: :tokens`) become
  plain strings (`"usage_unit": "tokens"`) — same no-symbol simplification
  as earlier steps, just showing up in nested data now.
- Ruby's `Backends::Base` has both a class method `self.model_info(model)`
  (lookup by name) and an instance method `model_info` (this instance's
  resolved dict) — legal in Ruby because class/instance methods don't share
  a namespace. Python doesn't have that separation, so the classmethod is
  named `lookup_model_info`, and `model_info` is a genuine instance
  attribute set by `configure_model`.
- **Known Ruby quirk, carried forward rather than fixed:**
  `PromptBuilder#to_messages` calls `backend.to_messages(@context.messages)`
  — one argument. That matches Anthropic/Gemini's `to_messages(messages)`,
  but OpenAI/Ollama/OllamaCloud need `to_messages(system, messages)` (they
  inline the system prompt as a `role: system` message). Calling
  `PromptBuilder.to_messages()` directly would raise for those three
  backends. Never triggered in the example — only `to_api_payload()` is
  called, and each backend's own `to_payload` invokes `to_messages` with the
  right arity internally. Porting this as-is rather than smoothing it over,
  since it's a real illustration of a leaky shared interface.

## Verification

- Ran the Anthropic path end to end via `examples/example.py` — payload
  matches the Ruby README's documented shape (tool_result wrapped in a user
  message, `input_schema`, etc.).
- Spot-checked Ollama, OpenAI, Gemini, and OllamaCloud backends directly
  (`context_window`, `url()`, `estimate_cost()`, including the
  `None`-cost OllamaCloud case).
- Confirmed `UnsupportedModelError` raises with the expected message for an
  unknown model name.

## Outcome

Matches plan. See [`python/03_prompt_builder/README.md`](../../week1_baseline/python/03_prompt_builder/README.md).

## Ruby build checklist (reference)

The course's checklist for building `ruby/03_prompt_builder` itself (not a
Python-port checklist). Checked retrospectively.

**1. Add the Prompt Builder Iteration**
- [x] 1.1 `week1_baseline/ruby/03_prompt_builder` exists with content
- [x] 1.2 No unwanted `Zone.Identifier` files
- [~] 1.3 Read the iteration README.md — read while planning the Python port, not verifiable as a past action

**2. Add the Prompt Builder Runner**
- [ ] 2.1/2.2 Runner at `week1_baseline/bin/ruby/03_prompt_builder` — **doesn't exist**; actual runner is `week1_baseline/ruby/bin/03_prompt_builder`. Same as step 02 — leaving pre-existing Ruby structure as-is
- [ ] 2.3 Run the example — **not verified**, Ruby isn't installed here

**3. Review the Prompt Builder** — understanding checks; covered in this plan's Design decisions and the step README's per-provider comparison

**4. Verify Provider Configuration**
- [ ] 4.1 Active provider selected from `.boukensha/settings.yaml` — **not currently possible**: no `settings.yaml` exists yet at the repo's `.boukensha/` (only `.keep`)
- [ ] 4.2 Required API keys in `.env` — same gap, no `.env` present yet either
- [x] 4.3 Only the selected provider needs credentials — architecturally true of both the Ruby and Python ports (each backend is only constructed for the configured provider)

**5. Verify the Prompt Builder**
- [x] 5.1 Ran the (Python) example — Ruby unverified, no Ruby installed
- [x] 5.2 Confirmed payload matches the selected provider (Anthropic path; spot-checked the other four backends directly)
- [ ] 5.3 Swap provider/model in `settings.yaml` and rerun to compare — **not done**, since no `settings.yaml` exists yet to edit
- [ ] 5.4 Commit the completed iteration separately — **not how the Ruby side happened** (single `Initial commit` for all of `ruby/`); the Python side now does follow one-commit-per-step
