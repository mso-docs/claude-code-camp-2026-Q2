Read `./AGENTS.md` and `../002_agent_skills/play-mud/SKILL.md` completely. Treat
`AGENTS.md` as the task definition and use the generated `play-mud` skill as the
operating workflow.

This is an interactive, checkpointed evaluation of the top-level sections
`Test 2`, `Test 3`, and `Test 4`. The numbered items inside each test are steps
belonging to that test; they are not separate test numbers.

At the beginning of the first turn, inspect the three required report paths.
If the user explicitly requests `test N`, select that test. Otherwise, select
the earliest test from Test 2 through Test 4 that does not have a report marked
`PASSED`. A fresh evaluation therefore starts with Test 2, while an interrupted
evaluation resumes at the earliest unfinished test. Execute only the selected
test in that turn.

On later user turns:

- `yes` means execute the next test in sequence: Test 3 after Test 2, then Test
  4 after Test 3.
- `test N` means execute only the specified top-level test.
- `retry` means retry the most recently attempted test using the saved report
  and memory.
- `quit` means stop without running another test.

Never begin the next test until the user replies. After Test 4, `yes` does not
select a nonexistent test; ask the user to specify another test or quit.

The required reports are:

- Test 2: `../002_agent_skills/completion-report/qwen3.6-test2-completion.md`
- Test 3: `../002_agent_skills/completion-report/qwen3.6-test3-completion.md`
- Test 4: `../002_agent_skills/completion-report/qwen3.6-test4-completion.md`

Create `../002_agent_skills/completion-report` if it does not exist. Produce
one separate report for each selected test over the course of the interactive
evaluation. Create or update only the current test's report, use the exact
filename above, and never combine multiple tests into one report.

Logging in and confirming the movement commands are required steps within each
test. You have permission to connect only to the MUD at `localhost:4000` using
the credentials supplied in `AGENTS.md`.

Use existing completion-report statuses only to select the next unfinished
test. Existing player, world, menu, helper-script, and report content provides
context, but it is not live proof that the newly selected test succeeded.
Verify the selected test through current MUD interaction.

Maintain one long-lived connection while exploring. Count commands sent to the
MUD and write a checkpoint after no more than four MUD commands. At each
checkpoint, update `data/player.md`, `data/world.md`, and the current report,
then read back the changed sections before resetting the counter. Shell and
file commands do not count as MUD commands.

Do not wait for four commands after discovering a new room, exit, NPC, item,
shop, hazard, or route; after a player-state change; at the start or end of
combat; after a purchase, training action, objective milestone, login, logout,
death, or connection loss; or before a risky action. Write those checkpoints
immediately.

Update current state in `data/player.md` and merge confirmed locations, exits,
NPCs, items, services, hazards, and routes into `data/world.md`. Correct stale
facts in place, preserve genuinely new information, and mark uncertain
destinations as unconfirmed. Base memory on captured game output, not recalled
chat history or assumptions. Do not put credentials in memory, scripts,
transcripts, or reports.

At the final memory checkpoint, write `Last completed test: Test N` to
`data/player.md` and `Last updated by: Test N` to `data/world.md`, using the
actual selected test number. If no new world fact was discovered, preserve the
world data and state that explicitly in the report instead of inventing one.

Create or update the selected test's report at the beginning with `Status: In
Progress`. Update it after major milestones. Before responding to the user,
finish it with the actions taken, evidence observed, final player state,
failures and recovery attempts, unclear skill instructions, and a clear
pass/fail result. Include a `Memory changes` section naming the exact facts
written to `data/player.md` and `data/world.md`. Verify that the report and both
memory files contain the current test's markers before asking the user to
continue.

Keep conversational narration concise and store detailed evidence in the
report. Continue using terminal and file tools until the selected test is
complete or concretely blocked. Do not merely explain how to perform the task,
do not report success based only on existing files, and do not start a second
test in the same turn.

End the turn with one short checkpoint question:

`Test <current> is complete/blocked and its report and memory are saved.
Continue to Test <next>? Reply yes, test <number>, retry, or quit.`
