class UnknownToolError(Exception):
    pass


class UnsupportedModelError(Exception):
    pass


class ApiError(Exception):
    pass


class LoopError(Exception):
    """Dropped in step 06's snapshot, back in step 07's — snapshot drift,
    not a design change. Still never raised anywhere."""


class TurnInterrupted(Exception):
    """Not in the Ruby reference — Ruby's Esc key forcibly injects an
    Interrupt into the running turn's thread (Thread#raise), which Python's
    standard library can't do safely. This is the Python port's cooperative
    alternative: Agent checks a cancel_event between loop iterations and
    raises this instead of starting the next round-trip."""
