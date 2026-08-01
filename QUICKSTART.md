# QUICKSTART — running the Python port (step 12)

Everything below assumes your shell is in the repository root.

If you've already set the below up, you can access the Boukensha agent using the commands below:

Start the Docker container (even if you have Docker Desktop/Engine running):
```bash
cd week0_explore/infrastructure
docker compose up --build
```

Run the Boukensha executable:
```bash
export BOUKENSHA_DIR="$(pwd)/.boukensha"
./week1_baseline/python/bin/12_context           # full textual TUI
# or
./week1_baseline/python/bin/12_context --no-tui  # plain terminal REPL
```

And here is how you open the Log Viewer (use another terminal tab):

```bash
cd week1_baseline/ruby/log_viz
LOG_VIZ_SESSIONS_DIR="$(pwd)/../../../.boukensha/sessions" bundle exec ruby bin/log_viz

```

Each session has two views: the default chronological **transcript**, and
an experimental **Story view** (one narrative beat per turn, with
reasoning/tool details collapsed by default) at `/sessions/:id/story` — or
click "Story view" in the toggle under a session's header. See
[docs/plans/15_otel_tracing.md](docs/plans/15_otel_tracing.md) for what
it's comparing against and why.

## 1. Set your API key

A config directory already exists at `.boukensha/` in the repo root
(that's the designated spot — `Config` looks for `.boukensha/` in the
current working directory before falling back to `$HOME/.boukensha`).

Edit `.boukensha/.env` and add the key required by your selected provider.
For example, Anthropic uses:

```
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

`.env` is gitignored (matches anywhere in the tree), so this is safe to
edit in place.

Supported remote-provider variables are `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_API_KEY` (Ollama Cloud), and
`OPENROUTER_API_KEY`. Local Ollama does not require an API key.

## 2. (Optional) settings.yaml

Only needed if you want to override the defaults
(`claude-haiku-4-5` on `anthropic`, 25 max iterations, 60,000 max turn
tokens). `.boukensha/settings.yaml`:

```yaml
tasks:
  player:
    provider: anthropic       # anthropic, openai, gemini, ollama, ollama_cloud, or openrouter
    model: claude-sonnet-4-6  # swap to "qwen3.6:27b" or "qwen3.6:35b-a3b" (both whitelisted
                               # in boukensha/backends/ollama.py + boukensha/models.py)

agent:
  max_iterations: 25
  max_turn_tokens: 60000

# Only read when provider: ollama above. Uncomment and fill in your server:
# ollama:
#   host: "http://your-dns-name:port"

# Optional — connect to a CircleMUD server and unlock gameplay tools.
# Without this block, MUD tools simply don't register.
# mud:
#   host: localhost
#   port: 4000
#   username: yourcharacter
#   password: yourpassword
```

This file is **not** gitignored — delete it or `git rm` it if you'd
rather stick with defaults and not have it tracked.

### Using your local Ollama server instead of Anthropic

No API key needed — just flip `provider`/`model`/`ollama.host` in
`settings.yaml` as shown above. This required two small additions beyond
the strict Ruby port (documented inline in the code, both untracked by
the step-12 commit):

- `qwen3.6:27b` and `qwen3.6:35b-a3b` added to `Ollama.MODELS`
  (`boukensha/backends/ollama.py`) — models not in this table are
  rejected outright.
- Both also added to `boukensha/models.py`'s `TABLE` (which the Ruby
  reference keeps Anthropic-only) — without this, `Context`'s
  `context_window` would fall back to a 32,000-token default and
  auto-compaction would fire almost immediately against a real
  256k-context local model.
- `Config.ollama_host` (reads `ollama.host` from `settings.yaml`) is new
  too — the Ruby reference has no settings.yaml-driven way to point at a
  non-default Ollama host at all.

If you're running a different local model, add it to both `MODELS`
tables (context window + whatever else you want tracked) the same way.

OpenRouter is the exception to backend model whitelisting: set
`provider: openrouter` and use any `vendor/model` slug. Unknown slugs still fall back
to the 32,000-token entry in `boukensha/models.py` for context compaction,
so add verified model metadata there before relying on automatic compaction
near the model's real limit.

## 3. Run it

`bin/12_context` uses the step-12 Python environment without changing the
directory where you launched it. Launching from the repo root therefore keeps
the agent's file and shell tools rooted at the repo and lets them access the
memory files under `.boukensha/memory/`. Exporting `BOUKENSHA_DIR` explicitly
is still recommended so config resolution remains unambiguous:

```bash
export BOUKENSHA_DIR="$(pwd)/.boukensha"

./week1_baseline/python/bin/12_context           # full textual TUI
./week1_baseline/python/bin/12_context --no-tui  # plain terminal REPL
```

(First run does `uv sync` automatically and creates a `.venv` under
`week1_baseline/python/12_context/`.)

## 4. (Optional) OpenTelemetry tracing

The agent can emit distributed traces — one span per turn, per
agent-loop iteration, per tool call, and per LLM request — to a local
OpenTelemetry Collector that fans out to both Jaeger and Grafana Tempo,
so you can compare the two trace UIs against each other and against the
`log_viz` transcript view. See
[docs/plans/15_otel_tracing.md](docs/plans/15_otel_tracing.md) for the
full design; this is the short version.

Bring the stack up (adds four containers alongside `circlemud`; leave
these services off `docker compose up` entirely if you don't want them
running):

```bash
cd week0_explore/infrastructure
docker compose up -d otel-collector jaeger tempo grafana
```

Point the agent at the collector and run it as usual:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export BOUKENSHA_DIR="$(pwd)/.boukensha"
./week1_baseline/python/bin/12_context --no-tui
```

Have a conversation with the agent (a couple of turns, ideally including
at least one tool call), then inspect the trace:

- **Jaeger UI** — <http://localhost:16686> — select service
  `boukensha-agent`, find the recent trace.
- **Grafana** — <http://localhost:3001> — Tempo is pre-provisioned as a
  datasource; use Explore → Tempo → search by service name.

Unset `OTEL_EXPORTER_OTLP_ENDPOINT` (or just don't set it) to run with
tracing off — the instrumentation is a no-op with no collector configured,
so there's no need to strip anything out for a normal session.

## 5. (Optional) Running evals

Repeatable, scored task runs against the agent (fixed scenario + turn
budget + a deterministic pass/fail check from game state, no LLM judge),
across models and repetitions, viewable as a dashboard in `log_viz`. See
[evals/README.md](evals/README.md) for the full guide; the short version:

```bash
python3 evals/run_bakery.py            # runs the bakery scenario, 5 reps, both budget modes
```

Then view results at `http://localhost:4567/evals` (same `log_viz` server
as above — start it with `LOG_VIZ_EVAL_RESULTS_DIR` set too, see the guide).

## Things worth knowing once you're in

- **Tools**: file-system tools (`pwd`, `read_file`, `write_file`,
  `delete_file`) and a shell (`run_command`) are rooted at whatever
  directory you *launch* the command from — run it from wherever you
  want the agent operating.
- **MUD play**: only active if `mud:` is configured in `settings.yaml`
  (see above).
- **`/compact`**: manually drops old conversation history to free up
  context space. It also compacts automatically once usage crosses 85%
  — watch the color-coded `ctx` indicator in the status bar
  (grey → yellow at 70% → red at 85%, with a `⚠` at 85%+).
- **`/clear`**: wipes conversation history entirely (tools stay
  registered).
- **Keyboard shortcuts (TUI only)**: `Esc` interrupts a running turn,
  `Ctrl-C`/`Ctrl-D` quits, `Ctrl-L` clears history, `PageUp`/`PageDown`
  scroll the conversation.

## Alternative to exporting BOUKENSHA_DIR every time

When you always launch from the repo root, its `.boukensha/` directory is
discovered automatically and the export can be omitted.
