# Paste into: AI Agent node -> Add Tool -> Code Tool, Language = Python (Beta)
#
# n8n node settings:
#   Name:        mud_capture
#   Description: Read the recent redacted terminal output from the
#                authenticated session (what the game printed after the
#                last command sent).
#   Specify Input Schema: OFF (this tool takes no arguments)
#
# Network-disabled fallback: native "HTTP Request Tool" node with
#   Method: GET   URL: http://<bridge-host>:8787/mud/capture
#   Header: X-Bridge-Token: <token, if set>

import json
import urllib.request

BRIDGE_URL = "http://localhost:8787"  # <-- point at your mud_bridge.py host
PROFILE = "mud"  # "mud" or "smarty"
BRIDGE_TOKEN = ""  # optional, must match MUD_BRIDGE_TOKEN on the bridge

request = urllib.request.Request(f"{BRIDGE_URL}/{PROFILE}/capture", method="GET")
if BRIDGE_TOKEN:
    request.add_header("X-Bridge-Token", BRIDGE_TOKEN)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["output"]
except Exception as exc:
    return f"mud_capture failed: {exc}"
