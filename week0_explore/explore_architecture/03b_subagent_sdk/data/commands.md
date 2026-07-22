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
| `look <name>` | Show a short description and health condition of a player/NPC in the room (e.g. `look smarty` -> "You see nothing special about him." + "Smarty is in excellent condition."). |
| `consider <name>` | Show a relative-difficulty message comparing you to the target (e.g. `consider smarty` -> "Would you like to borrow a cross and a shovel?"). |
| `wave <name>` | Perform a wave social gesture at the target (e.g. `wave smarty` -> "You wave to Smarty."). |
| `equipment` | Show items currently worn/wielded/held ("You are using: ..."). |
| `practice` | Show remaining practice sessions and known/unlearned spells or skills. |

Movement aliases such as `n` may work, but use the explicit forms above until
live output in this project confirms an alias.
