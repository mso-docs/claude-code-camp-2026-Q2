# MUD tools for n8n

[mud.py](mud.py) is the original Claude Agent SDK version: it uses
`@tool`/`create_sdk_mcp_server` and shells out to `mud.sh`, which drives a
persistent `tmux` session talking over raw TCP (`nc`) to a Dockerized
CircleMUD server, plus reads/writes local markdown files for memory.

n8n's Python (beta) Code node runs in a sandboxed interpreter with no
`subprocess`, no `tmux`, no local filesystem, and (in many setups) no
outbound network either — so `mud.py` can't be pasted in as-is. Instead:

- [mud_bridge.py](mud_bridge.py) — a small FastAPI service that keeps the
  same `mud.sh`-driving logic, but runs on the host next to the real tmux
  session and Docker Compose MUD server, and exposes it over plain HTTP.
- [n8n_tools/](n8n_tools/) — one Python snippet per action, meant to be
  pasted into a separate **Code Tool** node on an n8n **AI Agent** node.
  Each just calls the bridge over HTTP with `urllib.request` (stdlib only).

The AI Agent's own **Simple Memory** covers conversational turns for one
run; `mud_memory` / `mud_checkpoint` are for durable game state (quest
progress, player/world facts) that needs to survive across separate runs,
which Simple Memory does not do.

## 1. Run the bridge

From this directory, using the venv already set up for `03b_subagent_sdk`:

```bash
../03b_subagent_sdk/.venv/bin/python -m pip install fastapi uvicorn
../03b_subagent_sdk/.venv/bin/uvicorn mud_bridge:app --host 0.0.0.0 --port 8787
```

It needs the same env vars as the original tool (from `03b_subagent_sdk/.env`):
`MUD_USERNAME`, `MUD_PASSWORD`, `MUD_SMARTY_USERNAME`, `MUD_SMARTY_PASSWORD`.
Set `MUD_BRIDGE_TOKEN` too if n8n isn't on a trusted local network — every
request must then send a matching `X-Bridge-Token` header.

If n8n runs on a different machine/container than the bridge, `localhost`
in the snippets won't reach it — use the bridge host's real address or
Docker service name instead.

## 2. Add the tools in n8n

On an **AI Agent** node, add one **Code Tool** node per file in
`n8n_tools/`, language set to **Python (Beta)**. Each file's header comment
has the exact **Name**, **Description**, and (for `mud_send` /
`mud_checkpoint`) **Input Schema** to paste into that node's settings.
Before pasting, edit the `BRIDGE_URL` / `PROFILE` / `BRIDGE_TOKEN` constants
near the top of each snippet. Duplicate the six action tools (all but
`mud_doctor`, which is profile-agnostic diagnostics) with `PROFILE =
"smarty"` if you want the agent to control both characters.

Typical order for the agent to call things: `mud_doctor` → `mud_start` →
`mud_memory` → repeated `mud_send`/`mud_capture`/`mud_status` → `mud_checkpoint`
every ~4 sends.

## 3. If the Python sandbox has no network access

Each snippet's header documents the equivalent native **HTTP Request Tool**
node (method, URL, body) — swap the Code Tool for one of those and point it
at the same bridge endpoint if `urllib.request` errors out or hangs.
