class PromptBuilder:
    """Serializes Context into whichever backend's API format. Never calls the API."""

    def __init__(self, context, backend) -> None:
        self.context = context
        self.backend = backend

    def to_messages(self):
        return self.backend.to_messages(self.context.messages)

    def to_tools(self):
        return self.backend.to_tools(self.context.tools)

    def to_api_payload(self, *, max_output_tokens: int = 1024, tools: list | None = None):
        return self.backend.to_payload(self.context, max_output_tokens=max_output_tokens, tools=tools)

    def parse_response(self, response: dict) -> dict:
        """Delegates to the backend, which normalizes a provider response into
        the common shape documented in backends/base.py:
        {"stop_reason": "tool_use" | "end_turn",
         "content": [{"type": "reasoning", ...} | {"type": "text", ...} | {"type": "tool_use", ...}]}"""
        return self.backend.parse_response(response)

    def headers(self):
        return self.backend.headers()

    def url(self):
        return self.backend.url()
