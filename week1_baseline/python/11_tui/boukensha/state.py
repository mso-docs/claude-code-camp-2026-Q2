from __future__ import annotations

from .config import Config

# Module-level state, mirroring Ruby's Boukensha module-level @config/@debug.
# Kept in its own module (not __init__.py) so boukensha/logger.py can import
# it directly without a circular import back through the package __init__
# that's still in the middle of importing Logger itself.
#
# quiet/loud (set_quiet/set_loud/is_quiet) existed through step 10 but were
# removed here — dropped from both repl.rb and boukensha.rb in this step's
# Ruby reference, consistently, not snapshot drift. Removed to match.

_debug = False
_config: Config | None = None


def config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_debug() -> None:
    global _debug
    _debug = True


def is_debug() -> bool:
    return _debug
