# OpenCode MUD Player

This folder owns an OpenCode `play-mud` agent, native MUD tools, a programmatic
SDK runner, and durable memory. Inference uses the Ollama server configured by
the repository-root `.env`; tools and game memory remain in this folder.

## Interactive OpenCode

From this directory:

```bash
source ../../../.env
export OLLAMA_HOST
opencode --agent play-mud
```

Enter `start`. The agent loads memory, checks the bundled toolchain, creates or
reuses one authenticated MUD session, and begins `QUEST.md`.

## OpenCode SDK runner

Install once, verify without starting gameplay, then run:

```bash
npm install
npm run check
npm run test:login
npm run play -- start
```

Other SDK prompts include `status`, `continue`, and `quit`.

## Memory guarantees

OpenCode exposes named `mud_*` tools from `.opencode/tools/mud.ts`. `mud_send`
allows at most four gameplay commands before requiring `mud_checkpoint`.
Checkpoints replace `data/session.md` with the current resumable handoff and
append evidence to `data/checkpoints.md`. The agent also maintains canonical
state in `data/player.md`, `data/world.md`, and `data/commands.md`.

On every new run, `mud_memory` returns the quest, latest handoff, checkpoint
history, player state, world knowledge, and confirmed commands in one call.
The agent must reconcile that memory with live output instead of starting over.

## Login rule

`.ollama/.agents/tools/mud.sh` is the only permitted login and gameplay path.
Agent instructions explicitly forbid generating alternate telnet, netcat,
socket, tmux, expect, or login scripts.

The login tool owns every prompt and wait: name prompt, password prompt,
welcome/return screen, menu option `1`, and the first room prompt. It emits
`MUD_LOGIN_STAGE=...` progress markers and has a hard overall timeout. The model
must never type credentials, menu responses, or `sleep` commands itself.
