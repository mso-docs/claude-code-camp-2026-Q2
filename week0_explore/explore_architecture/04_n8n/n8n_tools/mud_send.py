# Paste into: AI Agent node -> Add Tool -> Code Tool, Language = Python (Beta)
#
# n8n node settings:
#   Name:        mud_send
#   Description: Send exactly one command through the authenticated MUD
#                session (e.g. 'look', 'north', 'say hello'). A checkpoint
#                is required after every 4 commands; call mud_checkpoint
#                before sending again once you see SDK_COMMAND_COUNT=4/4.
#   Specify Input Schema: ON, JSON schema:
#     {
#       "type": "object",
#       "properties": {
#         "command": {
#           "type": "string",
#           "description": "One MUD command line, no newlines."
#         }
#       },
#       "required": ["command"]
#     }
#
# Network-disabled fallback: native "HTTP Request Tool" node with
#   Method: POST   URL: http://<bridge-host>:8787/mud/send
#   Body (JSON):   { "command": "{{ $fromAI('command') }}" }
#   Header: X-Bridge-Token: <token, if set>

import json
import urllib.request

BRIDGE_URL = "http://localhost:8787"  # <-- point at your mud_bridge.py host
PROFILE = "mud"  # "mud" or "smarty"
BRIDGE_TOKEN = ""  # optional, must match MUD_BRIDGE_TOKEN on the bridge

command = (query or {}).get("command", "").strip() if isinstance(query, dict) else str(query).strip()
if not command or "\n" in command or "\r" in command:
    return "mud_send requires one non-empty command line"

payload = json.dumps({"command": command}).encode("utf-8")
request = urllib.request.Request(
    f"{BRIDGE_URL}/{PROFILE}/send", method="POST", data=payload, headers={"Content-Type": "application/json"}
)
if BRIDGE_TOKEN:
    request.add_header("X-Bridge-Token", BRIDGE_TOKEN)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    return f"{result['output']}\n\nSDK_COMMAND_COUNT={result['commands_since_checkpoint']}/{result['command_limit']}"
except Exception as exc:
    return f"mud_send failed: {exc}"
