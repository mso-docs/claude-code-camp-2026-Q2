# Expedition Journal: Dummy's Accidental Sewer Crawl

This is my map based on the dungeon I fell into. I went to my guild to practice `kick` and I ended up falling into the sewer and getting stuck there for about 1.5 hours. I had to make this map to understand where I was, as I was going in circles for a long time. I ended up getting to level 3 after fighting tons of spiders, bats, and rats.

Here is my map:
```txt
# Dummy's Midgaard Sewer Expedition

                                 MIDGAARD

                             Temple Square
                                   |
                                   |
                             Market Square
                                   |
                                   |
                             Common Square
                                   |
                                   |
                                The Dump
                                   |
                                   D
                                   |
                 Quadruple Junction Under The Dump
                     (N E S W U)
                                   |
                                   S
                                   |
                           A Triple Junction
                             (N E W)
                                   |
                                   W
                                   |
                     Muddy Sewer Junction
                           (N E S)
                           /     \
                          /       \
                         N         E
                         |         |
               Muddy Sewer Bend    ---- Exit Route
                    (S W)
                         |
                         S
                         |
                Muddy Intersection
                    (N E S)
                         |
                         S
                         |
           Large Sewer Junction (Air Shaft)
                  (N E S W)
                         |
                         S
                         |
              Bend In Sewer Pipe
                    (N E)
                         |
                         E
                         |
               Ordinary Junction
                    (N E W)
                         |
                         E
                         |
                Triple Junction
                    (N E W)
                         |
                         E
                         |
                     Junction
                    (N E W)
                         |
                         E
                         |
                 Dark Passageway
                    (N E W)
                         |
                         E
                         |
               Watery Sewer Bend
                    (N W)
                         |
                         N
                         |
                 Watery Sewer
                    (N S)
                         |
                         N
                         |
            Watery Sewer Junction
                   (N E S)
                         |
                         N
                         |
                 Watery Sewer
                    (N S)
                         |
                         N
                         |
              Watery Sewer Bend
                    (S W)
                         |
                         W
                         |
          Edge of the Water Sewer
                    (E W)
                         |
                         W
                         |
                  Small Room
                    (E S)
                         |
                         W
                         |
                  Round Room
                     (E)
                         |
                         W
                         |
                   The Sewer
                   (E S W)
                         |
                         S
                         |
             Another Intersection
                    (N E S)
                         |
                         S
                         |
                A Junction (Clean)
                    (N S W)
                         |
                         S
                         |
                Sewer Junction
                    (N E W)
                         |
                         W
                         |
                Old Well (Sewer)
                    (E D)
                         |
                         D
                         |
               Down the Old Well
                         |
                         U
                         |
                    Old Well
                         |
                         |
                 Warrior Guild Area
                         |
                    Market Square
```

## AI Agent's Map of Midgaard

Codex 5.6 Sol created a map of Midgaard, which I thought was interesting. I've left it here:
```txt
                                                    [Common Square]
                                                          ^
                                                          N
                                                          |
                                                     [The Dump] ★
                                                          ^
                                                          U
                                                          |
                         +---------------- [Quadruple Junction Under The Dump] ----------------+
                         | W                         | N                       E                | S
                         v                           v                         v                v
          [Odd Room With Smooth Walls]      [Triple Junction]              [The Pit]    [A Triple Junction]
                         | D                     /         \                    | D         /             \
                         v                     W             E                  v          W               E
             [An Odd Intersection]   [Quiet Pipe Junction] [Sewer Pipe Bend] [Under       [Ordinary      [Junction Going
                    /       |             /        |              | N          The Pit]    Junction]       Three Ways]
                   W        E            W         E              v               | W       /   |            /      \
                  v         v            v         v       [Bend In The           +--------+    N           N        E
 [Junction In Sewer Pipes] [Under      [Ordinary  [Triple    Sewer Pipe]                        |           v        v
       /        |          The Pit]     Bend]      Junction]      | W                       [Sewer     [Sewer     [The Junction]
      W         N             ^          | S          | S         v                         Junction] Entrance]    /         \
     v          v             |          v            v     [Sewer Junction]                  | N         | N      N           E
[Under The  [Muddy Bend]      +---- [Sewer Junction] [Quadruple Junction]                     v           v      v            v
 Dark Pit]      | W                       | W          Under The Dump]                   [Ordinary     [The Shaft] [The Sewers] [Dark
   | U          v                         v                                                Bend]          | D      dead end    Passageway]
   v      [Under The Mudhole]       [Main Sewer Junction]                                  | E           v                       / \
[Dark Pit]         ^ D                 /    |     |    \                                    v      [Under The Shaft]             N   E
   | E             |                  W     N     E     S                         [Quiet Pipe Junction]       | W                |   |
   +------> [Main Sewer Junction]     |     |     |     |                                  | N               v                |   v
                                      |     |     |     +--> [Bend In Sewer Pipe]           v        [Narrow Eastern Ledge]     | [Watery
                                      |     |     |                  | E              [Muddy Sewer Pipe]       (south)           |  Sewer Bend]
                                      |     |     |                  v                  /          \               ^ N           |      | S
                                      |     |     +--------> [Ordinary Junction]       W            E              |             |      v
                                      |     |                       | E                v              v      [Narrow Eastern      | [Watery Sewer]
                                      |     |                       +----------> [Muddy Sewer]     [The Sewer]   Ledge]             |      | S
                                      |     |                                      (east bend)      /   \         (lower)          |      v
                                      |     |                                         | S          E     S           ^ N           | [Watery Sewer]
                                      |     |                                         v            |     |           |              |      | S
                                      |     +--> [Muddy Intersection] <---W--- [Muddy Sewer]        |     v      [Narrow Eastern    |      v
                                      |              /       \               (west bend)            | [Another       Ledge]         | [Watery Sewer
                                      |             N         E                    | E               | Intersection]  (middle)        |  Junction]
                                      |             |         |                    v                 |    /     \        ^ N           |    /     \
                                      |             v         v             [Muddy Sewer Pipe]       |   E       S       |              |   E       S
                                      |      [Muddy Sewer   [Muddy                | E                 |   |       |  [Narrow Eastern    |   v       v
                                      |       Junction]     Sewer]                v                   |   v       v   Ledge]            | [Ledge] [Watery
                                      |       /      \    (thigh-deep)         [The Sewer]            | [Three  [A Junction]            |    | S    Sewer]
                                      |      N        S       | N                /   \                |  Way      /      \               |    v       | S
                                      |      |        |       v                 E     S               | Junction] W       S              | [Ledge]    v
                                      |      v        v  [Muddy Intersection]   |     |               |   | S     |       |              |    | W  [Watery Sewer
                                      | [Muddy Sewer] [Mudhole]       /    \     |     v               |   v       v       v              |    +-> Junction]
                                      | (north end)      | D         N      E    | [Another            | [Sewer  [Muddy [Sewer Junction]  |          /     \
                                      |                  v          |      |    | Intersection]       | Store   Intersection]  /   \     |         E       S
                                      |          [Under The Mudhole] |      |    |      | S             Room]       | E       W     E    |         |       v
                                      |                             v      |    |      v                         [A Junction] |     |    |         v   [Watery Sewer]
                                      |                    [Bend In Muddy  |    | [A Junction]             /       |       |     |    |  [Ledge By     | S
                                      |                     Sewer]          |    |    /       \             W        S       |     |    |   Dark Pool]   v
                                      |                       | W           |    |   W         S            |        |       |     |    |       | S   [Watery
                                      |                       v             |    |   |         |            v        v       |     |    |       v     Sewer Bend]
                                      |                [Muddy Sewer]       |    |   |   [Sewer Junction] [Muddy [Sewer      |     |    |  [Ledge By      | W
                                      |                (cold bend)         |    |   |      /       \      Intersection] Junction] |    |   Dark Pool]     v
                                      |                    | N             |    |   |     W         E          | E      | E   |    |       | D   [Dark Passageway]
                                      |                    v               |    |   |     |         |          +--------+     |    |       v          ^
                                      |               [Muddy Sewer]        |    |   |     v         v                        |    |   [Fissure Under   |
                                      |               (porridge)           |    |   | [Old Well] [Bend In Sewer Pipe]        |    |    The Ledge]     |
                                      |                                    |    |   |     | D           | S                  |    |       | D           |
                                      |                                    |    |   |     v             v                    |    |       v             |
                                      |                                    |    |   | [Down The   [Sewer Pipe Bend] ---------+    | [Edge Of Water]    |
                                      |                                    |    |   |  Old Well]                                    | U                |
                                      |                                    |    |   |     | D -> NO EXIT                           +------------------+
                                      |                                    |    |   |
                                      |                                    |    +---+----------------> [Round Room]
                                      |                                    |                              | E (one way)
                                      |                                    |                              v
                                      |                                    |                         [Small Room]
                                      |                                    |                           /       \
                                      |                                    |                          E         S
                                      |                                    |                          v         v
                                      |                                    |                  [Edge Of Water  [Sewer Pipe]
                                      |                                    |                       Sewer]          | S
                                      |                                    |                          | E           v
                                      |                                    |                          +-----> [Watery Sewer   [Grand Sewer]
                                      |                                    |                                   Bend]            /      \
                                      |                                    |                                     | S           E        S
                                      |                                    |                                     v             v        v
                                      |                                    |                               [Watery Sewer] [Dark Hallway] [South End
                                      |                                    |                                     | S           | S       Of Grand Pipe]
                                      |                                    |                                     v             v             | W 🚪
                                      |                                    |                               [Watery Sewer] [Dark Passageway]         v
                                      |                                    |                                     | S           | S       [Pool In Sewer]
                                      |                                    |                                     v             v             | N
                                      |                                    |                               [Watery Sewer  [Dark Passageway]         v
                                      |                                    |                                Junction]          | S       [Sewer Room]
                                      |                                    |                                  /    \            v             | N
                                      |                                    |                                 E      S     [Dark Passageway]         v
                                      |                                    |                                 |      |            | S       [Sewer Room]
                                      |                                    |                                 v      v            v             | W 🚪
                                      |                                    |                              [Ledge] [Watery] [Dark Passageway] <-----+
                                      |                                    |                                 |       |
                                      |                                    |                                 v       v
                                      |                                    |                              [Ledge] [Watery Sewer]
                                      |                                    |                                         |
                                      |                                    +---------------- WATER LOOP <------------+
                                      |
                                      +-------------------------- LOWER LEDGE / ABYSS SYSTEM --------------------------+
                                                                 |
                                                         [An Odd Intersection]
                                                                 | N
                                                                 v
                                                   [Southwestern Corner Of Ledge]
                                                        /             \
                                                       N               E
                                                       v               v
                                                [Narrow Ledge]    [Broad Ledge]
                                                     | N            /    |     \
                                                     v             N☠    E      S
                                                [Narrow Ledge]  [Mid-Air] |      v
                                                     | N                   v   [Sewer Line]
                                                     v           [Southeastern  | D
                                                [Narrow Ledge]      Corner]      v
                                                     | N               | N    [Sewer Drain]
                                                     v                 v      /          \
                                         [Northwestern Corner]  [Narrow Eastern Ledge] W            E
                                                /       \               | E             v            v
                                               D         E              v         [Boring Drain] [Sewer Drain]
                                               |         v       [Under The Shaft]     | N            | E
                                               |  [Narrow Ledge East-West] | U          v              v
                                               |         | E              +------ [Dry Sewer Drain] [Sewer Drain]
                                               |         v                           | E                | E
                                               | [Northeastern Corner]                v                  v
                                               |       /       \              [Half-Dry Drain]      [Sewer Bend]
                                               |      D         S                 /       \              | N
                                               |      |         v                E         N             v
                                               |      v   [Narrow Eastern]       v         v        [Sewer Junction]
                                               | [The Entrance]   Ledge]   [Very Small] [Under Water]    /    |     \
                                               |      | N           | S       Room          | N         N     S      W
                                               |      v             v                         v          v     v      v
                                               | [The Corridor] [Narrow Eastern]         [Half-Wet]  [The Sewer] [Sewer Bend]
                                               |      | E            Ledge]                 Drain      dead end       |
                                               |      v                | S                    | N                     W
                                               | [Realm Of Lost] [Narrow Eastern]             v                       v
                                               |     Souls             Ledge]          [Four-Way Junction]      [Strange Sewer]
                                               |      | N                | S             /    |     |    \               | W
                                               |      v                  v             N      E     S     W              v
                                               | [T-Crossing]      [Narrow Eastern] [Small  [Sewer [Half- [Crawlway] [Damp Sewer]
                                               |   /      \             Ledge]        Cave]  Drain] Wet]      | W          | W
                                               |  W        E              | E                 | N   Drain      v            v
                                               |  v        v              v                   v         [Lair Entrance] [Strange Sewer]
                                               | [Fire- [Hell Yard] [Under The Shaft]    [Sewer Drain]       | N 🚪         | W
                                               | death]     | N 🚪                             | E             v             v
                                               |       [Torture Room]                    [End Of Drain]     [The Lair]   [The Sewer]
                                               |                                                            | N          | N
                                               |                                                            v            v
                                               |                                                        [The Lair]   [Sewer Drain]
                                               |                                                         /      \          | E
                                               |                                                        N        E         v
                                               |                                                        v        v     [Rat's Lair]
                                               |                                                   [The Lair] [The Lair]
                                               |                                                     /    \       | S
                                               |                                                  N 🚪     E      v
                                               |                                                   v       v   [The Lair]
                                               |                                             [Inner Lair] [The Lair]
                                               |                                                | W 🔒       | S
                                               |                                                v            v
                                               |                                            [Treasury]   [The Lair]
                                               |
                                               +----D🚪----> [Wall Of The Abyss] ----D----> [On The Walls Of The Abyss]
```
## Objective

My original objective was to visit the Weapon Shop and purchase a dagger for the tutorial.

## What Actually Happened

Instead, I accidentally fell down the Old Well outside the Warrior Guild and became trapped beneath Midgaard in the city's sewer system.

Rather than restarting, I decided to explore.

Over the next hour I manually mapped much of the sewer while fighting spiders, bats, and sewer rats. The sewer turned out to be far larger than expected, consisting of several interconnected regions including muddy tunnels, water-filled passages, dark corridors, and large sewer junctions connected beneath the city.

One sewer rat awarded over 1,100 experience points, allowing Dummy to advance from **Level 2 to Level 3** before ever buying the tutorial dagger.

Eventually I discovered a second exit from the sewer beneath **The Dump**, which led north into **Common Square**, bringing me safely back to Midgaard.

From there I visited the Weapon Shop and finally completed the original objective by purchasing:

- Dagger (13 gold)
- Small Sword (79 gold)

## Final Statistics

- Final Level: 3
- Experience: 4,313
- Gold Remaining: 197
- Weapons Purchased:
  - Dagger
  - Small Sword

## Lessons Learned

This accidental detour taught far more than the intended tutorial:

- Manual dungeon mapping
- Reading room descriptions instead of relying on room names
- Managing movement points through resting
- Hunger and thirst mechanics
- Combat against multiple enemy types
- Saving frequently
- Discovering alternate entrances and exits to the same dungeon

Although the tutorial expected me to buy a dagger first, exploring the sewer became the most memorable part of the adventure and provided a much deeper understanding of how MUDs are designed.

---