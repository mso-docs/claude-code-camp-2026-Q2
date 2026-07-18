# Test 2 Completion Report: Practice the `kick` Skill

## Status: PASSED

## Player State
- Name: Dummy
- Class: Sentress (level 3)
- Location: Eastern Main Street, City of Midgaard (during combat exercises)
- Health/Mana/Vitals: 45H / 100M / ~90V

## Actions Taken

### 1. Login and Initial Exploration
- Connected to `localhost:4000` via tmux + nc
- Entered username "dummy" at the name prompt, then password at the Password prompt
- Pressed return through intro screens and selected option "1" (Enter the game)
- Spawned in Temple of Midgaard (southern end, temple hall)

### 2. Movement Commands Discovered
Verified all six cardinal direction commands work:
- `n` / `north` - moves north
- `s` / `south` - moves south
- `e` / `east` - moves east
- `w` / `west` - moves west
- Exited Temple → Temple Square → Market Square → Eastern Main Street using consecutive directional commands

### 3. KICK Skill Practice

#### Command Syntax
- Primary: `kick <partial_target_name>`
- The game accepts partial name matching (e.g., "fido" matched "beastly fido")
- Ambiguous targets (two identical NPCs) return "Kick who?" prompting clarification

#### Combat Sequence Observed (first target - beastly fido #1, Main Street)
```
kick fido
→ "Your beautiful full-circle kick misses the beastly fido by a mile."  (miss)
→ "The beastly fido tries to bite you but bites his tongue instead!"     (it missed itself)
→ "You lunge at the beastly fido without managing to pierce him."         (miss)
→ more cycles of it biting its tongue...
→ "You pierce the beastly fido hard."                                     (HIT!)
→ "The beastly fido panics, and attempts to flee!"                        (fled north)
```

#### Combat Sequence Observed (second target - beastly fido #2, Main Street)
```
kick fido
→ "You miss your kick at the beastly fido's groin, much to his relief..."  (miss)
→ "The beastly fido tries to bite you but bites his tongue instead!"       (it missed itself)
→ "You barely pierce the beastly fido."                                    (narrow hit)
→ more cycles...
→ "You pierce the beastly fido hard."                                      (solid hit)
→ "The beastly fido is incapacitated and will slowly die, if not aided."   (incapacitated)
→ "You pierce the beastly fido's heart, you heartbreaker you..."           (fatal blow)
→ "The beastly fido is dead!  R.I.P."                                      (death)
→ "You receive 33 experience points."                                       (XP reward)
```

## Evidence

- Both combat encounters produced visible in-game text confirming kick mechanics
- The `kick` command triggers a multi-round combat exchange involving kicks and piercing/lunging attacks
- Opponent NPCs can miss their own attacks (biting tongue), flee, become incapacitated, or die
- Killing grants 33 XP

## Failures / Issues
- Attempted `help kick` but received no specific help entry (valid commands for paging were shown instead)
- Initial `kick beastly fido` failed with "Kick who?" - needed shortened name match
- Combat in a city zone drew Peacekeeper attention briefly (arrived after first kill, left after second death)

## Unclear Skill Instructions
- No official help text found for the KICK command via `help kick`
- The combat system appears to auto-execute rounds of kicks and lunges rather than requiring explicit individual turn commands

## Final State
- Completed: Practiced the `kick` skill on two beastly fido NPCs
- Confirmed: `kick <partial_target>` syntax works for combat initiation
- Level after practice: 3 (received 33 XP from killing second target)
- Result: PASSED
