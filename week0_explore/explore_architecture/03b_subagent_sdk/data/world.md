# MUD World Notes

## Rooms
- **The Temple Of Midgaard (southern end of temple hall)** - confirmed live
  (smarty character's original login room in an earlier session). Giant
  marble blocks, ancient wall paintings of Gods/giants/peasants. Large steps
  lead down through the grand temple gate to the temple square below.
  Reading Room to the west. Donation room (small alcove) to the east. An
  automatic teller machine (ATM) is installed in the wall here.
- **Market Square** - confirmed live (smarty's login/reconnect room in a
  later session, after previously being in the Temple of Midgaard - room
  changed between sessions, cause not observed). "You are standing on the
  market square, the famous Square of Midgaard." A large, peculiar looking
  statue stands in the middle of the square. Roads lead in every direction:
  north to the temple square, south to the common square, east and west
  along the main street. A cityguard NPC was present (seen leaving west and
  later arriving again). Also observed here (primary/Dummy session): a
  cityguard (left west) and "The Mayor" (said "Good day, citizens!" then
  left east) - both transient wandering NPCs.

## Exits
- Temple Of Midgaard (south end of hall): n, e, s, w, d (confirmed via
  `[ Exits: n e s w d ]` live output).
- Market Square: n, e, s, w (confirmed via `[ Exits: n e s w ]` live output).

## NPCs
- **Smarty the Apprentice of Magic** - the other party character, confirmed
  standing in the Temple Of Midgaard (south hall) at the same time as
  Dummy (primary). `look smarty` -> "You see nothing special about him."
  (male) and "Smarty is in excellent condition." `consider smarty` ->
  "Would you like to borrow a cross and a shovel?" (far weaker than Dummy on
  the standard consider scale). Room title "Apprentice of Magic" suggests a
  Magic User class, but Smarty's own `score` rank line reportedly read
  "Dummy the Believer" - an unresolved naming quirk, see data/player.md and
  data/smarty/player.md for both sides' raw evidence. UPDATE: this quirk is
  reproducible and not a one-off lag artifact - Smarty's own `save` command
  also live-confirmed "Saving Dummy." (not "Saving Smarty."), matching the
  `score` rank line exactly. Also, Smarty's `equipment` shows: candle (light),
  2 leather rings, 2 leather gorgets, breast plate, leather cap, bronze
  leggings, leather boots, leather gloves, leather sleeves, a shield, brown
  leather cape, old leather belt, 2 leather wristguards, small sword
  (wielded), metal staff (held); `inventory` is empty; `practice` shows 3
  sessions remaining and 2 known-but-unlearned spells: armor, cure light
  (a spell pairing consistent with a Cleric spell list, matching "the
  Believer" title more than the Magic-User-styled room sdesc).
- Confirmed joint interaction: Dummy issued `wave smarty` and received
  "You wave to Smarty." while both the primary and Smarty sessions were
  live in the same room - satisfies the shared-activity/rendezvous
  requirement for this run.
- RE-VERIFICATION (later session, Smarty now in Market Square): all of
  Smarty's live stats/equipment/inventory were independently re-confirmed
  via fresh `score`/`equipment`/`inventory`/`save` calls after a fresh
  `start` and matched the earlier session's values exactly (age 17, HP
  16(16), Mana 100(100), Move 83(83), AC 39/10, alignment 0, exp 1, gold 0,
  questpoints 0, playtime 0d6h, level 1). `save` again returned "Saving
  Dummy." confirming the name discrepancy is stable and reproducible across
  sessions, not a one-off artifact.

## Items
*(empty - populate as items are confirmed)*

## Services
*(merchants, guildmasters, healers, etc.)*

## Hazards
- On Smarty's session, the `who` command triggered an immediate server-side
  disconnect ("MUD_LOGIN_ERROR: server closed the connection" /
  MUD_DRIVER_EXIT=1) twice in a row, distinct from the general connection
  instability seen with other commands. Avoid `who` on this session/build
  until further evidence suggests otherwise; not added to commands.md since
  it did not succeed.
- NOTE: on the primary (Dummy) session, `who` executed successfully multiple
  times with no disconnect (confirmed both characters online together), so
  the `who`-triggers-disconnect hazard appears specific to Smarty's session/
  process, not a universal server behavior.
- Login stalls at `MUD_LOGIN_STAGE=password_prompt_received` are common and
  can require anywhere from ~8 to ~35 consecutive `mcp__mud__start` retries
  before resolving to `MUD_LOGIN_OK`; this has now recurred across multiple
  sessions and should be treated as expected behavior requiring persistent
  retries, not a fatal error.
- General connection instability observed throughout: the underlying
  connection drops ("server closed the connection") after roughly 1-2
  commands on a regular basis, requiring a fresh `start` call to reconnect.
  A 1-call output lag pattern is also present: a sent command's real
  response sometimes only appears fully in the tool output of the
  *following* call rather than immediately.

## Routes
*(confirmed travel paths between rooms)*

