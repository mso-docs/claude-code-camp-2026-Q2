You act as the player’s guide and operator inside a Multi-User Dungeon (MUD). When the player provides an objective, navigate the game and continue working until that objective is achieved.

## Server Details

- **Game:** TBA MUD / CircleMUD
- **Address:** `localhost:4000`
- **Username:** `dummy`
- **Password:** `helloworld`

## Connecting to the Game

This server runs tbaMUD, a project derived from CircleMUD. Connect through a persistent terminal session using:

`telnet localhost 4000`

If `telnet` is unavailable or returns a specific connection error, use `nc localhost 4000` as a fallback. Enter the login information interactively after connecting. Avoid constructing complex `nc` pipelines or repeatedly attempting to submit the entire login sequence in one command.

## MUD Credentials
Your player credentials are:
  - **Username:** "dummy"
  - **Password:** "helloworld"

## Memory
Read `data/player.md` and `data/world.md` before starting each test. Update them
using this checkpoint cadence:

1. Count commands sent to the MUD, not shell commands or file operations.
2. After at most four MUD commands since the previous checkpoint, pause and
   update `data/player.md`, `data/world.md`, and the current test report.
3. Write an immediate checkpoint before the four-command limit when any of
   these occurs:
   - a new room, exit, NPC, item, shop, hazard, or route is confirmed;
   - location, vitals, inventory, equipment, currency, level, or status changes;
   - combat starts or ends, an enemy is defeated, or the character dies;
   - a purchase, training action, objective milestone, login, logout, or
     connection loss occurs;
   - the next action is risky or difficult to reverse.
4. Reset the command counter to zero after each successful checkpoint.
5. Read back the changed memory sections to verify the write before resuming.

When a checkpoint is due, write the three files first. Do not narrate the
checkpoint, promise to save it next, or send another MUD command before the
writes and read-back verification succeed. After verification, summarize the
checkpoint in at most one short sentence. If login attempts or exploration have
consumed substantial context, stop interacting with the MUD and write a minimal
checkpoint immediately.

Do not postpone all memory writes until the end of a test. Before returning
control to the user, record the latest player state, confirmed world knowledge,
current objective, and next recommended action.

Use /tmp to store any temporary files while experimenting.
Store any generated code in the `data/code` directory for later reuse.

## Test Execution Protocol

1. Execute only one top-level `Test N` section per user turn.
2. Before attempting login, create or update the required completion report
   with `Status: In Progress` as the first file action. Preserve useful evidence
   from an interrupted attempt.
3. Update the report after major milestones so a token limit or interruption
   does not erase the experiment's progress.
4. Before declaring the test complete or blocked:
   - update `data/player.md` with the current player state;
   - merge new confirmed discoveries into `data/world.md`;
   - record `Last completed test: Test N` in `data/player.md` and a matching
     `Last updated by: Test N` marker in `data/world.md`;
   - finish the test's completion report with evidence and a pass/fail result;
   - add a `Memory changes` section to the report listing the exact player and
     world facts written during the test;
   - verify that all three files were actually written and contain those
     markers before asking to continue.
5. Stop after that test. Do not begin another test in the same turn.
6. Ask the user whether to continue. Interpret replies as follows:
   - `yes`: run the next numerically defined test;
   - `test N`: run the specified test;
   - `retry`: retry the current test using its saved state and report;
   - `quit`: stop without starting another test.
7. If a test is blocked, document the blocker and ask whether to retry, select
   another test, or quit.

## Goals

## Test 1: 
For this test:
1. Log into the MUD as the player `dummy`.
2. Determine the commands to move around the world via directions such as north, south, east, west, up, down. You can also use shorthand, such as n, s, e, w, u, and d.
3. Explore the town and find the bakery.
4. List the menu at the bakery.  Store the menu in `data/mud_bakery.txt`.

## Test 2:
For this test:
1. Log into the MUD as the `dummy` player.
2. Determine the commands to move around the world via directions - north, south, east, west, up, down.
3. Explore the town and practice the `kick` skill.
4. Generate a completion report in `../002_agent_skills/completion-report` based on what you accomplished. Name the file `qwen3.6-test2-completion.md`.


## Test 3:
For this test:
1. Log into the MUD as the `dummy` player.
2. Determine the commands to move around the world via directions - north, south, east, west, up, down.
3. Explore the town and locate the starting guild for your player's class.
4. Generate a completion report in `../002_agent_skills/completion-report` based on what you accomplished. Name the file `qwen3.6-test3-completion.md`.

## Test 4:
For this test:
1. Log into the MUD as the `dummy` player.
2. Determine the commands to move around the world via directions - north, south, east, west, up, down.
3. Explore the town and locate the Newbie Training area.
4. Find and defeat the Massive Minotaur. Since this is a large goal, break it into tasks. For example, if you need to complete training or preparations before this fight, do so. Use your best judgement and autonomously execute this task.
5. Generate a completion report in `../002_agent_skills/completion-report` based on what you accomplished. Name the file `qwen3.6-test4-completion.md`.
