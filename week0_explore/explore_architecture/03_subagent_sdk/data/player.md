# Player State

## Basic Info
- **Name:** Dummy the Believer (Dummy)
- **Class:** (newbie - not yet set)
- **Level:** 1
- **Race:** Human (17 years old)

## Location
- **Room:** Temple of Midgaard — southern end of temple hall
- **Map Coordinates:** (not yet verified)

## Vitals
- **Hit Points:** 16/100
- **Mana:** 100
- **Moves:** 83/83
- **Armor Class:** 39/10
- **Alignment:** 0

## Equipment
- **Worn:** candle (light), leather ring x2, gorget x2, breastplate, cap, bronze leggings, boots, gloves, sleeves, shield, cape, belt, wristguard x2; small sword (wielded)
- **Held:** metal staff

## Inventory
- **Carried Items:** Nothing

## Currency
- **Gold:** 0
- **Spirit Stones:** unknown

## Status Effects
- Hungry
- Thirsty

## Current Objective
Level up enough to defeat the Massive Minotaur in the Newbie Zone. Blocked at level 1 (0/1499 exp). Must find gold, feed self, obtain water, and earn XP first.

## Session Notes (v2)
- **Session stability issues:** MUD crashed twice when Smarty vanished during ATM interaction attempt. Likely a server bug triggered by the ATM commands. After reconnection both crashes resolved.
- **Atm/Bank system:** Commands confirmed via help atm: `deposit`, `withdraw`, `balance` — available at any Bank of Ilniyr location, NOT directly usable on wall-mounted ATMs in this room. Smarty told me "hello" when I typed balance (NPC hijacked the command).
- **NPC interaction:** "ask smarty about gold" → no response. "talk to smarty about money" → Smarty says '"hi"' (greeting only). NPC interactions may be disabled when hungry/thirsty. Need to resolve status effects first or find proper dialogue triggers.
- **Crash prevention:** Avoid commands that cause server crashes — particularly ATM-related commands in this room and any actions involving pagination output. Keep command output short.

## Where We Left Off (2026-07-21)
**Status at handoff:** Ready to peek into the Donation Room (east exit) but had only 4/4 commands used — checkpoint already saved before attempting movement.
**Pending actions for next session:**
1. Enter the Donation Room (east) and examine what's there — could be a gold/source quest trigger
2. Explore the Reading Room (west) — common starting area for MUDs
3. Head south down the temple square to find NPC vendors or quest givers
4. North exit may lead to more exploration — map all exits systematically
5. Find food/water sources ASAP to stop status effect penalties
6. Figure out how to get the initial gold (0 gold is blocking everything) - probably a quest trigger somewhere
**Key blockers:** Zero gold, zero XP, hungry + thirsty debuffs. Cannot access ATM banking from current room per help atm output. Smarty's NPC script unclear — only responds with greetings so far.
**Session command count when stopped:** 4/4 used (balance, all kill dummy, ask smarty about gold, talk to smarty about money)

## Notes
- Fully equipped with starter gear despite having zero gold.
- `equipment` command reveals player stats (HP, MP, MV, AC, alignment, exp, level) on this tbaMUD instance.
- `inventory` shows status effects rather than carried items on this MUD; look in inventory confirms nothing carried but look at self or equipment shows worn/held.

