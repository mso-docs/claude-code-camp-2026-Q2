from __future__ import annotations

import math
from pathlib import Path

from .message import Message
from .tool import Tool


class Context:
    """Holds everything Boukensha needs to make an API call, plus proper
    token accounting: context_window (the model's real ceiling) tracked
    separately from current_tokens (actual usage from the last response) and
    turn_tokens (this turn's cumulative input+output spend)."""

    def __init__(
        self,
        *,
        system: str | None,
        context_window: int = 200_000,
        working_dir: str | None = None,
        compaction_threshold: float = 0.85,
    ) -> None:
        self.system = system
        self.context_window = context_window
        self.working_dir = str(Path(working_dir).expanduser().resolve()) if working_dir else None
        self.compaction_threshold = compaction_threshold
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens = 0
        self.turn_tokens = 0

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str, *, tool_use_id: str | None = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def update_tokens(self, n: int) -> None:
        """Update the known context size from the last API response's
        input_tokens."""
        self.current_tokens = int(n or 0)

    def reset_turn_tokens(self) -> None:
        """Reset the cumulative per-turn spend counter. Called at the top of
        a turn."""
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens, output_tokens) -> None:
        """Add one API call's input+output tokens to the cumulative per-turn
        total. This is the spend budget — distinct from current_tokens
        (window pressure)."""
        self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)

    @property
    def usage_fraction(self) -> float:
        """Fraction of the context window currently in use (0.0-1.0)."""
        return self.current_tokens / self.context_window if self.context_window > 0 else 0.0

    @property
    def usage_pct(self) -> int:
        """Integer percentage (0-100)."""
        return round(self.usage_fraction * 100)

    def needs_compaction(self, *, threshold: float | None = None) -> bool:
        """True when we should compact before the next API call. Defaults to
        the configured compaction_threshold (a fraction of context_window)."""
        return self.usage_fraction >= (threshold if threshold is not None else self.compaction_threshold)

    def compact_messages(self, *, target_fraction: float = 0.60) -> int:
        """Drop the oldest 40% of messages to free space, keeping at least 2.
        Resets current_tokens to 0 (will be updated by the next API
        response). Returns the number of messages dropped."""
        drop_count = min(math.ceil(len(self.messages) * 0.40), len(self.messages) - 2)
        drop_count = max(drop_count, 0)
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self) -> None:
        """Drop all conversation history, keeping tools and system prompt
        intact."""
        self.messages = []
        self.current_tokens = 0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return (
            f"#<Context turns={self.turn_count} tools={self.tool_count} "
            f"window={self.context_window} current={self.current_tokens}>"
        )
