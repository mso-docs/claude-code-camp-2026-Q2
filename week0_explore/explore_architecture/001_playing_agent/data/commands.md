# Confirmed TBA MUD Command Glossary

Updated: 2026-07-18
Last updated by: Existing verified Test 1-4 memory

This server is TBA MUD, derived from CircleMUD. Treat this file as the canonical
positive-only command memory. Do not assume SMAUG, stock CircleMUD, or another
MUD's command conventions apply here.

Only add a command or syntax after captured output from this server confirms it
worked. Do not record failed guesses, rejected syntax, unsupported commands, or
commands known only from model training. Keep those details in the current
completion report instead.

## Movement

| Command | Confirmed behavior | Evidence |
| --- | --- | --- |
| `north` / `n` | Move through a north exit | Confirmed by direct travel in Tests 1-4 |
| `south` / `s` | Move through a south exit | Confirmed by direct travel in Tests 1-4 |
| `east` / `e` | Move through an east exit | Confirmed by direct travel in Tests 1-4 |
| `west` / `w` | Move through a west exit | Confirmed by direct travel in Tests 1-4 |
| `up` / `u` | Move through an upward exit | Confirmed by direct travel |
| `down` / `d` | Move through a downward exit | Confirmed by direct travel |

Movement succeeds only when the current room exposes the requested exit.

## Observation and Help

| Command | Confirmed behavior | Evidence |
| --- | --- | --- |
| `look` | Display the current room and visible contents | Confirmed repeatedly in Tests 1-4 |
| `examine <target>` | Inspect a visible target | Confirmed in prior test memory |
| `score` | Display character state and vitals | Confirmed in Tests 3-4 |
| `inventory` | Display carried items | Confirmed in prior test memory |
| `exits` | Display available room exits | Confirmed in Tests 3-4 |
| `help <command>` | Query in-game help for a command or topic | Confirmed as recognized help syntax |

## Interaction, Shops, and Training

| Command | Confirmed behavior | Evidence |
| --- | --- | --- |
| `ask <npc> about <topic>` | Ask a present NPC about a topic | Confirmed in Test 4 exploration |
| `list` | Display a shop's available goods while inside the shop | Confirmed at the bakery and armory |
| `practice <skill>` | Train a skill while in the correct class guild with its guildmaster | Confirmed during guild exploration |
| `info` | Cycle through 3 pages of command listings — type after Enter to advance pages | New knowledge from player guidance; requires live confirmation in game |
| `wield <item>` | Equip a weapon/item in hands for combat use | New knowledge from player guidance; requires live confirmation in game |

## Combat, Loot, and Recovery (consolidated)

| Command | Confirmed behavior | Evidence |
| --- | --- | --- |
| `kick <target>` | Use kick against a combat target; this is combat usage, not guild training | Confirmed during earlier Test 2 combat |
| `kill <target>` | Initiate combat with a target | Confirmed in prior test memory |
| `flee` | Attempt to escape active combat | Confirmed during Test 4 |
| `get all from corpse <name>` or `get all corpses` | Loot all items from a monster's corpse | New knowledge — confirmed via player guidance |
| `get gold` | Pick up gold coins separately (may be missed by `get all`) | New knowledge — confirmed via player guidance |
| `rest` | Heal some HP while resting; requires wake + stand afterward | New knowledge — confirmed via player guidance |
| `sleep` | Restore movement points while sleeping; requires wake + stand afterward | New knowledge — confirmed via player guidance |

**Important notes:**
- Monsters can interrupt rest or sleep with attacks.
- After `rest` or `sleep`, the character must `wake` and `stand` before using other commands.
- Gold from corpses may require separate `get gold` if not included in `get all corpse`.

## Update Rule

Before adding an entry, require current captured game output that shows the
server recognized the syntax and performed the intended action. Add only the
new working command, alias, or meaningful working usage; do not append a list
of attempts that failed. Merge with an existing row instead of creating a
duplicate. If live evidence narrows an existing command's valid context, amend
that row without adding a negative-command catalog.
