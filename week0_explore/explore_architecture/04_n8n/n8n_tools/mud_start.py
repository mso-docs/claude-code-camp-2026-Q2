# Paste into: AI Agent node -> Add Tool -> Code Tool, Language = Python (Beta)
#
# n8n node settings:
#   Name:        mud_start
#   Description: Ensure the CircleMUD server is up and create/reuse the one
#                authenticated tmux session for this character. Call this
#                once before status/capture/send. This is the only login path.
#   Specify Input Schema: OFF (this tool takes no arguments)
#
# Network-disabled fallback: native "HTTP Request Tool" node with
#   Method: POST   URL: http://<bridge-host>:8787/mud/start
#   Header: X-Bridge-Token: <token, if set>

import json
import urllib.request

BRIDGE_URL = "http://localhost:8787"  # <-- point at your mud_bridge.py host
PROFILE = "mud"  # "mud" or "smarty"
BRIDGE_TOKEN = ""  # optional, must match MUD_BRIDGE_TOKEN on the bridge

request = urllib.request.Request(f"{BRIDGE_URL}/{PROFILE}/start", method="POST", data=b"")
if BRIDGE_TOKEN:
    request.add_header("X-Bridge-Token", BRIDGE_TOKEN)

try:
    with urllib.request.urlopen(request, timeout=125) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["output"]
except Exception as exc:
    return f"mud_start failed: {exc}"
