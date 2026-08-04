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
  OpenRouter-catalog model slug without backend-side pre-registration. Ollama
  model names are also no longer statically allowlisted: the server determines
  whether an explicitly selected tag exists.
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
| `--list-ollama-models` | off | Query the configured Ollama host, print installed tags and advertised capabilities, then exit. The private host is not printed. |
| `--all-ollama-tools` | off | Add every unique installed completion model advertising Ollama's `tools` capability. Tags sharing a digest are deduplicated. |
| `--all-ollama` | off | Add every unique installed completion model, including models without tool support that are expected to fail this harness. |
| `--include-ollama-aliases` | off | Keep multiple tags that point at the same Ollama digest. |
| `--probe-ollama-tools` | off | Before MUD trials, require selected Ollama models to emit a tool call and then complete after receiving its result. Failed models are reported and skipped. |
| `--ollama-probe-only` | off | Run probes for the selected Ollama targets and exit without connecting to the MUD. Returns nonzero if any selected Ollama model fails. |
| `--ollama-probe-timeout SECONDS` | `120` | Per-request timeout for the probe's two model requests. Loading a cold large model can dominate this time. |
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

## Ollama model discovery

The eval runner resolves the server through `OLLAMA_HOST` from the existing
process or repository `.boukensha/.env`, then `ollama.host` in
`.boukensha/settings.yaml`, then Ollama's localhost default. No private server
name is embedded in the runner, printed in its catalog, or written into eval
results.

List the catalog without loading a model or running the MUD:

```bash
python3 evals/run_bakery.py --list-ollama-models
```

Run one strict trial against every unique tag whose `/api/show` response
advertises both `completion` and `tools`:

```bash
python3 evals/run_bakery.py \
  --all-ollama-tools \
  --repetitions 1 \
  --reprompts 0
```

Capability metadata is only a compatibility hint. A model can advertise
`tools` yet emit malformed arguments, ignore the result, repeatedly call the
same tool, or be too specialized/small to solve the task. Add the two-request
probe to screen those failures before paying for full trials:

```bash
python3 evals/run_bakery.py \
  --all-ollama-tools \
  --probe-ollama-tools \
  --repetitions 1 \
  --reprompts 0
```

The probe deliberately uses Boukensha's Ollama message format and
`think: false`. First the model must call `boukensha_probe` with an exact
argument. The original instruction also tells it what to do after the result.
The result is then returned directly using Ollama's `tool_name` tool-result
shape, with no extra user reminder, and the model must produce a normal final
completion without calling the tool again. Outcomes such as `no_tool_call`,
`bad_arguments`, `tool_loop`, and
`no_final_completion` separate basic model/harness compatibility failures from
later MUD reasoning failures.

Probe one model without starting a gameplay trial:

```bash
python3 evals/run_bakery.py \
  --model ollama:gemma4:latest \
  --ollama-probe-only
```

Discovery deduplicates aliases by digest, preventing a versioned tag and its
`latest` alias from silently running the same weights twice. Pass
`--include-ollama-aliases` when alias behavior itself is what you want to test.

### Gemma caveat

"Gemma supports tools" is not one model-wide fact. Check the exact tag. In the
catalog inspected on 2026-08-04, the installed Gemma 2 tags advertised
`completion` but not `tools`, while the Gemma 4 tags advertised both. Gemma 4
can therefore enter the tool probe; Gemma 2 is excluded by
`--all-ollama-tools`.

Even for Gemma 4, emitting the first tool call does not prove that the full
agent loop works. The observed "stuck on tool calls" behavior could occur after
the result is returned, or later on Boukensha's larger and less precise MUD
schemas. The two-request probe isolates the first case. If Gemma 4 passes the
probe but loops in a MUD trial, inspect the transcript for repeated calls,
invalid optional arguments, or failure to interpret the game result. That
points away from basic Ollama serialization and toward schema, prompt, or model
behavior. The explicit required/optional schema cleanup in
`docs/plans/16_state_aware_execution.md` remains relevant because the current
adapters still mark every declared property required.

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

Open <http://localhost:4567> — the nav bar at the top switches between
every view below; nothing needs a restart after a new batch, every page
re-reads the results files on load.

### Sessions — Transcript / Story / Movement

`/sessions/:id` is the raw per-trial view (also what an eval run's
**transcript**/**story** links open, since `evals/boukensha_agent.py`'s
driver writes trials through the same `Logger` as interactive play — see
[`session.rb`](../week1_baseline/ruby/log_viz/lib/log_viz/session.rb)).
Three tabs, toggled at the top of the page:

- **Transcript** — the flat, chronological event log: every prompt, tool
  call/result, reasoning block, and turn boundary, as it happened.
- **Story** — the same events regrouped into one narrative "beat" per turn
  (what the agent was asked, what it thought/did, how it landed), with
  reasoning and tool mechanics folded behind `<details>` toggles.
- **Movement** — for any trial that actually played the MUD: a
  reconstruction of the room-by-room path, parsed straight out of the
  transcript's own `move`/`look` results (no separate logging needed). A
  static map of every room the trial visited (node size/color = time
  spent there, path drawn over it) plus an interactive play/scrub/speed
  replay with a live "which room, how long, how many blocked moves"
  readout. A trial that never connected, or whose harness doesn't log a
  per-step transcript (see the OpenCode caveat below), shows an empty
  state here rather than a blank chart.

### Evals — `/evals`

The scenario/mode/model dashboard. Each scenario/model/mode combination
gets its own summary row (success rate, average iterations used, average
reprompts used) plus a scatter chart (iterations used vs. duration,
colored pass/fail — hover a point for batch/rep detail) and a run-by-run
table linking each row to that run's **transcript**/**story**/**movement**
views. `/evals/legacy` holds the same layout for runs scored before
`mud_connected`/`content_matched` existed (see `EvalRun#legacy_scoring?`)
— kept separate rather than folded in, since those runs passed under a
looser rule and would otherwise quietly inflate a model's apparent rate.

Each trial also runs inside its own `eval.trial` OTel span (parenting the
same `agent.turn`/`agent.iteration`/`llm.request` spans interactive play
already emits — see `docs/plans/15_otel_tracing.md`), tagged under the
`boukensha-agent-eval` service so it doesn't mix into interactive play's
traces. `boukensha_agent.py` points every trial at the collector
(`http://localhost:4318` by default — override with `OTEL_EXPORTER_OTLP_ENDPOINT`
before running a batch) and records the resulting `trace_id` back into
`results.jsonl`, so a run row in the dashboard gets a **trace** link
straight to Jaeger alongside **transcript**/**story**/**movement**. None of
this requires the observability stack to be running — a trial that can't
reach the collector just doesn't get a `trace_id` (checked automatically:
`span.get_span_context().is_valid` is false with no real provider
configured), and everything else about the trial is unaffected.

### Scoreboard — `/scoreboard`

The coarsest "which model is actually winning" view: every scenario and
mode summed together into one pass/fail count per model, ranked by win
rate (ties broken by whoever has more total runs — more data behind the
same rate is worth ranking above it). Not a replacement for `/evals`'s
scenario-by-scenario breakdown, just the leaderboard version of the same
numbers. `/scoreboard/legacy` mirrors the `/evals/legacy` split.

### Movement — `/movement`, `/movement/replay`, `/movement/world`, `/movement/grid`

Everything under the **Movement** nav tab rolls the per-session Movement
tab above up across runs, so you can compare *how* models played, not
just whether they passed:

- **`/movement`** — the aggregate landing page: bar charts of average
  blocked moves (wandering) and average distinct rooms explored per
  model, a summary table, and a trend-over-time line chart (same metric,
  per model, across eval batches) with links to filter by scenario/mode.
- **`/movement/replay?scenario=...&mode=...`** — each model's most recent
  run for one scenario/mode, replayed together on **one shared map**.
  Room positions are resolved against CircleMUD's real room graph
  ([`WorldMap`](../week1_baseline/ruby/log_viz/lib/log_viz/world_map.rb),
  exported once from the `.wld` world files by
  [`export_room_graph.py`](../week0_explore/circlemud-world-parser/export_room_graph.py)
  into a static JSON asset — no Python needed at request time), so a room
  means the same physical place for every model instead of each session
  inventing its own layout. Plays back as a live, decaying group "heat
  trail" — rooms glow by how many models are currently or recently in
  them — rather than individual markers, plus a per-model room/dwell
  readout table.
- **`/movement/world`** — every scenario, mode, and model's movement at
  once, combined into a single cumulative traffic heatmap on the same
  shared map. No playback (runs span days, so there's no one shared clock
  worth scrubbing) — toggle between total dwell time and visit count as
  the metric, and a table of the busiest rooms below the map.
- **`/movement/grid?scenario=...&mode=...`** — small multiples: each
  model's most recent run drawn on its *own* layout (like the
  per-session Movement tab, not the shared world map), side by side in a
  grid, all advancing together on one shared step control. Steps are
  room-arrival counts rather than wall-clock time or a fixed command
  budget, since this harness doesn't cap trials at a fixed number of
  actions the way some other agent harnesses do.

Two caveats worth knowing before reading too much into any of these:

- **OpenCode/OpenRouter runs have no Movement data.** `run_bakery_opencode.py`
  (see above) doesn't currently log a per-step transcript, only aggregate
  counts — every Movement view says so explicitly rather than rendering a
  misleading all-zero bar for a harness that was never instrumented for
  this.
- **Room-name resolution isn't 100%.** `WorldMap#resolve_trace` matches a
  session's room *names* (there's no vnum in the transcript) against the
  real world graph, disambiguating reused names (e.g. multiple "Main
  Street" segments across zones) by checking adjacency to an
  already-resolved neighbor. A very short trial with only ambiguous room
  names, or a name that simply doesn't exist in the mapped `.wld` files,
  can't be placed — it's skipped rather than guessed at, and
  `/movement/world`'s page shows the actual resolved/total ratio rather
  than hiding the gap.

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
