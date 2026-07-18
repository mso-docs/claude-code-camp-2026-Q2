# World Knowledge: City of Midgaard

Updated: 2026-07-18

## Movement Commands

- `north` (`n`)
- `south` (`s`)
- `east` (`e`)
- `west` (`w`)
- `up` (`u`)
- `down` (`d`)

A movement command can fail when the current room has no exit in that direction. A failed `up` command does not mean that `up` is invalid everywhere.

## Bakery

Last visited: 2026-07-18
Status: Confirmed

Description: A small bakery selling bread, danishes, and other food.

### Exits

| Direction | Destination | Status |
|---|---|---|
| south | Main Street | Confirmed |

### NPCs

- Baker
- Cityguard
- Janitor

### Services

- Food shop operated by the baker.
- Use `list` to display the menu.
- The captured menu is stored in `data/mud_bakery.txt`.

## Main Street

Last visited: 2026-07-18
Status: Confirmed

Description: A main road through the City of Midgaard.

### Exits

| Direction | Destination | Status |
|---|---|---|
| north | Bakery | Confirmed by travel |
| east | Market Square | Confirmed by travel |
| south | Armory Entrance | Reported; not confirmed by travel |
| west | Unknown | Exit observed; destination not recorded |

## Market Square

Last visited: 2026-07-18
Status: Confirmed

### Exits

| Direction | Destination | Status |
|---|---|---|
| north | Unknown | Exit observed |
| east | Unknown | Exit observed |
| south | Unknown | Exit observed |
| west | Main Street | Confirmed by travel |

## Unconfirmed Knowledge

- The destinations north, east, and south of Market Square still need to be explored.
- The destination west of Main Street still needs to be confirmed.
- Do not infer reverse exits unless they have been observed in the game.
