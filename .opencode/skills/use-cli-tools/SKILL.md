---
name: use-cli-tools
description: Discover and invoke existing bash CLI helper scripts for CircleMUD gameplay. Use when asked to run or execute a MUD tool, automate repeated interactions, navigate the world, check inventory, fight enemies, or manage gameplay state via scripts in data/code/. Loads only scripts that exist; report missing ones instead of inventing them.
---

# Use CLI Tools for CircleMUD

## Discovery

1. Before invoking any tool, check what scripts already exist: `ls -la data/code/` (or list the directory).
2. If a script matching the requested task exists in `data/code/`, invoke that one. Do not assume one exists if the listing is empty.
3. Available tools typically follow the `mud-<name>.sh` pattern:
   - `mud-login.sh` - Login sequence
   - `mud-inventory.sh` - Inventory management
   - `mud-combat.sh` - Combat workflow
   - `mud-navigate.sh` - Navigation helper

## Invocation

1. Verify the script is executable before running: `[ -x data/code/<name>.sh ]`. If not, fix permissions with `chmod +x`.
2. Run scripts from the project root so relative paths resolve correctly:
   ```bash
   cd /path/to/project && bash data/code/<name>.sh [args...]
   ```
3. Pass arguments explicitly; do not hardcode them in your invocation command.
4. Capture and inspect the full output before deciding the next action.

## Error Handling

1. If a script returns a non-zero exit code, read stderr output carefully before retrying.
2. Do not repeat a failed tool more than twice without investigating the root cause.
3. If the script fails because a prerequisite is missing (e.g., telnet not installed, MUD not running), report exactly what is missing and suggest how to fix it.

## State Awareness

1. Scripts may read from or write to memory files (`data/player.md`, `data/world.md`, etc.). Check these paths after invoking a tool to confirm state changes were applied correctly.
2. If a tool does not update any memory files, check whether that is expected behavior (e.g., a read-only query) or if the script needs an additional argument/flag to persist output.

## Decision Rules

- Prefer existing tools over writing new ones for repeated interactions.
- Use `use-cli-tools` when a user asks to execute, run, or invoke a MUD helper script.
- Use `create-cli-tools` when no existing tool matches the required interaction and one should be built.
- If no matching tool exists, report which scripts are available and suggest alternatives rather than guessing.

## Guardrails

- Never pass credentials as command-line arguments to a running process (they appear in `/proc` and `ps`). Use memory files or interactive prompts instead.
- Do not execute scripts that contain hardcoded secrets. Refuse and flag the file for repair via `create-cli-tools`.
- Do not run state-changing tools from combat or purchases unless explicitly requested by the user.
- Limit interactions to safe exploration if the user has not specified a particular objective.

## Output Requirements

After invoking a tool:

1. Report the exit code and key output (not verbose logs).
2. State what changed in game state, memory files, or MUD session as a result.
3. If the invocation failed, report the error message and suggest next steps.

# Verification

Before reporting completion of a tool invocation:

- The script ran to completion with exit code 0 (or the failure was expected and handled).
- Any output that should have been captured or persisted is present in the correct location.
- Game state changes match what the user's original request expected.
- No unexpected side effects occurred (e.g., unintended world mutations, credential leakage).
