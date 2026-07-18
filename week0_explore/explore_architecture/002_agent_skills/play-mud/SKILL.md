---
name: play-mud
description: Connect to and operate a local CircleMUD game, maintain player and world notes, and complete user-directed gameplay objectives. Use when asked to log in to the MUD, explore or navigate its world, inspect rooms, manage inventory, buy items, fight enemies, or automate repeated MUD interactions.
---

# Workflow

Connect to the MUD, log in, explore, complete tasks, and report results.

## Connection

1. Check whether a reusable MUD helper or persistent terminal session already exists before starting another connection.
2. Use `nc localhost 4000` or `telnet localhost 4000` in a persistent terminal session. Do not use a short idle timeout that could disconnect an active game.
3. Read the login prompt and enter credentials supplied at runtime. Do not hardcode credentials in scripts or committed files.
4. Confirm successful login from the character prompt or recognizable game output before sending gameplay commands.

## Exploration

1. Run `help` to see available commands.
2. Use `look`, `examine <target>`, `inventory`, and `help <command>` as needed. CircleMUD commands do not use a leading slash.
3. Read the complete terminal output before choosing the next action.
4. Note important locations, items, NPCs, and quest objectives.

## Task Execution

1. Follow instructions precisely.
2. Execute commands when appropriate (e.g., buying items, fighting).
3. Log progress to `data/player.md` and `data/world.md`.
4. Report completion when the objective is met.

## Error Recovery

If a command fails:

1. Read the error message carefully.
2. Check `help <command>` or nearby game context before retrying with a correction.
3. Do not repeat the same failed or state-changing command more than twice without new evidence.
4. If the failure persists, report what was attempted and suggest alternatives.

## Termination

Report when all objectives are complete or if the user stops. Do not continue indefinitely without explicit instruction.

# Decision Rules

- Use `nc` for faster connections; use `telnet` only if `nc` is unavailable.
- Always confirm login before proceeding.
- Log progress after each significant step, not just at the end.
- If a command fails repeatedly, report what you tried and why it failed.
- Do not continue after character death without user confirmation. After a connection loss, preserve the latest known state and report whether reconnection is safe.

# Guardrails

- Never expose credentials in logs or output.
- Do not run commands that could cause data loss unless explicitly requested.
- Limit combat to only when necessary for the objective.
- Do not enter infinite command loops; if you repeat the same action, report it and ask how to proceed.
- If character dies, stop immediately and report what happened.

# Output Requirements

After completing a task:

1. Report completion clearly with what was accomplished.
2. Include any relevant findings or discoveries.
3. State whether any follow-up actions are needed.

## Verification

Before reporting success, verify:

- The objective is actually complete (check game state if possible).
- All required output files exist and contain the expected information.
- No errors occurred during execution.

# Data Logging

Append to `data/player.md`:

```markdown
## Progress Log - [YYYY-MM-DD]

### Objective: [Objective Name]
Status: Completed / In Progress / Failed
Progress: [What was done]
Notes: [Key findings, discoveries, issues encountered]
```

Append to `data/world.md` when discovering new locations or items:

```markdown
## World Log - [YYYY-MM-DD]

### New Location Discovered
Location: [Name] at [Coordinates if known]
Description: [What you learned about it]

### Item Found
Item: [Name] (ID: XXXXX)
Location: [Where found]
```

# Helper Scripts

Inspect `data/code` before creating a helper. Reuse or improve an existing script when possible; otherwise, create a helper only when an interaction is repeated or complex. Never store credentials in a helper script.

## Script Naming Convention

Use kebab-case, prefixed with `mud-`:

- `mud-login.sh` - Login sequence
- `mud-inventory.sh` - Inventory management
- `mud-combat.sh` - Combat workflow
- `mud-navigate.sh` - Navigation helper

## Script Structure

Make each script self-contained, validate its prerequisites, and make it safely restartable where practical. Do not treat purchases, combat, movement, or other state-changing game actions as idempotent.

```bash
#!/bin/bash
# mud-<name>.sh - [Brief description]

# Check prerequisites (e.g., is the game running?)
# Run commands sequentially with error checking
# Log progress if needed
```

## Script Management

Keep scripts in `data/code`. Edit an existing helper in place instead of creating a duplicate, and test new or modified helpers with a safe, limited interaction before relying on them for a full task.
