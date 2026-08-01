# Evals — running the boukensha agent through repeatable, scored tasks

This directory runs the `week1_baseline/python/12_context` boukensha agent
through fixed "scenarios" (a task, a turn budget, and a way to check success
from game state — no LLM judge) across models and repetitions, and records
the results for comparison. [`bakery.py`](bakery.py) is the primary scored
scenario; [`return_to_midgaard.py`](return_to_midgaard.py) is a separately
logged recovery scenario used to restore its expected starting room.

Everything below assumes your shell is in the repository root.

## Prerequisites

- CircleMUD running on `localhost:4000` (`docker compose up` from
  `week0_explore/infrastructure`, or check `docker ps` — see the main
  [QUICKSTART.md](../QUICKSTART.md)).
- Whatever backend you're testing against is reachable — a local/remote
  Ollama server, or the right `..._API_KEY` (`ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_API_KEY`, `OPENROUTER_API_KEY`)
  set in `.boukensha/.env` at the repo root (the eval runner reads that file
  automatically; see [`boukensha_agent.py`](boukensha_agent.py)'s
  `_load_env_vars`). `--model openrouter:<vendor>/<model>` accepts any
  OpenRouter-catalog model slug without backend-side pre-registration.
  Unknown model IDs still use `boukensha/models.py`'s 32,000-token context
  fallback for agent compaction; add a verified entry there when the real
  context window is known.
- **The MUD character's position isn't automatically reset between trials.** CircleMUD resumes a
  character exactly where it was on both a clean `quit` and a raw
  disconnect (checked directly), independent of whether `save_character`
  was ever called — so every trial's ending room is the next trial's
  starting room, full stop. There is no `recall`/teleport command on this
  server either (checked directly — bare `recall` returns `Huh!?!`), so
  there is no instant command that moves the character back to a known room.
  Four safeguards deal with this, but only the recovery task changes
  position, and it does so through ordinary gameplay rather than a true
  fixture reset:
  1. `save_character` is removed from the tool registry entirely for every
     eval trial ([`_disable_save`](_driver.py) — not shadowed with a
     "disabled" message, genuinely gone; a model calling it anyway gets a
     framework `UnknownToolError`, indistinguishable from an unrecognized
     command). This only matters for surviving an actual CircleMUD server
     restart — it does **not** stop position drift between trials, since
     drift happens on reconnect regardless of any save.
  2. Every scenario that defines `EXPECTED_START_ROOM` (see `bakery.py`)
     gets a quick connect-look-disconnect check before each trial. If the
     character isn't there, `boukensha_agent.py` doesn't just fail the
     trial — it runs [`return_to_midgaard.py`](return_to_midgaard.py) as a
     recovery attempt first: the agent gets its own budget to navigate
     back to The Temple Of Midgaard using the same look/move tools any scenario
     uses, logged as its own `return_to_midgaard` row in the results
     (separate from whatever scenario was actually requested, so it never
     pollutes that scenario's own stats). If recovery succeeds, the real
     scenario then runs normally, immediately after, in the same batch.
  3. `return_to_midgaard.py` gets up to `RECOVERY_ATTEMPTS` (2) tries, each a
     brand-new subprocess/connection — a single failure is often just a
     transient MUD hiccup, not a genuinely stuck character, so retrying once
     before giving up avoids losing an unattended batch to one bad
     connection.
  4. If every recovery attempt fails, `run_once()` raises
     `RecoveryFailedError`. `run_bakery.py` does **not** stop the batch on
     the first one of these — it logs the failed recovery attempt and moves
     on to the next repetition, which gets its own fresh preflight check and
     recovery attempt. Only `CONSECUTIVE_STALL_LIMIT` (3) stalled
     repetitions *in a row* — no successful trial in between — stops the
     batch outright. That pattern means something structural is wrong (MUD
     container down, network dead), not one-off bad luck, and no amount of
     per-trial retrying fixes it. At that point a human has to check on it
     (and likely walk the character back by hand) — there's no fifth layer.
     `PreflightConnectionError` (couldn't even confirm the starting room) is
     handled the same way, sharing the same stall counter.
- Only run one eval trial at a time. CircleMUD allows exactly one live
  session per character, and every trial logs in as the same shared
  account (`dummy`, from `.boukensha/settings.yaml`) — the runner already
  runs trials sequentially for this reason, don't parallelize it.

## Running a trial batch

```bash
python3 evals/run_bakery.py
```

That's the full default: 5 repetitions, against `ollama:qwen3.6:35b-a3b`,
in **both** budget modes (see below). Progress prints to stderr per trial,
one JSON line per trial gets appended to `evals/results/bakery.jsonl`.

Flags:

| Flag | Default | What it does |
|---|---|---|
| `--repetitions N` | `5` | Trials per (model, mode) combination. LLM output is stochastic — a single run's pass/fail is close to meaningless; run enough reps to see a *rate*. |
| `--model backend:model` | `ollama:qwen3.6:35b-a3b` | Repeatable — pass it more than once to test several models in one batch, e.g. `--model ollama:qwen3.6:35b-a3b --model anthropic:claude-haiku-4-5`. |
| `--reprompts N` | `0` and `2` (both) | Repeatable — see "Strict vs. reprompt" below. Passing this at all replaces the default entirely, so `--reprompts 0` alone runs strict-only. |
| `--timeout SECONDS` | auto-scaled | Per-trial kill switch. Default scales off `--reprompts` and the scenario's `MAX_TURNS` (`run_bakery.default_timeout()`) — `(max_reprompts + 1) * MAX_TURNS * 15s + 60s`, e.g. ~7 min for strict, ~20 min for `reprompt2`. A flat 300s default silently killed 28% of bakery trials in the 2026-08-01 overnight batches, well before the agent's own iteration/reprompt budget was used up — see `docs/journal/2.5_evals.md`. Pass `--timeout` explicitly to override the auto-scaled value for every mode in the batch. |

Examples:

```bash
# strict only (hard 25-action budget, no reprompt)
python3 evals/run_bakery.py --reprompts 0

# reprompt only, up to 2 extra fresh budgets
python3 evals/run_bakery.py --reprompts 2

# quick smoke test: both modes, 1 rep each
python3 evals/run_bakery.py --reprompts 0 --reprompts 2 --repetitions 1

# compare two models, 3 reps each, strict only
python3 evals/run_bakery.py --model ollama:qwen3.6:35b-a3b --model ollama:qwen3.6:27b --reprompts 0 --repetitions 3
```

## OpenCode comparison runner

`run_bakery_opencode.py` runs the same bakery task through the separate
OpenCode agent in `.opencode/agents/bakery-evaluator.md`:

```bash
python3 evals/run_bakery_opencode.py
python3 evals/run_bakery_opencode.py --repetitions 3 --model ollama/qwen3.6:35b-a3b
```

It requires the `opencode` CLI plus `MUD_USERNAME` and `MUD_PASSWORD` in the
repository-root `.env`. It drives the older `tmux`/telnet bridge rather than
Boukensha's Python connector, writes `evals/results/bakery_opencode.jsonl`,
and always attempts to stop its `opencode-mud` tmux session after a trial.

Do not run it concurrently with a Boukensha batch when both are configured
for the same character; CircleMUD allows only one live connection per
character. Unlike `run_bakery.py`, the OpenCode runner currently has no
starting-room preflight, return-to-Midgaard recovery, reprompt mode, or
consecutive-stall circuit breaker. It is intended for occasional comparison
runs, not unattended overnight batches.

## Strict vs. reprompt modes

Every scenario has a fixed turn budget (`MAX_TURNS` in the scenario file —
25 for `bakery`). Two ways to run against that budget:

- **Strict** (`--reprompts 0`) — one attempt, hard budget, no follow-up. If
  the agent runs out of actions, that trial is scored as-is. This is the
  cleaner mode for comparing models against each other: every trial costs
  the same fixed amount of budget, so differences in outcome are
  attributable to the model, not to how many extra chances it got.
- **Reprompt** (`--reprompts N`, `N>0`) — if the agent exhausts its budget
  *without voluntarily ending its turn* (i.e. it was still actively working
  when the ceiling hit, not giving up or claiming to be done), it's sent a
  nudge ("you haven't finished, continue") and given a **fresh** budget —
  same conversation history and live MUD session, new action count — up to
  `N` additional times. This mirrors how the interactive REPL already
  behaves when you type a follow-up message
  (`boukensha.run_reprompted()` in
  [`boukensha/__init__.py`](../week1_baseline/python/12_context/boukensha/__init__.py),
  same "fresh Agent per turn" mechanism as `repl.run_turn()`). Useful for
  seeing whether a model that fails under a strict budget can actually
  finish given more runway, versus one that's genuinely stuck regardless of
  budget.

Run both (the default) to see whether reprompting meaningfully changes the
outcome for a given scenario/model, or just spends more wall-clock time
reaching the same result — that comparison is exactly what the two mode
rows in the dashboard (below) are for.

## Viewing results

Results accumulate in `evals/results/*.jsonl` (for example `bakery.jsonl`
and `bakery_opencode.jsonl`) —
gitignored except for the `.jsonl` files themselves, since the per-run
working directories and throwaway configs under `evals/results/<batch>/`
are regenerable. View them in `log_viz`:

```bash
cd week1_baseline/ruby/log_viz
LOG_VIZ_SESSIONS_DIR="$(pwd)/../../../.boukensha/sessions" \
LOG_VIZ_EVAL_RESULTS_DIR="$(pwd)/../../../evals/results" \
bundle exec ruby bin/log_viz
```

Then open <http://localhost:4567/evals> (nav bar at the top switches
between the session transcript viewer and this eval dashboard — no
restart needed after a new batch, it re-reads the results files on every
page load). Each scenario/model/mode combination gets its own summary row
(success rate, average iterations used, average reprompts used) plus a
scatter chart (iterations used vs. duration, colored pass/fail — hover a
point for batch/rep detail) and a run-by-run table with a link to that
run's raw session log.

Each trial also runs inside its own `eval.trial` OTel span (parenting the
same `agent.turn`/`agent.iteration`/`llm.request` spans interactive play
already emits — see `docs/plans/15_otel_tracing.md`), tagged under the
`boukensha-agent-eval` service so it doesn't mix into interactive play's
traces. `boukensha_agent.py` points every trial at the collector
(`http://localhost:4318` by default — override with `OTEL_EXPORTER_OTLP_ENDPOINT`
before running a batch) and records the resulting `trace_id` back into
`results.jsonl`, so a run row in the dashboard gets a **trace** link
straight to Jaeger alongside **transcript**/**story**. None of this
requires the observability stack to be running — a trial that can't reach
the collector just doesn't get a `trace_id` (checked automatically:
`span.get_span_context().is_valid` is false with no real provider
configured), and everything else about the trial is unaffected.

## Adding a new scenario

Following `bakery.py`'s shape:

```python
TASK = "..."            # the exact prompt handed to the agent
MAX_TURNS = 25           # per-attempt action budget
OUTPUT_FILE = "data/..."  # relative to the run's working_dir — how score.py checks success
```

Success is checked deterministically from game state (a file the agent was
told to write, in this case) — not by asking another model to judge the
transcript. Keep new scenarios checkable the same way if at all possible;
see [`score.py`](score.py) for how the check plugs in. You'd also want a
new `run_<scenario>.py` mirroring `run_bakery.py` (swap the `import
bakery` for your new module and the `"scenario"` tag in the results dict).

## How it fits together

```
run_bakery.py             — CLI: loops (model × mode × repetition), writes results.jsonl
  → boukensha_agent.py     — adapter: one subprocess per trial (isolates config/model per run)
      → _driver.py          — subprocess entry point: calls boukensha.run_reprompted()
      → check_starting_room — preflight; on mismatch, runs return_to_midgaard.py as recovery first
  → score.py               — reads the trial's working_dir/final_room + session log, computes pass/fail and stats
bakery.py                  — a scenario: task text, turn budget, success-file path, EXPECTED_START_ROOM
return_to_midgaard.py      — the recovery scenario: task text, turn budget, SUCCESS_ROOM (no output file)
```

Each trial is a fresh subprocess against a throwaway `.boukensha/` config
dir (model/backend/turn budget baked into a generated `settings.yaml`) —
`boukensha.state.config()` is a process-wide singleton, so this is the only
way to vary those settings between trials in one batch. See
[`boukensha_agent.py`](boukensha_agent.py)'s module docstring for the full
reasoning.
