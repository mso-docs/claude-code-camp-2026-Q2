# Paste into: AI Agent node -> Add Tool -> Code Tool, Language = Python (Beta)
#
# n8n node settings:
#   Name:        mud_memory
#   Description: Load the quest brief and durable memory (session handoff,
#                checkpoint history, player facts, world facts, command
#                reference). Call this at the start of a run to re-orient;
#                this is separate from the AI Agent's own conversational
#                Simple Memory, which does not carry facts between runs.
#   Specify Input Schema: OFF (this tool takes no arguments)
#
# Network-disabled fallback: native "HTTP Request Tool" node with
#   Method: GET   URL: http://<bridge-host>:8787/mud/memory
#   Header: X-Bridge-Token: <token, if set>

import json
import urllib.request

BRIDGE_URL = "http://localhost:8787"  # <-- point at your mud_bridge.py host
PROFILE = "mud"  # "mud" or "smarty"
BRIDGE_TOKEN = ""  # optional, must match MUD_BRIDGE_TOKEN on the bridge

request = urllib.request.Request(f"{BRIDGE_URL}/{PROFILE}/memory", method="GET")
if BRIDGE_TOKEN:
    request.add_header("X-Bridge-Token", BRIDGE_TOKEN)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["output"]
except Exception as exc:
    return f"mud_memory failed: {exc}"
