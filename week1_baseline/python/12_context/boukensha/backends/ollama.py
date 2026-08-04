from __future__ import annotations

from .base import Base


class Ollama(Base):
    # Known metadata overrides, not an allowlist. Ollama itself is the source
    # of truth for whether a model is installed; dynamically discovered or
    # explicitly named server models use the conservative fallback below.
    MODELS = {
        "gemma4:e4b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # Added for local testing against a custom Ollama server — context
        # windows are estimates (matching this repo's existing qwen3:30b
        # entry from step 11), not vendor-confirmed; adjust if you know the
        # real figure for your build.
        "qwen3.6:27b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3.6:35b-a3b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # For fast eval iteration (evals/README.md) — same Qwen family as
        # qwen3.6:27b/qwen3.6:35b-a3b above, already proved out for
        # tool-calling in this harness, at a fraction of the size/latency.
        # Context window is a rough estimate like the others above, not
        # vendor-confirmed.
        "qwen3.5:4b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # Same family as qwen3.5:4b above, one size class up — added to fill
        # in the gap between that model's near-total failure and
        # qwen3.6:27b's ~67% pass rate on the bakery/return_to_midgaard
        # evals. Context window matches the 4b entry (vendor-unconfirmed).
        "qwen3.5:9b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # Cross-family same-size-class control against qwen3.6:27b — Gemma 2
        # is a different lineage from the Gemma 4/qwen3.x entries above.
        # Context window is Gemma 2's real vendor-documented figure (8k),
        # NOT copied from the other entries — Gemma 2 was never trained past
        # that, so requesting more via num_ctx would degrade rather than help.
        "gemma2:27b": {
            "context_window": 8_192,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # Same size class as qwen3.6:27b/gemma2:27b above, but Gemma 4-gen
        # like the gemma4:e4b entry — a fairer context budget (128k) than
        # gemma2:27b's 8k for models otherwise being compared side by side.
        "gemma4:26b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # Cohere Command R7B — purpose-built for tool-use/RAG rather than
        # general chat, unlike every other entry here. Included as a control
        # for whether tool-calling-specific training beats raw size (see
        # qwen3.6:35b-a3b underperforming qwen3.6:27b despite being bigger).
        # 128k is Cohere's documented context window for this model.
        "command-r7b:latest": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # Cross-family, smaller size class — Llama 3.1's documented context
        # window is 128k.
        "llama3.1:8b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # Cross-family, smaller size class — this tag resolves to Mistral 7B
        # Instruct v0.3 on the Ollama library, documented context window 32k.
        "mistral:latest": {
            "context_window": 32_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        # UNVERIFIED — a custom/private tag, not a public model this doesn't
        # have specs for; no Ollama server was reachable from where this was
        # added to check `ollama show agents-a1` for its real base model and
        # trained context length. 32k here is a conservative placeholder
        # (matching models.py's DEFAULT_CONTEXT_WINDOW), not a vendor figure
        # — replace with the real number once known, since an inflated value
        # would silently degrade this model's eval results via a too-large
        # num_ctx request.
        "agents-a1:latest": {
            "context_window": 32_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
    }

    DEFAULT_CONTEXT_WINDOW = 32_000

    def __init__(self, *, model: str, host: str = "http://localhost:11434") -> None:
        super().__init__()
        self.host = host
        self.configure_model(model)

    @classmethod
    def validate_model(cls, model: str) -> str:
        model = str(model).strip()
        if not model:
            raise ValueError("Ollama model name cannot be empty")
        return model

    def configure_model(self, model: str) -> None:
        self.model = self.validate_model(model)
        self.model_info = self.MODELS.get(self.model) or {
            "context_window": self.DEFAULT_CONTEXT_WINDOW,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        }

    def to_messages(self, system, messages) -> list[dict]:
        system_message = [{"role": "system", "content": system}]
        conversation = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append(
                    {"role": "tool", "tool_name": msg.tool_use_id, "content": msg.content}
                )
            elif msg.role == "assistant":
                conversation.append(self._assistant_message(msg.content))
            else:
                conversation.append({"role": msg.role, "content": msg.content})
        return system_message + conversation

    def to_tools(self, tools) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict:
        return {
            "model": self.model,
            "stream": False,
            "think": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            # Without this, Ollama silently serves the request at its own
            # runtime default context (commonly 4096, sometimes less) —
            # unrelated to and much smaller than context.context_window,
            # the figure Context's own compaction bookkeeping (compaction_
            # threshold, needs_compaction()) is measured against. That
            # mismatch means boukensha thinks it has room and never
            # compacts, while Ollama is quietly truncating/losing earlier
            # messages well before that — the likely real cause behind a
            # small local model "failing" after only a few tool calls, not
            # actually the max_turn_tokens circuit breaker. This makes the
            # two agree.
            "options": {"num_ctx": context.context_window},
        }

    def headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def url(self) -> str:
        return f"{self.host}/api/chat"

    def parse_response(self, response: dict) -> dict:
        """Normalizes an Ollama /api/chat response into the common shape.

        Ollama doesn't assign call ids, so the function name is reused as the
        id (Ollama also matches tool results back to a call by name).
        Reasoning is discarded by the assistant-message rebuild below (Ollama
        does not accept a "thinking" field back in the request)."""
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content = []
        thinking = message.get("thinking")
        if thinking:
            content.append({"type": "reasoning", "text": thinking})
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            fn = tc.get("function") or {}
            content.append(
                {"type": "tool_use", "id": fn.get("name"), "name": fn.get("name"), "input": fn.get("arguments") or {}}
            )

        return {"stop_reason": "tool_use" if tool_calls else "end_turn", "content": content}

    def usage(self, response: dict) -> dict:
        """Ollama's /api/chat has no "usage" key at all — token counts are
        top-level prompt_eval_count/eval_count instead (see Base.usage())."""
        return {
            "input_tokens": response.get("prompt_eval_count") or 0,
            "output_tokens": response.get("eval_count") or 0,
        }

    def _assistant_message(self, content) -> dict:
        """Rebuilds an Ollama assistant message from normalized content blocks
        (the inverse of parse_response). Reasoning blocks are dropped."""
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text_blocks = [b for b in blocks if b["type"] == "text"]
        tool_blocks = [b for b in blocks if b["type"] == "tool_use"]

        message = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
        if tool_blocks:
            message["tool_calls"] = [
                {"function": {"name": b["name"], "arguments": b["input"]}} for b in tool_blocks
            ]
        return message
