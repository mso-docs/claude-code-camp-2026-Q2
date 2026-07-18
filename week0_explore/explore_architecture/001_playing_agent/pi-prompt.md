Read `./AGENTS.md` and `../002_agent_skills/play-mud/SKILL.md` completely. Treat
`AGENTS.md` as the task definition and use the generated `play-mud` skill as the
operating workflow.

Execute the three top-level sections `Test 2`, `Test 3`, and `Test 4` in that
order. Do not execute `Test 1`. The numbered items inside each test are steps
belonging to that test; they are not separate test numbers.

- Test 2: practice the `kick` skill, then write
  `../002_agent_skills/completion-report/qwen3.6-test2-completion.md`.
- Test 3: locate the starting guild for the player's class, then write
  `../002_agent_skills/completion-report/qwen3.6-test3-completion.md`.
- Test 4: locate the Newbie Training area and defeat the Massive Minotaur, then
  write
  `../002_agent_skills/completion-report/qwen3.6-test4-completion.md`.

Create `../002_agent_skills/completion-report` if it does not exist. Produce
three separate reports with exactly the filenames above; do not combine the
tests into one report.

Logging in and confirming the movement commands are required steps within each
test. You have permission to connect only to the MUD at `localhost:4000` using
the credentials supplied in `AGENTS.md`.

Verify each goal through live interaction with the MUD. Existing player,
world, menu, helper-script, and completion-report files are prior-run evidence,
not proof that this run succeeded. You may read them for context, but do not
copy their conclusions without confirming them in the current game session.

Maintain one long-lived connection while exploring. After every meaningful
action, update `data/player.md` and `data/world.md` with confirmed observations.
Correct stale facts in place, preserve genuinely new information, and mark
uncertain destinations as unconfirmed. Do not put credentials in memory,
scripts, transcripts, or reports.

Each completion report must describe the actions taken, evidence observed,
final player state, failures and recovery attempts, unclear skill instructions,
and a clear pass/fail result for that test. Finish and save each report before
starting the next test.

Continue using terminal and file tools until Tests 2, 3, and 4 are complete or
a concrete blocker prevents further progress. If one test is blocked but the
character remains usable, document the blocker and proceed to the next test.
Do not merely explain how to perform the tasks, and do not report success based
only on existing files.
