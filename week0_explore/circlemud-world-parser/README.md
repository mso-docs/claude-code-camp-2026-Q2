CircleMUD World Parser
======================

This repo contains code for parsing [CircleMUD](http://www.circlemud.org/) world files (and therefore, in many cases older [DikuMUD](https://en.wikipedia.org/wiki/DikuMUD)). The flat files are parsed into simple Python data structures. From there, they can be output to JSON (the default command line functionality).

What is a world file?
---------------------

MUDs are text-based games made up primarily of interconnected rooms, non-player characters, objects (like weapons, armor, food), and other players.

![](https://upload.wikimedia.org/wikipedia/en/2/27/JediMUD_screenshot.png)

All of the rooms, items, and everything else that made up the game were persisted in simple textfiles. The specification for these file formats is described in "[The CircleMUD Builder's Manual](http://www.circlemud.org/cdp/building/building.html)" by Jeremy Elson, the creator of CircleMUD.

Here are the different types of files in CircleMUD v3.1:

| File extension | Description                                                 |
|----------------|-------------------------------------------------------------|
| `wld`          | Rooms                                                       |
| `mob`          | Mobiles (also known as "mobs" or NPCs)                      |
| `obj`          | Objects                                                     |
| `shp`          | Shops                                                       |
| `zon`          | Zone files (what to load where, how often to refresh, etc.) |
| `trg`          | DG Script triggers                                          |
| `qst`          | Quests                                                      |

The problem
-----------

CircleMUD world files are in a custom format that, in the original codebase, were parsed directly into memory by [db.c](https://github.com/Yuffster/CircleMUD/blob/master/src/db.c).

This is inconvenient if you want to inspect these entries or use them in other games. Because the values are not annotated and because many of the interesting features are compressed into [bitvectors](https://en.wikipedia.org/wiki/Bit_array), many lookups are necessary to understand even the simplest entry.

For example, here is one entry for an object in `lib/world/obj/30.obj` within the stock [CircleMUD world files](https://github.com/Yuffster/CircleMUD/tree/master/lib/world):

```
#3005
key dull metal~
a key of dull metal~
A key made of a dull metal is lying on the ground here.~
~
18 cdq 16385
3005 0 0 0
1 0 0
```

In the past, others have parsed these files to [XML](http://inventwithpython.com/blog/2012/03/19/circlemud-data-in-xml-format-for-your-text-adventure-game/), but the XML had some validity issues, certain file types weren't converted, and the original source code wasn't published.

Here's the same item as above in our new JSON file:

```json
{
    "affects": [], 
    "aliases": [
      "key", 
      "dull", 
      "metal"
    ], 
    "cost": 0, 
    "effects": [
      {
        "note": "NORENT", 
        "value": 4
      }, 
      {
        "note": "NODONATE", 
        "value": 8
      }, 
      {
        "note": "NOSELL", 
        "value": 65536
      }
    ], 
    "extra_descs": [], 
    "id": 3005, 
    "long_desc": "A key made of a dull metal is lying on the ground here.", 
    "rent": 0, 
    "short_desc": "a key of dull metal", 
    "type": {
      "note": "KEY", 
      "value": 18
    }, 
    "values": [
      3005, 
      0, 
      0, 
      0
    ], 
    "wear": [
      {
        "note": "WEAR_TAKE", 
        "value": 1
      }, 
      {
        "note": "WEAR_HOLD", 
        "value": 16384
      }
    ], 
    "weight": 1
}
```

Usage
-----

This repository uses `uv` and requires the Python version declared in
`pyproject.toml`. Install the environment from this directory:

    uv sync

To convert the bundled `assets/obj/30.obj` file to JSON, run:

    uv run circlemud-parse assets/obj/30.obj > 30.json
    
or

    uv run circlemud-parse --dest 30.json assets/obj/30.obj
    
These are equivalent. The file extension selects the parser. Entry-level
parse errors are logged to `stderr`; successfully parsed entries are still
written to the JSON output.

The upstream parser project also publishes converted stock CircleMUD files
in its [`output` folder](https://github.com/isms/circlemud-world-parser/tree/master/output).

Other notes
-----------

### Converting a whole `world` directory

You may want to convert all of the files in the CircleMUD world folder (typically found at `lib/world/`).

A bash script, `convert_all.sh`, is also included. It parses the five classic
world types (`mob`, `obj`, `shp`, `wld`, and `zon`) to JSON in a folder called
`_output/` by default while maintaining the same folder structure. Given a
folder like this:

    world
    ├── mob
    ├── obj
    ├── shp
    ├── wld
    └── zon

You can run the following command:

    ./convert_all.sh world/

And you will end up with this:

    _output
    ├── mob
    ├── obj
    ├── shp
    ├── wld
    └── zon

The new folders will have JSON files instead of `.obj`, `.mob`, `.wld` and so forth.

### Make shortcuts

Tests can be run with `make test`. `make all` converts the bundled files under
`assets/` into `_output/`. The repository-level
`week0_explore/bin/convert-world` helper additionally converts `trg` and `qst`
files into `week0_explore/preview/data/world/`.

### Non-standard codebases

Heavily modified codebases may not be parsed correctly. Any extra fields or non-standard entries are likely to cause parsing errors. Notes on bitvector entries (such as HUMMING or ANTI-MAGE) are based on the stock CircleMUD values, so if the MUD has added extras these won't be recognized and will end up as `null` in JSON.

These are all stored in `constants.py` which should be easy to change.
