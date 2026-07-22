# Active MUD Quest

## Objective

Run the primary character and Smarty together, then determine and record
Smarty's age, gender, class, and current stats from live game evidence.

## Execution contract

- Log in the primary character and Smarty concurrently using their isolated
  sessions.
- Both characters must actively participate: each must execute and confirm at
  least one gameplay command while both sessions are live.
- Coordinate a safe shared activity or rendezvous when the live map permits;
  do not merely query Smarty and leave the primary character idle.
- On `start`, log in with the bundled tool and begin playing immediately.
- For Smarty, use live output to determine age, gender, class, and all stats
  shown by the server. Do not infer missing values.
- Live-confirm both characters' locations and Smarty's score, equipment, and
  inventory.
- Use existing memory as navigation leads, but verify rooms and exits live.
- Stop immediately on character death.
- Save and checkpoint each participating character independently.
- A successful result requires captured evidence for Smarty's age, gender,
  class, and stats; evidence that both sessions participated; one successful
  final `save` per character; and verified memory updates.

The objective comes from `week0_explore/CHALLENGES.md`. Edit this file when the
class assigns a different active quest; the agent workflow does not need to be
rewritten.
