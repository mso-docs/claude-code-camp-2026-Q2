"""Common base for all provider backends.

Normalized response contract
-----------------------------
Every backend's parse_response() returns:

    {"stop_reason": "tool_use" | "end_turn",
     "content": [<block>, <block>, ...]}

where each block is one of:

    {"type": "reasoning",
     "text": "<human-readable reasoning, may be empty>",
     "signature": "<opaque provider token, optional>",  # round-trip only
     "redacted": True | False}                          # optional

    {"type": "text", "text": "..."}

    {"type": "tool_use", "id": ..., "name": ..., "input": {...}}

Reasoning blocks come FIRST in content, before text and tool_use (matching
Anthropic's native ordering). `text` is what the viewer renders and may be
empty (redacted/omitted reasoning). `signature`/`redacted` are opaque
carry-through for providers that require the block echoed back unchanged
(Anthropic thinking signatures, Gemini thoughtSignature) — consumers never
interpret them. Backends that don't accept reasoning back in a request drop
these blocks when rebuilding assistant turns."""

from __future__ import annotations

from ..errors import UnsupportedModelError


class Base:
    """Shared backend contract: model validation, model metadata, cost estimation."""

    MODELS: dict = {}

    def __init__(self) -> None:
        self.model: str | None = None
        self.model_info: dict | None = None

    @classmethod
    def models(cls) -> dict:
        if not cls.MODELS:
            raise NotImplementedError(f"{cls.__name__} must define MODELS")
        return cls.MODELS

    @classmethod
    def lookup_model_info(cls, model: str) -> dict | None:
        return cls.models().get(str(model))

    @classmethod
    def validate_model(cls, model: str) -> str:
        model = str(model)
        if cls.lookup_model_info(model):
            return model
        supported = ", ".join(sorted(cls.models().keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    def configure_model(self, model: str) -> None:
        self.model = self.validate_model(model)
        self.model_info = self.lookup_model_info(self.model)

    @property
    def context_window(self) -> int:
        return self.model_info["context_window"]

    @property
    def input_token_cost_per_million(self) -> float | None:
        return self.model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self) -> float | None:
        return self.model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self) -> str:
        return self.model_info["usage_unit"]

    @property
    def usage_level(self) -> str | None:
        return self.model_info.get("usage_level")

    def estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float | None:
        in_cost = self.input_token_cost_per_million
        out_cost = self.output_token_cost_per_million
        if in_cost is None or out_cost is None:
            return None
        return ((input_tokens * in_cost) + (output_tokens * out_cost)) / 1_000_000.0
