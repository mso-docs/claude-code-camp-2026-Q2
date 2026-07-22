# MUD World Notes

## Rooms
- **The Temple Of Midgaard (southern end of temple hall)** - confirmed live
  (smarty character login room). Giant marble blocks, ancient wall paintings
  of Gods/giants/peasants. Large steps lead down through the grand temple
  gate to the temple square below. Reading Room to the west. Donation room
  (small alcove) to the east. An automatic teller machine (ATM) is installed
  in the wall here.

## Exits
- Temple Of Midgaard (south end of hall): n, e, s, w, d (confirmed via
  `[ Exits: n e s w d ]` live output).

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
- General connection instability observed throughout: the underlying
  connection drops ("server closed the connection") after roughly 1-2
  commands on a regular basis, requiring a fresh `start` call to reconnect.
  A 1-call output lag pattern is also present: a sent command's real
  response sometimes only appears fully in the tool output of the
  *following* call rather than immediately.

## Routes
*(confirmed travel paths between rooms)*

