---
name: manage-mud-memory
description: Load, reconcile, checkpoint, and verify durable MUD player and world memory across agent sessions. Use at the start of every MUD test, after live state changes or discoveries, at the command checkpoint cadence, before context exhaustion, and before completing, blocking, or handing off an objective.
---

# Manage MUD Memory

Use repository files as durable memory. The model does not retrain itself or
retain hidden state between OpenCode sessions.

## Canonical Memory

- Use `data/player.md` for current character state, current test and step,
  latest confirmed position, vitals, inventory, equipment, currency, statuses,
  last verified game save, and recommended next action.
- Use `data/world.md` for cumulative confirmed rooms, exits, routes, NPCs,
  items, services, hazards, and unresolved leads.
- Use `data/commands.md` as a positive-only TBA MUD command glossary. Store a
  command only after current captured output proves that its syntax worked on
  this server. Never add failed guesses or conventions borrowed from SMAUG,
  stock CircleMUD, or another MUD.
- Use the unique completion report for chronological evidence and the exact
  changes written at each checkpoint. Do not turn the canonical memory files
  into raw session transcripts.

## Load at Every Session Start

Before connecting to the MUD:

1. Read `AGENTS.md`, `data/player.md`, `data/world.md`, and `data/commands.md`
   completely.
2. Read the selected harness/model/test completion report if it exists.
3. Reconcile the current test, last completed test, unresolved objective,
   latest confirmed position, recommended next action, and confirmed command
   vocabulary.
4. Treat saved facts as a handoff that requires live confirmation when stale,
   risky, or contradicted by the current session.
5. Record the loaded memory summary in the current report before gameplay.

Never claim to start from a blank state when these files exist. Never rely on
chat history in place of reading them.

## Checkpoint

Follow the checkpoint cadence and immediate triggers in `AGENTS.md`. When a
checkpoint is due, do not send another MUD command until all of these succeed:

1. Update existing sections of `data/player.md` with the latest confirmed state,
   current test step, status, and next recommended action.
2. Merge new confirmed facts into canonical entries in `data/world.md`. Replace
   stale facts and label uncertain or inferred facts instead of duplicating
   contradictions.
3. If and only if current captured output proves a new working command, alias,
   or meaningful working syntax, merge it into `data/commands.md`. Do not add
   failed, ambiguous, untested, or merely assumed commands. Do not edit the
   glossary when no new successful command was discovered.
4. Update the current completion report with findings, command count, and exact
   player, world, and command-memory facts written. Failed command attempts may
   be evidence in the report but must not enter `data/commands.md`.
5. Read back every changed section and correct any missing or conflicting fact.
6. Reset the MUD-command checkpoint counter only after verification succeeds.

Use current captured game output as evidence. Never store credentials, hidden
reasoning, or guessed state.

## Final Handoff

For a passing test, verify the CircleMUD `save` first. Then write the final
player state, cumulative world discoveries, any newly verified working command,
completion markers, save result, and recommended next action. Mark a test
completed only after the memory files and unique report agree and have been
read back.

For a blocked, failed, interrupted, or context-limited test, still persist the
latest safe state, exact blocker, unresolved step, and next action. Do not write
completion markers for an unfinished test.
