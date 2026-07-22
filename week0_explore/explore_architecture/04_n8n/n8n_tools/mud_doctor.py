# Paste into: AI Agent node -> Add Tool -> Code Tool, Language = Python (Beta)
#
# n8n node settings:
#   Name:        mud_doctor
#   Description: Check that the MUD server, tmux session, and stored
#                credentials are all ready before starting a session. Call
#                this first if 'start' or 'send' fail unexpectedly.
#   Specify Input Schema: OFF (this tool takes no arguments)
#
# If this errors with something like "NotImplementedError" / "network
# disabled" your n8n Python (beta) sandbox has no outbound network access.
# In that case delete this Code Tool and add a native "HTTP Request Tool"
# node instead, configured as:
#   Method: GET
#   URL:    http://<bridge-host>:8787/mud/doctor
#   Header: X-Bridge-Token: <token, if MUD_BRIDGE_TOKEN is set on the bridge>
# (swap /mud/ for /smarty/ to check the other character)

import json
import urllib.request

BRIDGE_URL = "http://localhost:8787"  # <-- point at your mud_bridge.py host
PROFILE = "mud"  # "mud" or "smarty"
BRIDGE_TOKEN = ""  # optional, must match MUD_BRIDGE_TOKEN on the bridge

request = urllib.request.Request(f"{BRIDGE_URL}/{PROFILE}/doctor", method="GET")
if BRIDGE_TOKEN:
    request.add_header("X-Bridge-Token", BRIDGE_TOKEN)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["output"]
except Exception as exc:
    return f"mud_doctor failed: {exc}"
