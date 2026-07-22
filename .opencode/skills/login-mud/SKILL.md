---
name: login-mud
description: Establish, inspect, reuse, and close an authenticated persistent CircleMUD session using the repository's deterministic login tool. Use when OpenCode needs to log in before gameplay, recover from interactive login failures, inspect connection state, or send commands through the long-lived MUD socket.
---

# Login to the MUD

Use `data/code/mud-login.sh` from the directory containing `AGENTS.md`. The tool waits through client detection, handles the prompt-driven login on one socket, and leaves the authenticated session running in tmux.

## Start or Reuse the Session

1. Read `AGENTS.md` and the current test report before connecting.
2. Load the `manage-mud-server` skill and run `data/code/mud-server.sh ensure`. Do not attempt login until it confirms port 4000 is ready.
3. Ensure the repository-root `.env` defines `MUD_USERNAME` and `MUD_PASSWORD`. Never print their values or pass them as arguments.
4. Run:

   ```bash
   data/code/mud-login.sh start
   ```

5. Require `MUD_LOGIN_OK` and recognizable room output before treating login as successful.
6. If an authenticated session already exists, reuse it instead of creating another connection.

## Inspect and Send Commands

Inspect recent output without changing game state:

```bash
data/code/mud-login.sh status
data/code/mud-login.sh capture
```

Send exactly one gameplay command through stdin:

```bash
printf '%s\n' 'look' | data/code/mud-login.sh send
```

Read the complete captured output before selecting another command. Count each `send` invocation as one MUD command for the checkpoint cadence in `AGENTS.md`.

## Stop

Preserve required game and file state before closing. Then run:

```bash
data/code/mud-login.sh stop
```

This closes only the managed `opencode-mud` tmux session.

## Recovery

- If credentials are missing, ask the user to add `MUD_USERNAME` and `MUD_PASSWORD` to the ignored repository-root `.env`; never copy them into a tracked file.
- If the connection is refused, use `manage-mud-server` once; do not keep retrying login against a closed port.
- If login times out, run `capture` and report the last visible prompt before retrying.
- If the session exited, inspect the error once, correct the concrete cause, and run `start` again.
- Do not submit the full login sequence through a pipeline or create parallel connections.

## Verification

Before reporting login success, verify:

- `status` reports the managed session is running.
- The captured output contains `MUD_LOGIN_OK`.
- A room description or character prompt is visible.
- Credentials are absent from captured output, reports, and memory files.
