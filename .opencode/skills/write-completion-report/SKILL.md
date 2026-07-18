---
name: write-completion-report
description: Create, name, incrementally update, and finalize MUD evaluation completion reports with consistent identity, objective, evidence, save, memory, and result sections. Use for every test run or retry that requires a completion report, especially when multiple agent harnesses or model variants must produce separate auditable files.
---

# Write Completion Report

Maintain one evidence report for each harness, full model identifier, and test.

## Select the Report Path

1. Identify the active harness, such as `opencode`, `pi`, `codex`, or
   `claude-code`.
2. Read the full configured model identifier. Do not shorten a model family in
   a way that makes two variants collide.
3. Convert both values to lowercase filename slugs. Replace `:`, `/`, spaces,
   and unsupported characters with `-`; collapse repeated hyphens.
4. Name the report
   `<harness>-<model-slug>-test<N>-completion.md` under the completion-report
   directory required by `AGENTS.md`.

Example: OpenCode plus `qwen3.6:35b-a3b` running Test 2 must use
`opencode-qwen3.6-35b-a3b-test2-completion.md`.

Never overwrite a report belonging to another harness, model, or test. Reuse
the same exact file for a retry and preserve useful evidence from earlier
attempts. Treat legacy reports with shorter names as read-only history unless
the user explicitly requests migration.

## Initialize Before Gameplay

Read [report-template.md](references/report-template.md) completely. As the
first file action for a selected test, create the unique report or update its
existing status to `In Progress`. Fill in the identity fields and every
numbered objective from `AGENTS.md`. Add a new attempt entry on retry instead of
erasing the previous attempt.

Do not connect, log in, or send a MUD command until the initialized report has
been written and read back.

## Update Incrementally

Update the same report before continuing whenever any of these occurs:

- environment readiness or login is confirmed;
- a numbered test step starts, completes, fails, or becomes blocked;
- the checkpoint cadence in `AGENTS.md` or `manage-mud-memory` is reached;
- a new live finding changes player state, world knowledge, or the route;
- combat, training, a purchase, death, disconnection, or recovery occurs;
- the final CircleMUD `save` command is attempted.

For each update:

1. Mark the affected objective `Pending`, `In Progress`, `Completed`, or
   `Blocked`.
2. Record concise findings backed by current captured MUD output.
3. Record the checkpoint number and number of MUD commands since the prior
   checkpoint.
4. List the exact facts written to player, world, or command memory. Record a
   command-memory change only for new syntax proven successful by current
   captured output; failed attempts stay in the report evidence only.
5. Update the report timestamp and read back the changed section before sending
   another MUD command.

Do not paste credentials, hidden reasoning, or unbounded terminal transcripts.
Quote only the minimum game output needed as evidence. Never defer all report
writing until the end of the test.

## Finalize

Mark `PASSED` only after every numbered objective is completed, the final
CircleMUD `save` is verified, both memory files are current, and all three files
have been read back. Otherwise record `BLOCKED` or `FAILED` with the exact
blocker, latest safe state, and next action.

Before returning control, verify that the filename identity matches the report
metadata and that no other harness/model report was modified.
