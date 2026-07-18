---
name: play-mud
description: Connect to and operate a local CircleMUD game, maintain player and world notes, and complete user-directed gameplay objectives. Use when asked to log in to the MUD, explore or navigate its world, inspect rooms, manage inventory, buy items, fight enemies, or automate repeated MUD interactions.
---

# Workflow

Connect to the MUD, log in, explore, complete tasks, and report results.

## Connection

1. Load and follow the `manage-mud-server` skill. Ensure the local service and port 4000 are ready.
2. Load and follow the `login-mud` skill. Use `data/code/mud-login.sh start` to create or reuse the authenticated persistent session.
3. Require `MUD_LOGIN_OK` and recognizable room output before sending gameplay commands.
4. Send gameplay commands through `data/code/mud-login.sh send` so the same socket remains alive.
5. Fall back to manual `telnet localhost 4000` only after the deterministic tool fails with a concrete error. Use `nc` only if `telnet` is unavailable or fails.
6. Never build repeated pipelines, submit the entire login sequence at once, or put credentials in scripts, arguments, reports, or memory.

## Exploration

1. Read `data/commands.md` and prefer its live-confirmed TBA MUD syntax over
   conventions recalled from CircleMUD, SMAUG, or another codebase.
2. Use confirmed commands such as `help`, `look`, `examine <target>`, and
   `inventory` to investigate safely. TBA MUD commands do not use a leading
   slash unless this server later proves an exception.
3. Read the complete terminal output before choosing the next action.
4. Note important locations, items, NPCs, and quest objectives.
5. Add a command to `data/commands.md` only after captured output proves a new
   syntax worked. Keep failed guesses in the current report only; never build a
   reusable list of commands that do not work.

## Task Execution

1. Load and follow `manage-mud-memory` before gameplay so existing player,
   world, and handoff state is read at the start of every session.
2. If the task requires a report, load and follow `write-completion-report` and
   initialize the harness/model/test-specific report before connecting.
3. Follow instructions precisely.
4. Execute commands when appropriate (e.g., buying items, fighting).
5. Write confirmed state changes and discoveries to memory as they occur; do
   not wait until the end of a long objective.
6. Update the current report after every numbered objective step, memory
   checkpoint, important finding, recovery action, and final game save.
7. After every required objective step is live-confirmed, follow the single
   final-save gate under Memory Checkpoints before marking the objective PASS.
   Do not merely narrate that the character was saved.
8. Complete only the currently selected objective, persist its final state,
   and return control to the user before beginning another objective.

## Training Versus Using a Skill

Distinguish training a character skill from using it:

- Treat `practice <skill>` in the correct class guild with a guildmaster as
  training.
- Treat commands such as `kick <target>` as combat usage, not training.
- When an objective says to practice or train a skill, locate the correct
  guildmaster and issue `practice <skill>`. Do not satisfy it by attacking an
  arbitrary NPC.
- Capture the guildmaster's response. If training is refused because of class,
  level, practice points, or existing skill state, preserve that evidence and
  report the step blocked or failed instead of substituting combat.

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

1. Read `data/player.md`, `data/world.md`, and `data/commands.md`.
2. Treat saved state as context that may need live confirmation.
3. Record the current objective and its in-progress status.

During an objective:

- Update `data/player.md` in place when location, vitals, inventory, equipment,
  currency, status effects, or objective state changes.
- Merge confirmed rooms, exits, NPCs, items, services, hazards, and routes into
  canonical entries in `data/world.md`.
- Merge a command into `data/commands.md` only when live output confirms a new
  working command, alias, or meaningful syntax. Do not edit it for failures.
- Mark uncertain facts as unconfirmed and replace stale facts instead of
  appending contradictory copies.
- Count MUD commands and persist a checkpoint after no more than four commands.
  Update player and world memory, conditionally update command memory, and
  update the current report. Read back the changed sections, then reset the
  counter. Do not count shell or file operations.
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

1. If every objective step is live-confirmed, send exactly one final CircleMUD `save` command before marking PASS:
   `printf '%s\n' 'save' | data/code/mud-login.sh send`. Count it as a MUD
   command, capture the response, and verify the game did not reject it or lose
   the connection. If persistence cannot be verified, do not mark PASS; record
   the problem as BLOCKED or FAIL.
2. Write the latest player state and recommended next action to `data/player.md`.
3. Write all new confirmed world knowledge to `data/world.md`.
4. Record the final MUD `save` result in the current report without copying
   credentials or unrelated terminal output.
5. Add an objective or test marker to both memory files so the checkpoint can
   be audited.
6. Finish the selected objective's report, if required, and list the exact
   memory changes it made.
7. If a new working command was confirmed, merge it into `data/commands.md` and
   record the exact addition in the report. Otherwise leave command memory
   unchanged.
8. Read back the changed memory and report sections and verify that they contain
   the latest state and final save evidence.
9. Never store credentials in memory or reports.

The MUD `save` command persists the character on the game server. Editing
`data/player.md`, `data/world.md`, `data/commands.md`, and the report persists
the evaluation evidence in the repository. A passing test requires both forms
of persistence.

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
