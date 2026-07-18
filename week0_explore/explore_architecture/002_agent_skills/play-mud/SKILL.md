---
name: play-mud
description: Connect to and operate a local CircleMUD game, maintain player and world notes, and complete user-directed gameplay objectives. Use when asked to log in to the MUD, explore or navigate its world, inspect rooms, manage inventory, buy items, fight enemies, or automate repeated MUD interactions.
---

# Workflow

Connect to the MUD, log in, explore, complete tasks, and report results.

## Connection

1. Check whether a reusable MUD helper or persistent terminal session already exists before starting another connection.
2. Start `telnet localhost 4000` in a persistent terminal session. Do not use a short idle timeout that could disconnect an active game.
3. Use `nc localhost 4000` only if `telnet` is unavailable or fails with a concrete connection error. Do not build repeated `nc` pipelines or send the entire login sequence at once.
4. Read each login prompt before entering the corresponding credential or menu response. Do not hardcode credentials in scripts or committed files.
5. Confirm successful login from the character prompt or recognizable game output before sending gameplay commands.

## Exploration

1. Run `help` to see available commands.
2. Use `look`, `examine <target>`, `inventory`, and `help <command>` as needed. CircleMUD commands do not use a leading slash.
3. Read the complete terminal output before choosing the next action.
4. Note important locations, items, NPCs, and quest objectives.

## Task Execution

1. Follow instructions precisely.
2. Execute commands when appropriate (e.g., buying items, fighting).
3. Write confirmed state changes and discoveries to memory as they occur; do
   not wait until the end of a long objective.
4. If the task requires a report, create it with an in-progress status before
   starting and update it after major milestones.
5. Complete only the currently selected objective, persist its final state,
   and return control to the user before beginning another objective.

## Error Recovery

If a command fails:

1. Read the error message carefully.
2. Check `help <command>` or nearby game context before retrying with a correction.
3. Do not repeat the same failed or state-changing command more than twice without new evidence.
4. If the failure persists, report what was attempted and suggest alternatives.

## Termination

Report when all objectives are complete or if the user stops. Do not continue indefinitely without explicit instruction.

# Decision Rules

- Prefer `telnet` for login and the persistent gameplay session. Use `nc` only as a fallback after a concrete `telnet` failure.
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

# Memory Checkpoints

At the start of an objective:

1. Read `data/player.md` and `data/world.md`.
2. Treat saved state as context that may need live confirmation.
3. Record the current objective and its in-progress status.

During an objective:

- Update `data/player.md` in place when location, vitals, inventory, equipment,
  currency, status effects, or objective state changes.
- Merge confirmed rooms, exits, NPCs, items, services, hazards, and routes into
  canonical entries in `data/world.md`.
- Mark uncertain facts as unconfirmed and replace stale facts instead of
  appending contradictory copies.
- Count MUD commands and persist a checkpoint after no more than four commands.
  Update both memory files and the current report, read back the changed
  sections, then reset the counter. Do not count shell or file operations.
- Treat a checkpoint as file operations, not narration. When one is due, write
  and verify all three files before summarizing the discovery or sending another
  MUD command. Never say that the checkpoint will be written next.
- Keep post-checkpoint narration to one short sentence. If login attempts or
  exploration have consumed substantial context, stop gameplay and persist the
  smallest accurate checkpoint immediately.
- Checkpoint immediately instead of waiting for command four after discoveries,
  player-state changes, combat, purchases, training, objective milestones,
  connection changes, death, or before risky actions.
- Base persisted facts on captured game output. Do not reconstruct memory from
  recalled chat history or inferred room names.
- Do not rely on a final bulk write.

Before returning control to the user:

1. Save the latest player state and recommended next action.
2. Save all new confirmed world knowledge.
3. Add an objective or test marker to both memory files so the checkpoint can
   be audited.
4. Finish the selected objective's report, if required, and list the exact
   memory changes it made.
5. Verify that the memory and report files exist and contain the latest state.
6. Never store credentials in memory or reports.

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
