# Active MUD Quest

## Objective

Level up enough to defeat the Massive Minotaur in the Newbie Zone.

## Execution contract

- On `start`, log in with the bundled tool and begin playing immediately.
- First live-confirm the character's location, score, equipment, and inventory.
- Use existing memory as navigation leads, but verify rooms and exits live.
- Break the objective into preparation, locating the Newbie Zone, and the final
  fight. Persist progress throughout; do not attempt the final fight while the
  captured state indicates the character is unprepared.
- Stop immediately on character death.
- A successful result requires captured evidence that the Massive Minotaur was
  defeated, one final successful `save`, and verified memory updates.

The objective comes from `week0_explore/CHALLENGES.md`. Edit this file when the
class assigns a different active quest; the agent workflow does not need to be
rewritten.
