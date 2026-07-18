Read `./AGENT.md` and `../002_agent_skills/play-mud/SKILL.md` completely. Treat
`AGENT.md` as the task definition and use the generated `play-mud` skill as the
operating workflow.

This run evaluates goals 2 through 4 from `AGENT.md`:

2. Identify the commands for moving north, south, east, west, up, and down.
3. Explore the live MUD and find the bakery.
4. Run the bakery's menu command and save the current menu to
   `data/mud_bakery.txt`.

Logging in is a prerequisite for the evaluation. You have permission to
connect only to the MUD at `localhost:4000` using the credentials supplied in
`AGENT.md`.

Verify each goal through live interaction with the MUD. Existing player,
world, menu, helper-script, and completion-report files are prior-run evidence,
not proof that this run succeeded. You may read them for context, but do not
copy their conclusions without confirming them in the current game session.

Maintain one long-lived connection while exploring. After every meaningful
action, update `data/player.md` and `data/world.md` with confirmed observations.
Correct stale facts in place, preserve genuinely new information, and mark
uncertain destinations as unconfirmed. Do not put credentials in memory,
scripts, transcripts, or reports.

Create `completion-report/qwen3.6-tests-2-4.md` containing:

- the connection method, without credentials;
- the movement commands tested and the evidence for each;
- the route taken to the bakery;
- the bakery menu command and output-file path;
- any failed commands, recovery steps, or skill instructions that were unclear;
- a final pass/fail result for goals 2, 3, and 4.

Continue using terminal and file tools until all three evaluated goals are
complete or a concrete blocker prevents progress. Do not merely explain how to
perform the task, and do not report success based only on existing files.
