# Week 1 Baseline Journal

The Week 1 deliverable was a line-for-line Python port of Andrew's Ruby
`boukensha` reference agent. I built it one numbered step at a time,
from `00_config` through `12_context`, planning each step before porting
it and verifying its behavior before calling it complete.

I followed Andrew's build order closely: watch the lesson, study that
iteration of the Ruby code, write the Python port, and compare the two
implementations. I did not read ahead and recreate the finished system
from its overall shape. That constraint made each architectural decision
visible as it arrived and exposed several places where the prose and code
had drifted apart.

After completing the strict port, I used the finished agent for the
Capable Challenge. That added local Ollama support, durable gameplay
memory, safer session logging, and several fixes discovered only through
long-running MUD sessions.

## Journal Entries

- [Porting Log](1_baseline/porting-log.md) — all 13 steps, condensed: what
  each one built, the trickiest Ruby→Python translation decision, and how
  it was verified.
- [Don't Trust the README — Diff the Code](1_baseline/reference-quirks.md) —
  the recurring pattern of README claims and reference-snapshot drift that
  didn't match the actual Ruby code, and the one real regression (step 09)
  that I deliberately did not reproduce.
- [Beyond the Port](1_baseline/beyond-the-port.md) — local Ollama model
  support, persistent agent memory, safer session logging, and operational
  fixes added after the strict port for the Capable Challenge.

See also the living [architecture diagram](../architecture-baseline.md)
and the per-step [plan docs](../plans/README.md) these entries summarize.

## Highlights

- Every one of the 13 steps has an independently verified Python
  counterpart under `week1_baseline/python/`, committed one step at a
  time from `02_the_registry` onward.
- Found and preserved several genuine Ruby quirks rather than "fixing"
  them on the way past: a leaky one-argument `to_messages` interface
  (step 03), a Ruby-truthiness gotcha around `max_output_tokens` that
  would have silently broken in Python if not caught (step 05), and an
  inconsistent dead `system_override?` method that checks the wrong
  settings key (step 12).
- Caught a real UI bug only via Textual's headless test harness: literal
  `"[interrupted]"` text was being silently swallowed as an unmatched
  Rich markup tag (step 11).
- Found one genuine, unexplained regression in the Ruby reference itself
  (step 09 quietly reverting three things step 08 had fixed) and chose to
  keep the Python port's better behavior instead of reproducing it —
  documented rather than silently diverged.
- Step 12 (context management) turned out to be the largest step in the
  whole port — bigger than the standard-tool-library step — with the Ruby
  README covering only about a third of what actually changed.
- Went past the strict port for the Capable Challenge: wired in local
  Ollama models (no API key required) and gave the agent persistent
  cross-session memory, without forking the finished port into a separate
  directory.
- Used real gameplay failures to harden the final iteration: distinguished
  an open socket from an authenticated MUD session, prevented accidental
  character creation, surfaced tool activity in the TUI, blocked direct
  `.env` reads, and redacted secret- and infrastructure-shaped values
  before session events reach either disk or live subscribers.

## Main Lesson

Porting is not translation — it's line-by-line verification against
behavior, not prose. The single habit that mattered most across all 13
steps was treating every "carried forward unchanged" label and every
README claim as something to diff and confirm, not something to trust.
That habit is what caught a dead code path here, a silent behavior change
there, and one real reference regression — and it's the difference
between a port that merely *looks* like the reference and one that's
actually been checked against it.
