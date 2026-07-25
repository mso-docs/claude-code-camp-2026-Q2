# Beyond the Port: Local Models, Memory, and Safer Operations

Once all 13 steps of the strict Ruby → Python port landed
(`692f80a — port step 12: context management (final step)`, see the
[porting log](porting-log.md)), work continued past the pure-port scope
for the Capable Challenge: running the step-12 agent against a local
Ollama model instead of Anthropic, then actually playing with it long
enough to need persistent memory and session logging. Real play sessions
then uncovered problems that the isolated port verification could not:
ambiguous login state, hidden tool activity, and sensitive values making
their way into committed logs.

All of this work lives inside `week1_baseline/python/12_context/` — the
final port step — rather than a separate directory. These are additive
changes to the version I actually run, not a parallel implementation (see
[`QUICKSTART.md`](../../../QUICKSTART.md) for the setup instructions and
the reasoning behind keeping it in place).

## Ollama Backend Support (`7237b8f`, `048912d`)

Three small, explicitly flagged additions went beyond the strict Ruby port:

- `qwen3.6:27b` and `qwen3.6:35b-a3b` were added to `Ollama.MODELS`
  (`boukensha/backends/ollama.py`) — models not in this table are
  rejected outright, so a local model has to be whitelisted before it can
  be selected at all.
- Both models were also added to `boukensha/models.py`'s `TABLE`, which the
  Ruby reference keeps Anthropic-only. Without this, `Context`'s
  `context_window` would fall back to a 32,000-token default and
  auto-compaction would fire far too early against a model with a much
  larger context window.
- `Config.ollama_host` reads `ollama.host` from `settings.yaml`. The Ruby
  reference has no settings-driven way to point at a non-default Ollama
  host.

Switching providers is a `settings.yaml` edit, no code change and no API
key: `provider: ollama`, `model: qwen3.6:27b`, plus an `ollama.host` block.

## Agent Memory and Logging (`f6a87d3`, `1d748e3`, `7720693`)

- `.boukensha/memory/player.md` and `.boukensha/memory/world.md` — the
  persistent state the agent reads and writes across sessions, an
  extension of the checkpoint discipline first developed during
  [preweek's MUD experiments](../0_preweek.md) (evidence-based memory,
  frequent checkpoints, no invented facts).
- `.boukensha/prompts/system.md` — the system prompt tying the agent to
  its memory files.
- `.boukensha/sessions/*.jsonl` — the step 06 JSONL session logger
  (see [porting log](porting-log.md#06--the-logger)) doing exactly what
  it was built for: a per-session structured record of every phase, now
  actually being read back to debug what the agent did during a real
  play session instead of just being verified in tests.
- One follow-up fix (`7720693`) after hitting an actual memory-loading
  bug while using the agent for real — the kind of problem that only
  shows up once there's a real memory file and a real multi-session
  history to load, not during the step's original unit-test verification.

The important shift was from conversation history to maintained state.
The JSONL log is an audit trail for debugging; the two Markdown files are
the agent's small, curated memory. The system prompt requires the agent to
read them at startup, verify saved claims against the live game, and
checkpoint after meaningful changes. That keeps stale observations from
quietly becoming facts.

## Debugging a Real Login Failure (`3c8d4e7`)

A longer play session exposed a failure across several layers. The agent
ended up with the wrong version of the `Dummy` character, overwrote the
saved player state, and left too little visible information in the TUI to
diagnose the sequence without opening the separate log viewer.

The resulting fix treated connection and authentication as separate
states:

- `mud_status` now distinguishes a closed connection, an open socket, and
  a fully logged-in session.
- `mud_connect` retries authentication on an existing but unauthenticated
  socket instead of claiming the agent is already connected.
- The login parser detects CircleMUD's "Did I get that right?" prompt,
  declines the new-character path, and raises a clear error when the
  requested player does not already exist.
- The TUI now shows bounded plan, reasoning, tool-call, and tool-result
  events in the conversation pane, making the agent's live behavior
  inspectable without flooding the display.

This was a useful systems lesson: a healthy TCP socket does not mean the
application session is healthy. Modeling those states separately made the
recovery path explicit and prevented the agent from continuing against a
half-completed login flow.

## Keeping Secrets Out of Session Logs (`3c8d4e7`)

The same debugging pass found a more serious issue: tool results are
written to JSONL, so a command that reads `.env` or prints environment
variables can persist credentials or private endpoints in a file intended
for sharing and review.

The fix uses two layers:

1. The file-system tool refuses direct reads of `.env` files.
2. The logger recursively redacts API keys, secrets, tokens, passwords,
   hosts, URLs, URIs, endpoints, and DSNs before an event reaches disk or
   a live subscriber.

The first layer prevents the obvious path; the second protects against
values returned by other tools, such as a shell command. Existing affected
logs still required manual cleanup, but future events are sanitized at the
shared logging boundary.

## Why This Stayed Outside the Strict-Port Lineage

The step-12 plan's `Outcome` section closes with "all of
`week1_baseline/ruby/00`–`12` now has a corresponding, independently
verified `week1_baseline/python/` counterpart" — that claim is about the
*port*, and it stays true at `692f80a`, the commit where step 12 landed
with nothing else layered on yet. Everything in this file is additive
exploration on top of that finished baseline, not a revision of it.
