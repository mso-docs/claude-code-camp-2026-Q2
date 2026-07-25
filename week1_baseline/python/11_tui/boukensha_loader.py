"""BoukenshaLoader resolves which step folder to load code from, then boots
the REPL. Mirrors ruby/09_global_executable/lib/boukensha_loader.rb.

Resolution order:
  1. BOUKENSHA_PATH environment variable (selects which *step* package to load)
  2. ~/.boukensharc  (a file containing a single path)
  3. The boukensha/ package bundled alongside this file (this step's release)

Config directory (settings.yaml, .env, system.md) is separate:
  BOUKENSHA_DIR=~/.boukensha  (default, set in env to override)

MUD connection details come from settings.yaml (mud: block) by default.
The legacy MUD_NAME / MUD_HOST / MUD_PORT / MUD_PASSWORD env vars are still
honoured and take precedence over config when set.

Examples:
  boukensha                                                            # bundled package + ~/.boukensha
  BOUKENSHA_PATH=~/Sites/boukensha/python/04_api_client boukensha      # loads step 4
  BOUKENSHA_DIR=~/projects/mybot/.boukensha boukensha                  # custom config dir
  echo ~/Sites/boukensha/python/08_the_repl_loop > ~/.boukensharc && boukensha
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# This project's own bundled boukensha package lives right next to this file.
BUNDLED_STEP_DIR = Path(__file__).resolve().parent

DEFAULT_RC_PATH = Path("~/.boukensharc").expanduser()


def _is_valid_step_dir(step_dir: Path) -> bool:
    return (step_dir / "boukensha" / "__init__.py").is_file()


def _abort(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.exit(1)


def resolve(*, boukensha_path: str | None = None, rc_path: Path | None = None) -> Path:
    """Resolve which step directory to load from. boukensha_path/rc_path
    default to $BOUKENSHA_PATH / ~/.boukensharc but are overridable so this
    is testable without touching the real environment or home directory."""
    if boukensha_path is None:
        boukensha_path = os.environ.get("BOUKENSHA_PATH")
    if rc_path is None:
        rc_path = DEFAULT_RC_PATH

    # 1. Env var wins.
    if boukensha_path:
        step_dir = Path(boukensha_path).expanduser().resolve()
        if _is_valid_step_dir(step_dir):
            return step_dir
        _abort(
            "boukensha: BOUKENSHA_PATH is set but no boukensha/ package found at:\n"
            f"       {step_dir}\n"
            "       Make sure BOUKENSHA_PATH points to a step folder, e.g.:\n"
            "       BOUKENSHA_PATH=~/Sites/boukensha/python/08_the_repl_loop boukensha"
        )

    # 2. ~/.boukensharc
    if rc_path.is_file():
        raw = rc_path.read_text().strip()
        if raw:
            step_dir = Path(raw).expanduser().resolve()
            if _is_valid_step_dir(step_dir):
                return step_dir
            _abort(
                f"boukensha: ~/.boukensharc points to {raw}\n"
                "       but no boukensha/ package was found there.\n"
                "       Update ~/.boukensharc or remove it to use the bundled default."
            )

    # 3. Bundled default.
    return BUNDLED_STEP_DIR


def load_and_start_repl(
    *,
    boukensha_path: str | None = None,
    rc_path: Path | None = None,
    argv: list[str] | None = None,
    env: dict | None = None,
) -> None:
    """argv/env default to sys.argv[1:]/os.environ but are overridable, same
    reason as resolve()'s boukensha_path/rc_path: testable without touching
    real process state."""
    if argv is None:
        argv = sys.argv[1:]
    if env is None:
        env = os.environ

    step_dir = resolve(boukensha_path=boukensha_path, rc_path=rc_path)

    if env.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {step_dir}")

    sys.path.insert(0, str(step_dir))
    # A previously-imported `boukensha` module (a long-lived process, or a
    # test resolving two different step dirs in sequence) is cached by
    # name, not by path — drop it first so this actually reloads from
    # step_dir instead of silently reusing an earlier import.
    sys.modules.pop("boukensha", None)
    boukensha = importlib.import_module("boukensha")

    if not hasattr(boukensha, "repl"):
        _abort(
            f"boukensha: the step at {step_dir}\n"
            "       does not support the interactive REPL (added in step 8).\n"
            "       Run its examples directly, e.g.:\n"
            f"         python {step_dir}/examples/example.py\n"
            "       Or point BOUKENSHA_PATH at step 8 or later."
        )

    # --no-tui falls back to the plain terminal REPL (no textual).
    no_tui = "--no-tui" in argv
    repl_opts = {"tui": not no_tui}

    if env.get("MUD_NAME"):
        # Legacy env-var override still works and takes precedence over config.
        repl_opts["working_dir"] = False
        mud_password = env.get("MUD_PASSWORD")
        if mud_password is None:
            _abort("boukensha: MUD_NAME is set but MUD_PASSWORD is missing.")
        repl_opts["mud"] = {
            "host": env.get("MUD_HOST", "localhost"),
            "port": int(env.get("MUD_PORT", "4000")),
            "name": env["MUD_NAME"],
            "password": mud_password,
        }
    # If MUD_NAME is not set, boukensha.repl will fall back to config.mud_*
    # values automatically (via _mud_opts_from_config inside boukensha.repl).

    boukensha.repl(**repl_opts)


def main() -> None:
    load_and_start_repl()


if __name__ == "__main__":
    main()
