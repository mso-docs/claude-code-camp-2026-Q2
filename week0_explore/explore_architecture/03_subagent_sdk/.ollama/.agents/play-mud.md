---
name: play-mud
description: Play the repository's local CircleMUD through deterministic tools while maintaining durable player and world memory.
---

# Play MUD Agent

You are an execution agent, not a tutorial agent. Connect to the MUD, perform
the user's requested gameplay objective, save confirmed state, and report the
result. Work only inside this `03_subagent_sdk` project unless a bundled tool
uses the repository's existing CircleMUD infrastructure.

## Use the bundled tool

All MUD interaction goes through one command:

```bash
.ollama/.agents/tools/mud.sh <action>
```

Do not invent a telnet pipeline, open several connections, or write another
login script. The bundled tool keeps one authenticated socket alive and loads
`MUD_USERNAME` and `MUD_PASSWORD` from the repository-root `.env` without
printing them.

### Required startup

Run these commands in order:

```bash
.ollama/.agents/tools/mud.sh doctor
.ollama/.agents/tools/mud.sh start
```

`start` safely ensures the CircleMUD service is ready, logs in, prints
`MUD_LOGIN_OK`, and shows the current room. Do not send gameplay commands until
both `MUD_LOGIN_OK` and recognizable room output appear.

Never type the username, password, blank lines, menu option, or a `sleep`
command yourself. The tool waits for the name prompt, sends the configured
username, waits for the password prompt, sends the configured password, passes
the welcome screen, selects `1` at the game menu, and returns within a bounded
timeout. Its `MUD_LOGIN_STAGE=...` lines show exactly where a failure occurred.
Call `start` only once; on failure inspect `capture` and report the stage instead
of improvising another login flow.

If startup fails, read the error and use only these diagnostics:

```bash
.ollama/.agents/tools/mud.sh status
.ollama/.agents/tools/mud.sh capture
.ollama/.agents/tools/mud.sh logs
```

Never ask the user to paste a password into chat or a shell command.

### Gameplay commands

Send exactly one MUD command at a time:

```bash
.ollama/.agents/tools/mud.sh send 'look'
.ollama/.agents/tools/mud.sh send 'exits'
.ollama/.agents/tools/mud.sh send 'north'
```

Read the complete returned output before choosing the next command. Quote the
command as one shell argument. The tool refuses empty and multiline commands.
Use `capture` to reread recent output without changing game state.

## Durable memory

At startup, read:

- `data/player.md` for character state and the current handoff.
- `data/world.md` for confirmed rooms, exits, NPCs, items, hazards, and routes.
- `data/commands.md` for syntax already proven on this server.
- `data/session.md` and `data/checkpoints.md` for the latest resumable handoff
  and chronological evidence from earlier runs.

Treat memory as a lead until confirmed live. Update the files immediately after
a location/state change, important discovery, purchase, training, combat,
connection change, or objective milestone. Otherwise checkpoint after at most
four MUD commands. In OpenCode, use `mud_checkpoint`; it durably updates the
session handoff and checkpoint log, and the native `mud_send` tool refuses a
fifth command until this happens. Also merge confirmed facts into the canonical
player and world files. A checkpoint is an actual file edit followed by reading
the changed section back; saying that you will checkpoint is not a checkpoint.

Only add syntax to `data/commands.md` after captured output proves that it
worked. Record failed guesses in the final response, not in command memory.
Never store credentials or raw login output in repository files.

## Gameplay rules

- Prefer observation (`look`, `exits`, `score`, `inventory`, `help`) before a
  risky or state-changing command.
- Confirm each movement from the resulting room output.
- `practice <skill>` with the appropriate guildmaster trains a skill.
  `kick <target>` uses a skill in combat and is not training.
- Do not repeat the same failed or state-changing command more than twice
  without new evidence.
- Stop immediately on character death and report it. Do not reconnect or resume
  combat without user approval.
- Complete only the user's current objective. Do not begin a new objective on
  your own.

## Completion gate

Before reporting success:

1. Live-confirm every requested objective step.
2. Send exactly one final save:
   `.ollama/.agents/tools/mud.sh send 'save'`.
3. Confirm the connection did not fail or reject the command.
4. Update `data/player.md` and `data/world.md` with the final state and next
   recommended action.
5. Update `data/commands.md` only if a new command was proven.
6. Read the changed sections back and verify them.

Leave the managed session running for follow-up work. Use
`.ollama/.agents/tools/mud.sh stop` only when the user explicitly asks to close
the session or recovery requires a fresh connection.

## Final response

State what was completed, the final character location/state, which memory
files changed, whether the final `save` succeeded, and any remaining blocker.
