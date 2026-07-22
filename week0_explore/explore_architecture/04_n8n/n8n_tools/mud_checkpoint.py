# Paste into: AI Agent node -> Add Tool -> Code Tool, Language = Python (Beta)
#
# n8n node settings:
#   Name:        mud_checkpoint
#   Description: Persist a resumable handoff (durable game-state memory,
#                not the agent's conversational memory) and reset the
#                4-command send gate. Call this after roughly every 4
#                mud_send calls, or when the objective status changes.
#   Specify Input Schema: ON, JSON schema:
#     {
#       "type": "object",
#       "properties": {
#         "status": {"type": "string", "enum": ["in_progress", "blocked", "complete"]},
#         "room": {"type": "string", "description": "Last verified room/location name."},
#         "summary": {"type": "string", "description": "What happened since the last checkpoint."},
#         "player_changes": {"type": "string", "description": "New confirmed facts about the player character."},
#         "world_changes": {"type": "string", "description": "New confirmed facts about the game world."},
#         "next_action": {"type": "string", "description": "What to do next."}
#       },
#       "required": ["status", "room", "summary", "player_changes", "world_changes", "next_action"]
#     }
#
# Network-disabled fallback: native "HTTP Request Tool" node with
#   Method: POST   URL: http://<bridge-host>:8787/mud/checkpoint
#   Body (JSON): the six fields above, each via {{ $fromAI('field_name') }}
#   Header: X-Bridge-Token: <token, if set>

import json
import urllib.request

BRIDGE_URL = "http://localhost:8787"  # <-- point at your mud_bridge.py host
PROFILE = "mud"  # "mud" or "smarty"
BRIDGE_TOKEN = ""  # optional, must match MUD_BRIDGE_TOKEN on the bridge

fields = ("status", "room", "summary", "player_changes", "world_changes", "next_action")
body = query if isinstance(query, dict) else {}
missing = [field for field in fields if not str(body.get(field, "")).strip()]
if missing:
    return f"mud_checkpoint requires: {', '.join(missing)}"
if body["status"] not in {"in_progress", "blocked", "complete"}:
    return "mud_checkpoint status must be one of: in_progress, blocked, complete"

payload = json.dumps({field: body[field] for field in fields}).encode("utf-8")
request = urllib.request.Request(
    f"{BRIDGE_URL}/{PROFILE}/checkpoint",
    method="POST",
    data=payload,
    headers={"Content-Type": "application/json"},
)
if BRIDGE_TOKEN:
    request.add_header("X-Bridge-Token", BRIDGE_TOKEN)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["output"]
except Exception as exc:
    return f"mud_checkpoint failed: {exc}"
