# Player State

## Basic Info
- **Name:** Dummy (confirmed via `score` rank line: "This ranks you as Dummy
  the Believer (level 1)")
- **Class:** Believer (level-1 title from `score`; standard CircleMUD level-1
  Cleric title)
- **Level:** 1
- **Race:** NOT YET OBSERVED (score does not print race)
- **Age:** 17 years old (live, via `score`)

## Location
- **Room:** Market Square, the famous Square of Midgaard (live, via `look`
  this session). Exits: n (temple square) e w (main street) s (common
  square). Started session in Temple Of Midgaard; traveled south through
  Temple Square to Market Square.
- **Map Coordinates:** unknown

## Vitals
- **Hit Points:** 16(16)
- **Mana:** 100(100)
- **Moves:** 83(83)
- **Armor Class:** 39/10
- **Alignment:** 0
- **Experience:** 1 exp (1499 more needed for next level)
- **Condition:** hungry, thirsty, standing

## Equipment
- **Worn:** NOT YET CAPTURED
- **Held:** NOT YET CAPTURED
- **Dropped:**

## Inventory
- **Carried Items:** NOT YET CAPTURED

## Currency
- **Gold:** 0 gold coins
- **Spirit Stones:**

## Status Effects
- Hungry, thirsty (live, via `score`)

## Current Objective
Run alongside Smarty, confirm shared room, and gather live evidence of
Smarty's age/gender/class/stats while both sessions are active.

## Notes
- Login required ~8 retries of `mcp__mud__start` before MUD_LOGIN_OK; earlier
  attempts consistently timed out at password_prompt_received. Once
  successful, landed directly in Temple Of Midgaard with Smarty already
  present in the same room.
- `look smarty` -> "You see nothing special about him." + "Smarty is in
  excellent condition." (confirms Smarty is male, healthy).
- `consider smarty` -> "Would you like to borrow a cross and a shovel?" i.e.
  Smarty is far weaker than Dummy by the standard CircleMUD consider-message
  scale.
- Smarty's own self-reported score output (captured on Smarty's side) is
  numerically identical to Dummy's own score (17yo, 16H/100M/83V, AC 39/10,
  1 exp, level 1, rank line "Dummy the Believer") - an unresolved
  name/identity quirk of this sandbox, recorded as observed, not resolved.
- `wave smarty` -> "You wave to Smarty." Confirmed live joint interaction
  while both Dummy and Smarty sessions were active in the same room.
- `save` issued after the wave; the server's delayed response (surfaced on
  the next command) was the explicit confirmation "Saving Dummy." - final
  save live-confirmed for this character. Character remained at full/normal
  health (16H 100M 83V) throughout - no death occurred.
- Connection dropped several times mid-session ("server closed the
  connection", "can't find pane") between commands; each time a fresh
  `mcp__mud__start` call reconnected to the same authenticated session and
  same room/state without any apparent data loss.
- Subsequent session (this update): login stalled at
  `password_prompt_received` for ~24 consecutive `mcp__mud__start` retries
  before succeeding (MUD_LOGIN_OK via `reconnecting` stage) - consistent
  with the recurring instability pattern (previously 8-35 retries). Landed
  live at Market Square. Reconfirmed both sessions online via `who`
  ([ 1 Cl] Dummy the Believer, [ 1 Mu] Smarty the Apprentice of Magic).
  Sent `tell smarty` (delivery confirmed via echo) and `save`, with the
  delayed "Saving Dummy." message confirmed via a follow-up `look` -
  final save live-confirmed again. No damage/death; vitals unchanged
  (16H/100M/83V).

