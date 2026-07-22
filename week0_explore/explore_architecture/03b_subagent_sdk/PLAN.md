# 03b Two-Player Subagent SDK Plan

## Goal

Mirror the durable MUD setup from `03_subagent_sdk`, but use two
programmatic Claude Agent SDK `AgentDefinition` objects instead of agent
Markdown files. The active challenge is to have both characters play
concurrently while collecting live evidence for Smarty's age, gender, class,
and stats.

## Design

- `scripts/run_agent.py` defines `play-mud` and `smarty` inline, converts
  each `AgentDefinition` into its own foreground SDK run, and supervises both
  concurrently with `asyncio.gather`. Python waits for both transports.
- `scripts/mud.py` creates two in-process MCP servers.
- Each character has an isolated tmux session, credential profile, command
  counter, player state, session handoff, and checkpoint history.
- Both characters share `QUEST.md`, `data/world.md`, and
  `data/commands.md`.
- The bounded shell login implementation remains the only connection path.

## Credentials

The primary values stay in the repository-root `.env`. Smarty's values are
kept in this folder's git-ignored `.env`:

```dotenv
MUD_SMARTY_USERNAME=smarty
MUD_SMARTY_PASSWORD=<smarty password>
```

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/run_agent.py --check
python3 scripts/test-mud-login.py
python3 scripts/run_agent.py start
```

Completion requires live evidence from the relevant character, one final save
per participating character, and verified memory updates.
