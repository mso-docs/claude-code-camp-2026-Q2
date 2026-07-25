# Don't Trust the README — Diff the Code

A pattern showed up often enough across the 13-step port that it became a
standing practice rather than a one-off surprise: the Ruby reference's own
READMEs and per-step directory snapshots don't always agree with what the
Ruby *code* actually does. Trusting prose over a diff would have ported
several bugs and phantom features straight into the Python side. Collected
here because it is a theme that cuts across the whole
[porting log](porting-log.md), not a single step's story.

## README Claims That Turned Out to Be False

- **Step 01**: the Ruby README documents a `token_budget` field and
  `budget=`/`used=` output on `Context` that doesn't exist in the actual
  code at that step (or any step ported so far at the time) — it's
  describing a later, fuller state of `Context`. Ported what the code
  does, not what the README's forward-looking example shows.
- **Step 05**: the README credits this step with adding `LoopError` "for
  runaway agents" — it's real code, but it's never raised anywhere. The
  wind-down mechanism replaced whatever hard-raise design it implied.
  Ported for structural parity, flagged as dead code.
- **Step 07**: three separate staleness issues appear in one README — it is
  headed "Step 6" instead of 7, its options table lists a
  `token_budget: 8192` parameter that does not exist (the real parameter is
  `max_output_tokens:`), and it claims that only two backends are supported
  when the code handles all five.
- **Step 08**: the README's headline claim for this step — that
  `Logger#turn` "prints a `╔══ turn N ══╗` header" — is simply wrong.
  Diffing `logger.rb` directly against step 07 shows **zero changes**;
  `turn(n:)` already existed and only ever writes a JSONL line, never
  `puts`. This is the most misleading claim found in the whole port: not
  incomplete or stale like the others, but describing behavior the code
  flatly doesn't have.
- **Step 11**: the README credits this step with adding `Logger.subscribe`
  — it actually existed since step 07 in this port (confirmed: zero diff
  in `logger.py` from step 10).

## Snapshot Drift Between Per-Step Reference Directories

The Ruby reference ships one directory per step (`ruby/00_config`,
`ruby/01_struct_skeleton`, …), and they aren't strict incremental diffs of
each other — a method can vanish and reappear between steps with no
functional meaning behind it:

- `Config#mud_host`/`mud_username`/etc. and `errors.rb`'s `LoopError` both
  disappear in step 06's snapshot, then reappear unchanged in step 07 —
  confirmed by direct diff, not something either step's README mentions.
- Step 12's `Config` finally *reads* `mud_host`/`mud_username` for real
  (step 10's three-way `mud:` resolution) — six steps of "dead code kept
  for parity" turned out to matter eventually.

## The One Regression That Wasn't Just Drift: Step 09

Diffing `08_the_repl_loop` against `09_global_executable` (whose entire
stated scope is gem packaging) turns up three unexplained reversions:
the friendly 401 error message, the project-local `.boukensha/` config
resolution tier, and the REPL banner's rich formatting all silently
revert to earlier, worse behavior. Unlike the dead-code flip-flopping
above, this one is tested, working, user-facing behavior actually
regressing, with nothing in the step's README suggesting it's
intentional.

### Decision

The Python port carries step 08's better versions of
`client.py`/`config.py`/`repl.py` forward through step 09 rather than
reproducing the regression — reverting working, verified functionality to
match an apparently-accidental snapshot gap would make the port strictly
worse for no pedagogical reason. Flagged in the step 09 plan, the step's
own README, and the architecture doc, rather than silently diverging —
so it's easy to spot and reverse if it turns out there was a reason for
it after all.

## How This Changed the Later Plans

From step 06 onward, every plan explicitly diffs each "carried forward
unchanged" file against the previous step before trusting that label, and
treats the Ruby README as a hint to verify rather than a source of truth.
Step 12 (context management) is the clearest payoff: its README covers
roughly a third of what actually changed — the rest (a second circuit
breaker, reasoning-block normalization across all five backends, OpenAI's
full `/v1/responses` rewrite) surfaced only by diffing every file against
step 11.
