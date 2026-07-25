from __future__ import annotations

import json

from .base import Base

# Full rewrite this step: OpenAI moved from /v1/chat/completions to the
# /v1/responses API — different message ("input"), tool, and response shapes
# throughout this file, not an incremental change.
BASE_URL = "https://api.openai.com/v1/responses"


class OpenAI(Base):
    MODELS = {
        "gpt-5.5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4-mini": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.75, "output": 4.5},
            "usage_unit": "tokens",
        },
        "gpt-5.4-nano": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.15, "output": 0.6},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        super().__init__()
        self.api_key = api_key
        self.configure_model(model)

    def to_input(self, messages) -> list[dict]:
        """Builds the "input" array for /v1/responses (renamed from
        to_messages — there is no separate system-message convention here;
        the system prompt is a top-level "instructions" field instead)."""
        result = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append(
                    {"type": "function_call_output", "call_id": msg.tool_use_id, "output": str(msg.content)}
                )
            elif msg.role == "assistant":
                result.extend(self._assistant_items(msg.content))
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools) -> list[dict]:
        # /v1/responses tools are flat — no more function: wrapper.
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict:
        return {
            "model": self.model,
            "instructions": context.system,
            "input": self.to_input(context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": "none"},
        }

    def headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self) -> str:
        return BASE_URL

    def parse_response(self, response: dict) -> dict:
        """Normalizes a /v1/responses response into the common shape. The
        "output" array interleaves reasoning/message/function_call items in
        the order the model produced them; function_call items are collected
        separately from content and appended after (the API allows a mix of
        text and tool calls in the same turn, unlike chat/completions)."""
        content = []
        function_calls = []
        for item in response.get("output") or []:
            item_type = item.get("type")
            if item_type == "reasoning":
                text = "\n".join(s.get("text", "") for s in item.get("summary") or [])
                content.append({"type": "reasoning", "text": text})
            elif item_type == "message":
                text = "".join(
                    c.get("text", "") for c in item.get("content") or [] if c.get("type") == "output_text"
                )
                content.append({"type": "text", "text": text})
            elif item_type == "function_call":
                function_calls.append(item)

        for fc in function_calls:
            content.append(
                {
                    "type": "tool_use",
                    "id": fc.get("call_id"),
                    "name": fc.get("name"),
                    "input": json.loads(fc.get("arguments") or "{}"),
                }
            )

        return {"stop_reason": "tool_use" if function_calls else "end_turn", "content": content}

    def _assistant_items(self, content) -> list[dict]:
        """Rebuilds /v1/responses input items from normalized content blocks
        (the inverse of parse_response). Reasoning blocks are dropped — this
        API does not accept reasoning items back in the input array. Text is
        re-emitted as a single assistant message item, followed by one
        function_call item per tool_use block."""
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        text = "".join(b["text"] for b in blocks if b.get("type") == "text")
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

        items = [{"role": "assistant", "content": text}]
        items.extend(
            {
                "type": "function_call",
                "call_id": b["id"],
                "name": b["name"],
                "arguments": json.dumps(b["input"]),
            }
            for b in tool_blocks
        )
        return items
