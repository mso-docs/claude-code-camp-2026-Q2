# World Knowledge: City of Midgaard

Updated: 2026-07-18
Last updated by: Test 4 checkpoint

Only treat routes as confirmed when supported by captured game output or
direct travel. Keep inferred destinations explicitly unconfirmed.

## Movement Commands

- `north` (`n`)
- `south` (`s`)
- `east` (`e`)
- `west` (`w`)
- `up` (`u`)
- `down` (`d`)

A direction can fail when the current room has no matching exit. The transcript
does not prove that commands are case-insensitive.

## Market Square

Status: Confirmed

Features:

- A cityguard was observed.
- Four exits were shown: north, east, south, and west.

| Direction | Destination | Status |
|---|---|---|
| north | Temple Square | Confirmed by travel |
| east | Main Street, eastern side | Confirmed by travel |
| south | Common Square | Confirmed by travel |
| west | Main Street, western side | Confirmed by travel |

## Main Street, Western Side

Status: Confirmed; exact repeated-room segment names were not captured

| Direction | Destination | Status |
|---|---|---|
| north | Bakery | Confirmed in an earlier test |
| east | Market Square | Confirmed by travel |
| south | Armory | Confirmed by travel |
| west | Unknown Main Street segment | Unconfirmed |

## Bakery

Status: Confirmed

- South returns to Main Street.
- NPCs observed previously: baker, cityguard, and janitor.
- Use `list` to display the food menu.
- The captured menu is stored in `data/mud_bakery.txt`.

## Armory

Status: Confirmed

- North returns to Main Street.
- No other exits were shown.
- An armorer sells armor.
- The wall note describes shop commands and policies, including `list`; it did
  not provide a training clue.

## Main Street, Eastern Side

Status: Confirmed; composed of multiple connected Main Street rooms

### Shop Segment

| Direction | Destination | Status |
|---|---|---|
| north | General Store | Described; not entered in this transcript |
| east | Main Street near the east gate | Confirmed by travel |
| south | Pet Shop | Described; not entered in this transcript |
| west | Market Square | Confirmed by travel |

### Guild and East-Gate Segment

| Direction | Destination | Status |
|---|---|---|
| north | Weapon shop | Described; not entered in this transcript |
| east | Inside the East Gate | Confirmed by travel |
| south | Guild of Swordsmen | Confirmed during Test 3 |
| west | Shop segment / Market Square route | Confirmed by travel |

## Guild of Swordsmen

Status: Confirmed during Test 3

- This is Dummy's starting guild as a Sentress.
- The entrance is south from the eastern Main Street guild segment.
- The guild contains an entrance hall, bar, and tournament/practice yard.
- A guildmaster was observed in the practice yard.
- A downward route from the practice yard was observed but not explored.

## Inside the East Gate

Status: Confirmed

- West returns to the eastern Main Street guild segment.
- South leads to the Water Shop.
- The eastward gate reported that it was closed when attempted.
- Multiple cityguards and a Peacekeeper were observed around the gate area.

## Water Shop

Status: Confirmed

- North returns to the east-gate area.
- It behaved as a dead end; westward movement failed.
- Wally the Watermaster, a janitor, and an oozing green gelatinous blob were
  observed.
- Asking Wally about training produced no useful response.

## Common Square

Status: Confirmed

- Three beastly fidos were observed during Test 4.

| Direction | Destination | Status |
|---|---|---|
| north | Market Square | Confirmed by travel |
| east | Dark Alley | Confirmed by travel |
| south | The Dump | Confirmed by travel |
| west | Eastern end of Poor Alley | Confirmed by travel |

## Dark Alley

Status: Confirmed

- Several mercenaries were observed.
- West returns to Common Square.
- South was described as leading to the Guild of Thieves.
- East continues farther through the alley; the destination remains
  unconfirmed.

## The Dump

Status: Confirmed

- North returns to Common Square.
- Down leads into the sewer system.
- The room contains garbage and a large pipe junction; no NPC was observed in
  the captured output.

## Quadruple Junction Under the Dump

Status: Confirmed

- Exits shown: north, east, south, west, and up.
- Up returns to The Dump.
- East leads to The Pit.
- South leads to A Triple Junction.
- The north and west destinations were not confirmed.

## The Pit

Status: Confirmed

- West returns to the quadruple junction.
- Down leads deeper; its destination was not explored.

## A Triple Junction

Status: Confirmed

- Exits shown: north, east, and west.
- North returns to the quadruple junction.
- The east and west destinations were not confirmed.

## Poor Alley Area

Status: Partially confirmed

- The eastern end is west of Common Square.
- A Peacekeeper was encountered at the eastern end.
- A farther-west room showed east and west exits and contained a Peacekeeper
  and a beggar.
- The Grubby Inn was reached while fleeing; a beggar and Filthy were observed.
- Do not infer a fixed route to the Grubby Inn from a random `flee` result.

## West Gate Area

Status: Confirmed

- Description: "You are walking next to the western city wall. The road continues further south and the city gate is just north of here."
- Exits:
  - north → Inside The West Gate Of Midgaard
  - south → Wall Road

## Western City-Wall Room

Status: Room contents confirmed; exact title unconfirmed

- Exits shown: north, east, and south.
- An oozing green gelatinous blob was present.
- The wall is made of mortared gray rocks and is too high to climb.
- East is expected to return toward Poor Alley, but this reverse route was not
  captured directly.
- Do not call this room `Wall Road` unless a future `look` captures that exact
  title.

## Unresolved Test 4 Objectives

- The Newbie Training area has not been located.
- The Massive Minotaur has not been found or defeated.
- The western city-wall room's north and south exits remain unexplored.
- Sewer branches north and west of the quadruple junction remain unexplored.
- The route below The Pit remains unexplored.
