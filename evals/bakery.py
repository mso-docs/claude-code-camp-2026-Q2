TASK = "Log into the MUD, navigate to the town bakery, list its menu, and write the menu to data/mud_bakery.txt."
MAX_TURNS = 25

# Relative to the run's working_dir — where the scorer checks for the agent's
# output, matching the path named in TASK above.
OUTPUT_FILE = "data/mud_bakery.txt"

# Real bakery item names, captured in week0_explore/explore_architecture/
# 001_playing_agent/data/mud_bakery.txt during the original manual test.
# score.py requires at least one of these (case-insensitive) in the output,
# not just a non-empty file — a qwen3.5:4b run once wrote a real bar's menu
# (ale, firebreather, a bottle of local specialty) to this path, explicitly
# noting in its own summary that it never found an actual bakery, and the
# old "file exists and is non-empty" check scored that a PASS. These are
# static, fixed game-world data (not randomly generated per run), so
# matching against known real item names is a legitimate deterministic
# check, not a fragile guess.
#
# Deliberately NOT including plain "bread" anymore: a qwen3.6:35b-a3b run
# that never even reached mud_connect() (every attempt timed out) fabricated
# an entire placeholder menu from scratch — "Fresh Bread", "Rye Bread",
# "Dragon Bread" — none of it real, all of it invented specifically because
# the model couldn't observe the actual game. "bread" is generic enough
# that any bakery-themed fabrication trivially contains it, which defeats
# the point of a content check entirely. "danish pastry" and "waybread" are
# specific enough to the real menu that they're implausible to invent by
# coincidence; see check_mud_was_actually_reached() in score.py for the
# other half of the fix this incident required — content keywords alone
# were never going to be enough against a model willing to make things up.
EXPECTED_MENU_KEYWORDS = ["danish pastry", "waybread"]

# Checked by boukensha_agent.check_starting_room() before every trial (a
# lightweight connect-look-disconnect, no agent/LLM involved) — the character
# must be here or return_to_midgaard.py runs as a recovery attempt first (see
# that file). Room name confirmed against a real manual reset+`look` — this
# is the temple interior itself ("Large steps lead down ... and ends on the
# temple square below"), not the separate "Temple Square" room down those
# steps. There's no recall/teleport on this server, so this can't fix drift
# on its own; see evals/README.md's "position isn't reset between trials"
# section.
EXPECTED_START_ROOM = "The Temple Of Midgaard"
