from __future__ import annotations

from typing import Callable

from .errors import UnknownToolError
from .tool import Tool


class Registry:
    """Stores tools and dispatches calls. The agent never calls a tool directly."""

    def __init__(self, context) -> None:
        self.context = context

    def tool(self, name: str, *, description: str, parameters: dict | None = None) -> Callable:
        """Decorator: @registry.tool("move", description=..., parameters=...)."""

        def decorator(block: Callable) -> Callable:
            registered = Tool(str(name), description, parameters or {}, block)
            self.context.register_tool(registered)
            return block

        return decorator

    def dispatch(self, name: str, args: dict | None = None):
        tool = self.context.tools.get(str(name))
        if tool is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**(args or {}))
