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
Read `data/player.md`, `data/world.md`, and `data/commands.md` before starting
each test. Update them using this checkpoint cadence:

1. Count commands sent to the MUD, not shell commands or file operations.
2. After at most four MUD commands since the previous checkpoint, pause and
   update `data/player.md`, `data/world.md`, and the current test report. Update
   `data/commands.md` only when a new working command was live-confirmed.
3. Write an immediate checkpoint before the four-command limit when any of
   these occurs:
   - a new room, exit, NPC, item, shop, hazard, or route is confirmed;
   - location, vitals, inventory, equipment, currency, level, or status changes;
   - combat starts or ends, an enemy is defeated, or the character dies;
   - a purchase, training action, objective milestone, login, logout, or
     connection loss occurs;
   - the next action is risky or difficult to reverse.
   - a new working command, alias, or meaningful command syntax is confirmed.
4. Reset the command counter to zero after each successful checkpoint.
5. Read back the changed memory sections to verify the write before resuming.

When a checkpoint is due, write player memory, world memory, the current report,
and command memory when it actually changed. Do not narrate the checkpoint,
promise to save it next, or send another MUD command before the writes and
read-back verification succeed. After verification, summarize the checkpoint
in at most one short sentence. If login attempts or exploration have consumed
substantial context, stop interacting with the MUD and write a minimal
checkpoint immediately.

Do not postpone all memory writes until the end of a test. Before returning
control to the user, record the latest player state, confirmed world knowledge,
current objective, and next recommended action.

Use /tmp to store any temporary files while experimenting.
Store any generated code in the `data/code` directory for later reuse.

## TBA MUD Command Memory

Treat `data/commands.md` as the canonical positive-only glossary for this TBA
MUD server. Prefer it over command conventions recalled from stock CircleMUD,
SMAUG, or another MUD. Do not assume that commands are portable between
codebases.

Add or amend an entry only when current captured game output proves that a new
command, alias, or meaningful syntax worked as intended. Merge with an existing
entry instead of duplicating it. Do not add failed guesses, rejected syntax,
untested commands, or a catalog of what does not work. Failed attempts belong
only in the current completion report when they matter to the evaluation.

## Completion Report Identity

Create a separate report for every harness, full model variant, and test. Use
`<harness>-<model-slug>-test<N>-completion.md` in the required
`completion-report` directory. Convert the full model identifier to lowercase
and replace `:`, `/`, spaces, and unsupported filename characters with `-`.

For example, OpenCode with `qwen3.6:35b-a3b` running Test 2 uses
`opencode-qwen3.6-35b-a3b-test2-completion.md`. Never overwrite another
harness/model report. A retry updates the same unique report and preserves
earlier evidence.

Initialize the report with `Status: In Progress` before gameplay. Update it
after environment setup, login, every numbered test step, every memory
checkpoint, important finding, recovery, and final game save. Each update must
state the step status, current findings, MUD command count, exact memory
changes, and next action. Read back the changed section before continuing.

## Test Execution Protocol

1. Execute only one top-level `Test N` section per user turn.
2. Before attempting login, create or update the required completion report
   with `Status: In Progress` as the first file action. Preserve useful evidence
   from an interrupted attempt.
3. Update the report after major milestones so a token limit or interruption
   does not erase the experiment's progress.
4. Before declaring the test complete or blocked:
   - after every numbered objective step is live-confirmed, send the CircleMUD
     `save` command through the authenticated persistent session before marking
     the report PASS;
   - count `save` as a MUD command, capture its response, and verify that the
     game did not reject it or lose the connection;
   - if the test objective was achieved but the final game save cannot be
     verified, do not declare PASS; record the result as BLOCKED or FAIL;
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

The CircleMUD `save` command and the repository checkpoint are separate. The
game command persists the character on the server; the checkpoint persists the
evaluation state in `data/player.md`, `data/world.md`, and the completion report.
For a passing test, perform and verify the game save first, then write and read
back the final repository checkpoint.

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
3. Train the `kick` skill with Dummy's Sentress guildmaster:
   - navigate to the **Tournament and Practice Yard** inside the **Guild of
     Swordsmen**;
   - use the confirmed Temple route as a navigation lead: `s`, `s`, `e`, `e`,
     `s`, `e`, `s` (Temple Square → Market Square → two eastern Main Street
     segments → Entrance Hall → Bar of Swordsmen → Tournament and Practice
     Yard);
   - confirm each room from current game output instead of blindly replaying
     the route, because the character may start elsewhere;
   - confirm the guildmaster is present, then issue `practice kick` and capture
     the training response.

   Using `kick <npc>` starts combat and does **not** satisfy this test. Do not
   attack arbitrary NPCs as a substitute for guild training. If `practice kick`
   is unavailable because of class, level, practice points, or existing skill
   state, record the live response and mark the training step BLOCKED or FAILED
   instead of switching to combat.
4. Generate and maintain the harness/model-specific Test 2 report in `../002_agent_skills/completion-report`.


## Test 3:
For this test:
1. Log into the MUD as the `dummy` player.
2. Determine the commands to move around the world via directions - north, south, east, west, up, down.
3. Explore the town and locate the starting guild for your player's class.
4. Generate and maintain the harness/model-specific Test 3 report in `../002_agent_skills/completion-report`.

## Test 4:
For this test:
1. Log into the MUD as the `dummy` player.
2. Determine the commands to move around the world via directions - north, south, east, west, up, down.
3. Explore the town and locate the Newbie Training area.
4. Find and defeat the Massive Minotaur. Since this is a large goal, break it into tasks. For example, if you need to complete training or preparations before this fight, do so. Use your best judgement and autonomously execute this task.
5. Generate and maintain the harness/model-specific Test 4 report in `../002_agent_skills/completion-report`.
