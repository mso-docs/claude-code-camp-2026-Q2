from __future__ import annotations

from .config import Config

# Module-level state, mirroring Ruby's Boukensha module-level @config/@quiet/
# @debug. Kept in its own module (not __init__.py) so boukensha/logger.py can
# import it directly without a circular import back through the package
# __init__ that's still in the middle of importing Logger itself.

_quiet = False
_debug = False
_config: Config | None = None


def config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_quiet() -> None:
    global _quiet
    _quiet = True


def set_loud() -> None:
    global _quiet
    _quiet = False


def is_quiet() -> bool:
    return _quiet


def set_debug() -> None:
    global _debug
    _debug = True


def is_debug() -> bool:
    return _debug
