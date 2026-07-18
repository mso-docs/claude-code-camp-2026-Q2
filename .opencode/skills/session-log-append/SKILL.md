# Skill: session-log-append

## Purpose

Append (never overwrite or delete) learnings from every MUD gameplay session into the persistent memory files `data/player.md` and `data/world.md`. This ensures all knowledge compounds across sessions regardless of interruption.

## Rules

1. **Always read** `data/player.md` and `data/world.md` before writing.
2. **Append new sections below existing content** — never delete, truncate, or clear prior entries. Use timestamps / session labels to separate discoveries.
3. If a section already exists with the same title (e.g., "Test 4"), append underneath it instead of duplicating.
4. Write at least two appends per session:
   - A **session summary** block in `data/world.md` under a timestamped heading (e.g. `## Session 2026-07-18 -- Test 4`).
   - A **state update** in `data/player.md` — vitals, location, gold, hunger, inventory, blockers, and next action.
5. Append one or more **checkpoint** entries when major discoveries occur (new room, new route, NPC dialogue that resolves a blocker, item obtained). Each checkpoint should:
   - Be timestamped.
   - State what was learned vs. what was already known.
   - Show the live output or command that proved it.
6. Append to `data/commands.md` (also appended — never rewritten) any newly proven working command syntax, alias, or behavior pattern. Do not append failed guesses.
7. Always run `session-log-append` **immediately before calling the user back** with a "Continue?" prompt, even if the session was truncated or blocked mid-flow.

## Session Log Format (append only)

```markdown
### --- Append: Session YYYY-MM-DD -- TEST <N> --- ###

[Session summary with context, purpose, and what was accomplished or blocked.]

#### NEW WORLD FINDINGS
- ...

#### PLAYER STATE UPDATE
- ...

#### CHECKPOINTS
- [timestamp] What happened, output evidence.

#### COMMANDS DISCOVERED
- ...

#### OPEN BLOCKERS FOR NEXT SESSION
- ...

#### NEXT RECOMMENDED ACTION
- ...

### --- END APPEND --- ###

```

## When to Activate

- At the **end of every MUD session**, no matter how short or truncated.
- After any **major discovery** (new room, confirmed route, NPC answer that resolves a blocker).
- Before returning control to ask **"Continue?"**.

## Important Constraints

- Never delete prior content. Ever. Use append-only semantics.
- If prior content already covers the same topic for a different test, keep both entries labeled with their respective test numbers and timestamps.
- Keep entries compact but complete enough that a future session could continue without replaying old experiments.
