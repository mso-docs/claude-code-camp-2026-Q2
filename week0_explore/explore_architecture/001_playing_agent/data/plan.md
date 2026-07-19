# Test 4 Plan Checklist

## Objective: Locate Newbie Training area & defeat Massive Minotaur

### Prerequisites (Cross-Session Checks)
- [x] Read `commands.md` — confirmed directional movement + help/examine/score/inventory/list/ask practice kick/flee commands
- [x] Read `player.md` — current state, position, vitals recorded
- [x] Read `world.md` — full Midgaard route map loaded
- [ ] Read test4-completion report for latest checkpoint evidence
- [x] MUD server on localhost:4000 — check before login
- [ ] Docker container started if port 4000 unavailable

### Critical Knowledge From Player (pending live verification)
**Combat/Loot/Recovery commands confirmed by player:**
- `kick <name>` / `kill <target>` → initiate combat
- `get all corpses` or `get gold` → loot from monsters
- `rest` → heals HP; requires wake + stand after
- `sleep` → restores movement; requires wake + stand after
- Monsters can attack during rest/sleep — always alert!
- Deposit gold in ATM after returning to city

**Command exploration:**
- Type `info` and press Enter to cycle through 3 pages of command listings (MUST VERIFY)
- `score` → shows character score and detailed vitals (confirmed from earlier tests)
- `inventory` → lists carried items (confirmed from earlier tests)  
- `wield <item>` → equip a weapon for combat (MUSTA VERIFY)

**Strategy:** Fight sewers/fields outside temple → loot corpses → earn gold → deposit in ATM → use gold to unlock gates and explore further

- [ ] Verify `list` command on remaining shops (General Store, Weapon Shop, Pet Shop) for additional goods/items beyond bakery and armory

### Current Blockers
- [x] Gold = 0 → "You're broke!" blocks all direction commands in TBA MUD
- [x] Hunger + thirst persistent states (may add penalties)
- [x] Donation Room east exit requires donation (standard temple gate behavior)
- [ ] Identify free or cheap gold source

### Quest Progress Log
1. **Test 1:** Bakery discovered — menu saved to `data/mud_bakery.txt` ✓
2. **Test 2:** Guild of Swordsmen route confirmed, guildmaster found in Tournament Yard ✓
3. **Test 3:** Eastern Main Street + East Gate + Water Shop mapped ✓
4. **Test 4 (current):** In progress — exploring toward Newbie Training / Massive Minotaur

### Step-by-Step Checklist

#### Phase 1: Break Gold Blocker (PRIORITY)
- [ ] Test `donate gold` in Donation Room alcove (east from temple hall)
- [ ] If donate works, try direction again to see if gate opens
- [ ] If donation gives gold in return, pursue; if it's one-way, find alternatives
- [ ] Check bulletin board at Reading Room for clues about free gold/resources
- [ ] Alternative: `ask benefactor about everything` or `ask benefaktor about help` — try broader topics for free gold/food/donation info

#### Phase 2: Explore Reading Room (West)
- [ ] Once mobile, go `w` to Reading Room
- [ ] Look at bulletin board inside for clues about newbie training area
- [ ] Check all exits and contents of the room
- [ ] Verify whether Reading Room IS the Newbie Training area

#### Phase 3: Explore All Unmapped Areas
- [ ] Go to Temple Square → Market Square → Common Square → The Dump → Down to sewers
- [ ] Search Quadruple Junction thoroughly (north, west exits unconfirmed)
- [ ] Visit The Pit and explore downward route
- [ ] Check Wall Road south exit for hidden areas
- [ ] Explore Dark Alley south toward Guild of Thieves

#### Phase 4: Find & Fight Massive Minotaur
- [ ] Identify minotaur location from clues
- [ ] Acquire party members or training if needed before combat
- [ ] Prepare gear/inventory for fight
- [ ] Execute combat strategy
- [ ] Verify kill and report loot/XP

#### Phase 5: Save & Cleanup
- [ ] `save` game via MUD session
 - [ ] Update player.md, world.md, commands.md with final findings
 - [ ] Finalize completion report with PASS/BLOCKED/FAIL

### Post-T4 Objectives (Future Sessions)
- [ ] Identify and practice all Sentess class skills
- [ ] Complete guild training progression
- [ ] Find all hidden areas of Midgaard
- [ ] Build character level/equipment systematically
- [ ] Document new room/exits/NPCs discovered
