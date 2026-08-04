#!/usr/bin/env python3
"""One-off export of the CircleMUD room graph (vnum, name, exits) to a
static JSON asset, so the Ruby log_viz app can build a shared cross-session
room map without needing a Python runtime at request time.

Run from this directory with the package's own venv:
    .venv/bin/python export_room_graph.py <wld_dir> <output.json>

Reads every *.wld file in wld_dir (the real world data the eval CircleMUD
instance boots from, week0_explore/infrastructure/lib/world/wld — NOT this
package's own assets/wld, which is a smaller bundled sample) and merges
every zone's rooms into one vnum-keyed graph. Direction codes follow
CircleMUD's convention (0=N,1=E,2=S,3=W,4=U,5=D), translated to the same
"north"/"east"/... strings boukensha's move tool and this file's session
logs already use, so nothing downstream has to know about CircleMUD's
numeric codes.
"""
import json
import sys
from pathlib import Path

from circlemud_world_parser.parse import parse_based_on_filepath

DIRECTIONS = {0: "north", 1: "east", 2: "south", 3: "west", 4: "up", 5: "down"}


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <wld_dir> <output.json>", file=sys.stderr)
        sys.exit(1)

    wld_dir, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    rooms = {}
    total_errors = 0

    for wld_file in sorted(wld_dir.glob("*.wld")):
        payload, errors = parse_based_on_filepath(str(wld_file))
        total_errors += len(errors)
        for room in payload:
            rooms[room.id] = {
                "id": room.id,
                "name": room.name,
                "exits": {
                    DIRECTIONS[e.dir]: e.room_linked
                    for e in room.exits
                    if e.dir in DIRECTIONS and e.room_linked >= 0
                },
            }

    out_path.write_text(json.dumps(rooms, sort_keys=True, indent=None, separators=(",", ":")))
    print(f"{len(rooms)} rooms from {len(list(wld_dir.glob('*.wld')))} zone files "
          f"({total_errors} parse errors) -> {out_path}")


if __name__ == "__main__":
    main()
