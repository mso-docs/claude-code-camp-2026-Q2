"""Step 10 — A Standard Tool Library (MUD demo)

Demonstrates boukensha.tools.mud, which registers gameplay tools against a
live CircleMUD connection. Connection credentials come from
~/.boukensha/settings.yaml (mud: host/port/username/password) by default.
Set BOUKENSHA_DIR to point at a different config directory.

    python examples/demo.py
    BOUKENSHA_DIR=iterations/.boukensha python examples/demo.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parents[4] / ".boukensha"))

import boukensha  # noqa: E402

cfg = boukensha.config()
print(f"Config: {cfg}")
print(f"API key set? {os.environ.get('ANTHROPIC_API_KEY') is not None}")
print()

boukensha.run(
    task=(
        "Connect to the MUD, look at your surroundings, check your score, "
        "then look at the available exits and tell me what you see."
    ),
    # system/model/api_key all come from config automatically
    working_dir=False,  # no filesystem tools needed for MUD play
    # mud: comes from config (settings.yaml mud: block) automatically
)
