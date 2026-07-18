---
name: create-cli-tools
description: Create bash CLI helper scripts for the CircleMUD gameplay workflow (login, navigation, inventory, combat). Use when asked to build a new tool script, automate repeated MUD interactions, or add reusable command-line utilities that operate against a local MUD via telnet/nc. Creates scripts in data/code/ with the mud- prefix and kebab-case naming convention.
---

# Create CLI Tools for CircleMUD

## Planning

1. Inspect `data/code/` for existing tools before creating new ones. Reuse or improve an existing helper instead of duplicating functionality.
2. Confirm what interaction this script automates: login, inventory checks, combat, navigation, or a custom objective.
3. Determine the minimal interface: arguments, required state, and expected output.
4. Prefer small focused scripts over monolithic ones. One script per concern.

## Script Creation

1. Create the file at `data/code/<name>.sh`.
2. Use kebab-case naming with a `mud-` prefix:
   - `mud-login.sh` - Login sequence
   - `mud-inventory.sh` - Inventory management
   - `mud-combat.sh` - Combat workflow
   - `mud-navigate.sh` - Navigation helper
3. Make the script self-contained and validate its prerequisites at startup.
4. Add a one-line shebang, title comment, and brief description header.

```bash
#!/bin/bash
# mud-<name>.sh - [Brief description]

set -euo pipefail  # Fail fast on errors
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check prerequisites (e.g., is the game running?)
if ! command -v telnet &>/dev/null; then
  echo "Error: telnet is required but not found." >&2
  exit 1
fi

# Run commands sequentially with error checking
# Log progress if needed
echo "$0 running" >> /tmp/mud-tool.log 2>/dev/null || true
```

## Design Rules

- Scripts must be safely restartable where practical. Do not treat purchases, combat, movement, or other state-changing game actions as idempotent unless explicitly designed that way.
- Validate prerequisites before executing (dependencies, connection state).
- Never store credentials in script files; accept them as arguments, read from memory files, or prompt interactively.
- Use `set -euo pipefail` for defensive scripting.
- Log to `/tmp/mud-tool.log` or stderr if progress reporting is needed; do not log credentials.
- Exit non-zero on failure and clear error message via stderr.

## Script Naming Convention

Use kebab-case, prefixed with `mud-`:

| Name | Purpose |
|---|---|
| `mud-login.sh` | Login sequence |
| `mud-inventory.sh` | Inventory management |
| `mud-combat.sh` | Combat workflow |
| `mud-navigate.sh` | Navigation helper |

## Testing and Validation

1. After creating a script, test it with a safe, limited interaction before relying on it for a full task.
2. Verify the execution path: `bash -n data/code/<name>.sh` must pass syntax check with no errors.
3. Run the script once in dry-run or simulation mode if the MUD connection is not available; confirm logic without sending state-changing commands to live gameplay.

## Guardrails

- Never hardcode credentials in scripts or committed files.
- Do not include sensitive data, tokens, or private server addresses in any file.
- Scripts must exit gracefully on connection failure with a clear error message.

# Output Requirements

After creating the tool:

1. Report the script path and what it does in one sentence.
2. Confirm `bash -n` syntax check passed.
3. State whether an existing tool was improved or if this is new.

## Verification

Before reporting success, verify:

- The script exists at `data/code/<name>.sh` and is executable (`chmod +x`).
- `bash -n data/code/<name>.sh` returns exit code 0.
- No credentials appear in the script or any referenced files.
- An existing tool was not unnecessarily replaced with a duplicate.
