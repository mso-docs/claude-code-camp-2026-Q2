import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402

os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parents[4] / ".boukensha"))

import boukensha  # noqa: E402

# Config is loaded automatically inside boukensha.run() — system prompt, model,
# and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by default.
# You can still override any of them as keyword arguments if you want.

print("=== Boukensha Step 7: The boukensha.run DSL ===")
print()
print(f"Config: {boukensha.config()}")
print()

base_dir = Path(__file__).resolve().parent


def configure(dsl):
    @dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
    )
    def read_file(path):
        return (base_dir / path).read_text()

    @dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
    )
    def list_directory(path):
        entries = [f for f in os.listdir(base_dir / path) if not f.startswith(".")]
        return ", ".join(entries)


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    block=configure,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
