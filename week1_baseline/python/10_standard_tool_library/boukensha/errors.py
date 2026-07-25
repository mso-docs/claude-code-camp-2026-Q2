class UnknownToolError(Exception):
    pass


class UnsupportedModelError(Exception):
    pass


class ApiError(Exception):
    pass


class LoopError(Exception):
    """Dropped in step 06's snapshot, back in step 07's — snapshot drift,
    not a design change. Still never raised anywhere."""
