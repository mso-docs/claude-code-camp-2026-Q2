# Smarty Checkpoint Log

Append-only chronological handoffs for the Smarty character.

## 2026-07-22T02:22:06.284169+00:00

- Status: in_progress
- Room: The Temple Of Midgaard (southern end of temple hall)
- Result: Login succeeded after several retries (server closed connection on first ~4 attempts at password_prompt_received stage, then succeeded via reconnecting stage). MUD_LOGIN_OK confirmed with live room text. Character title shown: "Smarty the Apprentice of Magic". Vitals bar: 16H 100M 83V.
- Player changes: Confirmed alive, located in Temple of Midgaard. HP 16, Mana 100, Move 83 (from prompt bar). Title suggests class = Magic User (apprentice rank).
- World changes: Temple of Midgaard (south end of temple hall): exits n e s w d. ATM machine in wall. Reading Room to west, donation room to east (small alcove). Large steps lead down to temple square.
- Next action: Run score, inventory, equipment (worn) commands to capture age/gender/class/stats live, then coordinate with primary character, then save.

## 2026-07-22T02:23:38.905911+00:00

- Status: in_progress
- Room: The Temple Of Midgaard (southern end of temple hall) - last confirmed before disconnect
- Result: Captured live score data via 'score' command (shown after a 1-command output lag pattern: each send() call's tool output includes prior command's response appended at the end, plus a full replay of login+room text since the underlying driver seems to reconnect fresh each call). Equipment command was sent but only echoed stale score text back (likely same lag). Inventory command then hit MUD_LOGIN_ERROR: server closed the connection / MUD_DRIVER_EXIT=1 - connection dropped again, same failure mode as earlier login attempts. Command gate hit 4/4, checkpointing now before retrying.
- Player changes: LIVE-CONFIRMED via 'score': Age 17 years old. HP 16(16), Mana 100(100), Move 83(83). Armor class 39/10. Alignment 0. Exp 1, gold 0, questpoints 0. Playing time 0 days 6 hours. Score title line: "This ranks you as Dummy the Believer (level 1)." (NOTE: name mismatch - character/tool label is 'Smarty' and room self-listing shows 'Smarty the Apprentice of Magic is standing here', but the score command's rank line literally says 'Dummy the Believer' not 'Smarty' - recorded verbatim as a discrepancy, not yet resolved; possible that 'Apprentice of Magic' (room sdesc) = class title = Magic User, while 'the Believer' (score rank line) may be a differently-sourced/stale title string. Class NOT yet fully confirmed - need to reconcile via further evidence, e.g. 'help' on class or a class-specific score line.) Gender: not yet observed in any output. Equipment/inventory: not yet captured (command lag + disconnect prevented capture).
- World changes: Temple of Midgaard (south end of temple hall) reconfirmed on reconnect: exits n e s w d, ATM in wall, Reading Room west, donation room alcove east, steps down to temple square.
- Next action: Call start again to reconnect (driver appears to require fresh reconnect after 'server closed the connection'). Then re-send 'equipment' and 'inventory' as separate calls, watching for the 1-call output lag. Also try 'who' or self-look to resolve the Smarty vs Dummy name discrepancy, and find gender (try 'help' or examine self, or 'diagnose self'). Coordinate with primary character once stats fully captured, then issue final 'save'.
