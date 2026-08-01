from __future__ import annotations

import json

from .base import Base

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouter(Base):
    """OpenRouter aggregates hundreds of models across every provider behind
    one OpenAI-chat-completions-compatible endpoint — unlike the single-vendor
    backends above, there's no fixed catalog to enumerate ahead of time.
    validate_model()/configure_model() are overridden below to accept any
    "vendor/model" slug rather than requiring pre-registration in MODELS;
    unregistered models fall back to DEFAULT_CONTEXT_WINDOW and unknown
    (None) cost rather than raising UnsupportedModelError. Add a MODELS entry
    any time a specific model gets tested and its real context window/pricing
    is known — that just improves cost estimation and compaction bookkeeping,
    it's never required to use the model.

    This is the classic OpenAI /v1/chat/completions schema (tool_calls with
    real id strings, JSON-string arguments, {"role": "tool", "tool_call_id":
    ...} results) — notably different from this repo's own openai.py, which
    moved to OpenAI's newer /v1/responses API and no longer speaks this
    dialect. It's much closer to ollama.py's shape, but not identical: Ollama
    invents no real tool_call ids (reuses the function name) and expects
    "tool_name" on a tool result rather than "tool_call_id"."""

    MODELS: dict = {}

    DEFAULT_CONTEXT_WINDOW = 128_000

    def __init__(self, *, api_key: str, model: str) -> None:
        super().__init__()
        self.api_key = api_key
        self.configure_model(model)

    @classmethod
    def validate_model(cls, model: str) -> str:
        return str(model)

    def configure_model(self, model: str) -> None:
        self.model = self.validate_model(model)
        self.model_info = self.MODELS.get(self.model) or {
            "context_window": self.DEFAULT_CONTEXT_WINDOW,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "openrouter_usage",
        }

    def to_messages(self, system, messages) -> list[dict]:
        system_message = [{"role": "system", "content": system}]
        conversation = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append(
                    {"role": "tool", "tool_call_id": msg.tool_use_id, "content": str(msg.content)}
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
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "max_tokens": max_output_tokens,
        }

    def headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            # Optional per OpenRouter's docs (identifies the app on their
            # dashboard/leaderboards) — harmless to send, never required.
            "X-Title": "boukensha",
        }

    def url(self) -> str:
        return BASE_URL

    def parse_response(self, response: dict) -> dict:
        """Normalizes a /v1/chat/completions response into the common shape.
        Unlike Ollama, real tool_call ids come back from the API and must be
        echoed back verbatim in the matching tool-result message — reusing
        the function name (Ollama's trick) would break multi-tool-call turns
        where the same tool is called more than once."""
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content = []
        reasoning = message.get("reasoning")
        if reasoning:
            content.append({"type": "reasoning", "text": reasoning})
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            fn = tc.get("function") or {}
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            content.append(
                {"type": "tool_use", "id": tc.get("id"), "name": fn.get("name"), "input": arguments}
            )

        return {"stop_reason": "tool_use" if tool_calls else "end_turn", "content": content}

    def usage(self, response: dict) -> dict:
        """OpenAI-chat-completions-style usage: prompt_tokens/completion_tokens,
        not Anthropic's input_tokens/output_tokens (see Base.usage())."""
        usage = response.get("usage") or {}
        return {
            "input_tokens": usage.get("prompt_tokens") or 0,
            "output_tokens": usage.get("completion_tokens") or 0,
        }

    def _assistant_message(self, content) -> dict:
        """Rebuilds an assistant message from normalized content blocks (the
        inverse of parse_response). Reasoning blocks are dropped — most
        OpenRouter-routed models don't accept reasoning echoed back in the
        request the way Anthropic/Gemini do."""
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text_blocks = [b for b in blocks if b["type"] == "text"]
        tool_blocks = [b for b in blocks if b["type"] == "tool_use"]

        message = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
        if tool_blocks:
            message["tool_calls"] = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                }
                for b in tool_blocks
            ]
        return message
