from __future__ import annotations

from .base import Base


class Ollama(Base):
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
    }

    def __init__(self, *, model: str, host: str = "http://localhost:11434") -> None:
        super().__init__()
        self.host = host
        self.configure_model(model)

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
