from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    block: Callable

    def __repr__(self) -> str:
        description = (self.description or "")[:41]
        return f"#<Tool name={self.name} description={description} params={list(self.parameters.keys())}>"
