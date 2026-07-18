---
name: manage-mud-server
description: Check, start, verify, and diagnose the repository's local CircleMUD Docker Compose service without deleting persistent state. Use before MUD login, after connection-refused errors, when localhost port 4000 is unavailable, or when OpenCode needs safe server readiness and recent container logs.
---

# Manage the MUD Server

Use `data/code/mud-server.sh` from the directory containing `AGENTS.md`. The tool locates the repository Compose file, manages only the `circlemud` service, and verifies both container state and port 4000.

## Ensure Readiness

Before opening a new MUD connection, run:

```bash
data/code/mud-server.sh ensure
```

The command is idempotent:

- If the service and port are ready, it changes nothing.
- If the service is stopped and the port is free, it runs `docker compose up --build -d circlemud` and waits for readiness.
- If another process owns port 4000, it stops with an error instead of creating a conflict.
- If startup fails, it prints recent service logs and exits non-zero.

Only continue to the `login-mud` workflow after `ensure` reports that the endpoint is ready.

## Diagnose Without Starting

Check state:

```bash
data/code/mud-server.sh status
```

Inspect recent logs:

```bash
data/code/mud-server.sh logs
```

Use `status` first when the user asks for diagnosis without authorizing changes. Use `logs` after a failed start or unexpected container exit.

## Guardrails

- Manage only the Compose file at `week0_explore/infrastructure/docker-compose.yml` and its `circlemud` service.
- Never run `docker compose down -v`, `docker volume rm`, `docker system prune`, or any command that deletes volumes or persistent game state.
- Do not stop a healthy server merely to retry login.
- Do not repeatedly rebuild after the same concrete error; inspect logs and report the blocker.
- Treat Docker daemon permission errors as blockers requiring user action.

## Verification

Before reporting server readiness, require both:

- Compose reports `circlemud` as running.
- `localhost:4000` accepts a TCP connection.

Server startup does not count as a MUD gameplay command and does not reset the memory-checkpoint counter.
