# Agent Progress Comparison

As of July 18, 2026, four agents or model configurations have attempted the MUD bakery task. The objective is to read the agent instructions, log in as Dummy, identify the movement commands, find the bakery, run `list`, and save the menu while maintaining the player and world memory files.

| Agent or model | Status | Progress and observed issues |
| --- | --- | --- |
| **Codex 5.6 Sol** | **Completed — first achiever** | Logged in through a persistent interactive session, confirmed the movement commands, explored Midgaard, found the bakery, saved its menu, updated both memory files, saved Dummy, and closed the session cleanly. |
| **Qwen3-Coder:30B** | Failed | Located and read `AGENTS.md`, but then ran into tool-call problems and did not complete the login or bakery objective. |
| **Qwen 3.5** | Failed | Repeatedly failed to complete the interactive login. Its Bash commands eventually timed out, and its attempts also timed out while connecting to the MUD port. |
| **Qwen 3.6** | **Completed** | Created a reusable `tmux` helper under `data/code`, logged in successfully, tested movement between the Bakery, Main Street, and Market Square, ran `list`, saved the correct menu, and updated both state files. |

Individual completion reports:

- [Codex 5.6 Sol](../../../week0_explore/explore_architecture/01_plain_agent/completion-report/codex-5.6-sol.md)
- [Qwen 3.5](../../../week0_explore/explore_architecture/01_plain_agent/completion-report/qwen3.5.md)
- [Qwen3-Coder:30B](../../../week0_explore/explore_architecture/01_plain_agent/completion-report/qwen3-coder-30b.md)
- [Qwen 3.6](../../../week0_explore/explore_architecture/01_plain_agent/completion-report/qwen3.6.md)

## Codex 5.6 Sol Result

Codex 5.6 Sol was the first agent to finish the complete task during this comparison. It waited for tbaMUD's client-detection stage to finish, responded to the username, password, welcome, and game-menu prompts one at a time, and kept the same connection alive throughout exploration.

The successful route from the Temple of Midgaard was:

```text
south -> south -> west -> north
```

The bakery menu was saved to `data/mud_bakery.txt`, with exploration state recorded in `data/player.md` and `data/world.md`.

## Qwen 3.6 Result

Qwen 3.6 also completed the task. It turned the persistent-session requirement into a reusable shell helper at `data/code/mud_helper.sh`. The helper sends a command to a long-lived `tmux` session, waits for the MUD to respond, and captures the recent terminal output for the agent to inspect.

Because Codex had previously saved and disconnected Dummy while standing in the bakery, Qwen 3.6 began its successful session there. It moved south to Main Street, east to Market Square, west back to Main Street, and north back into the bakery. It confirmed the menu with `list` and saved the same three products and prices:

- Danish pastry: 7 gold
- Bread: 14 gold
- Waybread: 71 gold

Qwen 3.6 updated `data/player.md` and `data/world.md` and stored the menu in `data/mud_bakery.txt`. Its state notes confirm north, south, east, and west through actual movement; `up` was recognized but unavailable from the tested room.

## Main Experimental Finding

The largest difficulty was not recognizing the goal; it was controlling a stateful Telnet session through short-lived shell tool calls. Sending every login value to `nc` at once was unreliable because tbaMUD first performs client detection and expects later responses in sequence. Both successful approaches preserved an interactive session: Codex controlled a persistent PTY directly, while Qwen 3.6 used `tmux` plus a helper script.

This comparison supports separating deterministic connection management from model reasoning. A persistent PTY, `tmux` bridge, or dedicated MUD client can own the login sequence and socket while the language model decides which game command to issue next.
