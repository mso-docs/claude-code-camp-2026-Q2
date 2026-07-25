class UnknownToolError(Exception):
    pass


class UnsupportedModelError(Exception):
    pass


class ApiError(Exception):
    pass


class LoopError(Exception):
    """Defined for parity with the Ruby reference; never raised there either
    — the wind-down mechanism in Agent.run replaced whatever hard-raise
    design this implies."""
