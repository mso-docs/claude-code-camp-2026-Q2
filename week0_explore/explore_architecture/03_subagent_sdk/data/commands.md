# Confirmed MUD Commands

This is positive-only command memory. Add syntax only after current captured
game output proves it worked. Never record failed guesses here.

| Command | Confirmed behavior |
| --- | --- |
| `look` | Show the current room and visible contents. |
| `exits` | Show exits from the current room. |
| `score` | Show character vitals and progression. |
| `inventory` | Show carried items. |
| `help <topic>` | Show in-game help for a topic. |
| `north`, `south`, `east`, `west`, `up`, `down` | Move through a matching available exit. |
| `save` | Request character persistence on the game server. |

Movement aliases such as `n` may work, but use the explicit forms above until
live output in this project confirms an alias.
