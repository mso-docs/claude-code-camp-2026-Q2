# Week 2 · OpenTelemetry Tracing & Error Logs

**Lives in:** `week0_explore/infrastructure/` (the observability stack),
`week1_baseline/python/12_context/boukensha/` (the instrumentation), and
`week1_baseline/ruby/log_viz/` (the Story view prototype) — not
`week2_capable/`, since this instruments/extends existing baseline pieces
rather than adding a new capability.
**Builds on:** the existing `docker-compose.yml` (CircleMUD service), the
Python `12_context` agent (`Agent`, `Client`, `Registry.dispatch`), and the
Ruby `log_viz` session dashboard (`Session`, its Sinatra `App`, and the
transcript template).
**Status:** Built, smoke-tested, and confirmed working end-to-end: traces
visible in both Jaeger and Grafana Tempo, and a Story view alternative to
`log_viz`'s transcript running side by side with it against real session
data.
**Prompted by:** a lesson exercise in two parts — (1) stand up an OTel
stack, run the agent against it, and judge whether Jaeger or Grafana Tempo
communicates the agent's decision-making better than the existing
chronological session-log transcript; (2) independently of tracing,
prototype an alternative "Story view" session UI and compare it against
that same transcript.

## Goal

Give the Boukensha agent optional distributed tracing — one span per turn,
per agent-loop iteration, per tool call, and per LLM API request — exported
to a local OTel collector that fans out to both Jaeger and Grafana Tempo, so
the two trace UIs can be compared side by side against the transcript view
`log_viz` already provides.

This is explicitly a diagnostics/comparison add-on, not a replacement for
the transcript-based session log — `.boukensha/sessions/*.jsonl` and
`log_viz` are unchanged.

## Design — observability stack

New `week0_explore/infrastructure/observability/` config directory, plus
four new services in the existing `docker-compose.yml` (optional — the
`circlemud` service is unaffected and still runs standalone):

- **`otel-collector`** (`otel/opentelemetry-collector-contrib`) — receives
  OTLP (gRPC `4317`, HTTP `4318`) from the agent and fans it out to both
  backends below via its own `otlp/jaeger` and `otlp/tempo` exporters
  ([otel-collector-config.yaml](../../week0_explore/infrastructure/observability/otel-collector-config.yaml)).
  These are the ports the agent's `OTEL_EXPORTER_OTLP_ENDPOINT` should
  point at.
- **`jaeger`** (`jaegertracing/all-in-one`) — `COLLECTOR_OTLP_ENABLED=true`
  so it accepts OTLP directly from the collector; UI on `16686`.
- **`tempo`** (`grafana/tempo`) — local-disk block storage, OTLP receiver
  on its own internal `4317`; query API on `3200`
  ([tempo.yaml](../../week0_explore/infrastructure/observability/tempo.yaml)).
- **`grafana`** — Tempo pre-provisioned as a datasource via
  [grafana-datasources.yaml](../../week0_explore/infrastructure/observability/grafana-datasources.yaml)
  (anonymous admin access enabled so no login step is needed for this
  local/throwaway stack); UI on `3000`.

## Design — instrumentation

New `boukensha/tracing.py`: a single module-level `tracer` obtained via
`trace.get_tracer("boukensha")` at import time, and a `configure()` function
called once from both `run()` and `repl()` (`boukensha/__init__.py`).
`configure()` is a no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set — when
unset, every `tracer.start_as_current_span(...)` call elsewhere in the
codebase returns the OTel API's own no-op span, so the instrumentation is
always safe to leave in place, collector running or not, key point being
nobody has to remember to strip tracing code out for a normal run.

Spans, nested to mirror the shape of one turn:

- **`agent.turn`** (`agent.py:Agent.run`) — one per REPL round-trip, parent
  of everything below. Wraps the whole iteration loop.
- **`agent.iteration`** (`agent.py:Agent.run`) — one per loop iteration,
  `iteration` number as an attribute.
- **`tool.<name>`** (`agent.py:Agent._handle_tool_calls`) — one per tool
  call, named after the tool so Jaeger/Tempo's own span-name grouping does
  useful work for free. `Registry.dispatch`'s exceptions are caught here
  (a bad tool call shouldn't kill the turn), so the span's error status has
  to be set explicitly — `span.record_exception` / `span.set_status` inside
  the `except` — since nothing propagates out of the `with` block for
  `start_as_current_span`'s own default exception handling to catch.
- **`llm.request`** (`client.py:Client.call`) — one per `Client.call`
  invocation, wrapping the whole retry loop (so retries show up as one span
  with an `llm.attempts` count, not one span per HTTP attempt). Exceptions
  here (`ApiError`, after retries are exhausted) *do* propagate out of the
  `with` block, so this one relies on `start_as_current_span`'s default
  exception recording rather than doing it by hand.

`opentelemetry-api`, `opentelemetry-sdk`, and
`opentelemetry-exporter-otlp-proto-http` were added to
[pyproject.toml](../../week1_baseline/python/12_context/pyproject.toml).

## Design — Story view prototype (`log_viz`)

Independent of tracing: an alternative session view added alongside
`log_viz`'s existing transcript, so the two can be compared side by side
on the same real session data, per the lesson's second half.

- **[`Session#beats`](../../week1_baseline/ruby/log_viz/lib/log_viz/session.rb)**
  — new method, regrouping the same flat, chronological `entries` list the
  transcript already renders into one `Beat` struct per turn: the user's
  ask, every reasoning/plan entry as `thinking`, every tool call, the
  turn's actual narrated reply (`final_text` — skipping tool-use
  placeholder text, same rule `Session#final_response` already used for
  the session-wide case), and the `turn_end` entry if the turn finished.
  No new parsing — same `entries` the transcript uses, just regrouped.
- **New route** `GET /sessions/:id/story`
  ([app.rb](../../week1_baseline/ruby/log_viz/lib/log_viz/app.rb)) renders
  [views/story.erb](../../week1_baseline/ruby/log_viz/views/story.erb).
  The existing `/sessions/:id` transcript route is unchanged.
- **Shared header, differing body** — the session stats header (banner,
  token/cost stat strip, cost breakdown, sparkline) was factored out of
  `session.erb` into
  [`views/_header.erb`](../../week1_baseline/ruby/log_viz/views/_header.erb)
  so both views render identical metadata and differ only in how the
  turn-by-turn content itself is shown — otherwise the comparison would be
  confounded by unrelated layout differences. A small view-toggle link
  (`Transcript` / `Story view`) sits under the header on both pages.
- **What's actually different in the Story view**: reasoning/plan entries
  collapse behind a `<details>&#129504; N thoughts` toggle instead of
  always-visible blocks, each tool call collapses behind its own
  `<details>&#9881; tool_name(...)` toggle instead of an always-expanded
  block, and the turn's narrated reply is surfaced as a single prominent
  "outcome" block. The goal being tested: does hiding the mechanical
  detail by default make the narrative easier to follow, or does it just
  hide detail that mattered.

## Verification plan

- ~~Schema/compose validity~~ — done: all four new/changed YAML files
  (`docker-compose.yml` and the three new `observability/*.yaml` configs)
  parse cleanly (`python3 -c 'import yaml; yaml.safe_load(...)'` — docker
  itself isn't available in the dev sandbox this was built in, so
  `docker compose config` couldn't be run as a second check).
- ~~Span shape~~ — done, via an in-memory-exporter smoke test (no collector
  or network needed): a fake `Client`/`Registry` drives `Agent.run()`
  through two iterations, one tool call that succeeds and one that raises —
  confirmed `agent.turn` parents exactly two `agent.iteration` spans, each
  tool call produces its own `tool.<name>` child span, the raising tool's
  span has `status=ERROR` with a recorded exception while the successful
  tool's span doesn't, and a separately mocked `Client.call()` produces one
  `llm.request` span with the expected `llm.attempts`/`llm.url` attributes.
- ~~No-op safety~~ — done: with `OTEL_EXPORTER_OTLP_ENDPOINT` unset,
  `configure()` returns without registering a provider and
  `tracer.start_as_current_span(...)` still starts/stops cleanly (no-op
  span), confirming a normal run with no collector present is unaffected.
- ~~Live end-to-end run~~ — done: stack brought up via `docker compose up
  -d` from `week0_explore/infrastructure/` (Grafana moved to host port
  `3001` — `3000` was already in use locally), agent run against it with
  `OTEL_EXPORTER_OTLP_ENDPOINT` pointed at the collector, trace confirmed
  visible in both Jaeger (`:16686`) and Grafana Tempo (`:3001` → Explore →
  Tempo datasource).
- ~~Story view renders correctly~~ — done: ran `log_viz` locally against a
  real session log (`.boukensha/sessions/20260731T022332Z-e4079acc.jsonl`,
  a multi-turn MUD session with 20+ reasoning entries and dozens of tool
  calls) and hit both `/sessions/:id` and `/sessions/:id/story` directly —
  both return 200. Confirmed beats group correctly by turn (thinking
  toggle count matches actual reasoning-entry count, tool-call toggles
  render ANSI-colored results identically to the transcript's own
  rendering, a turn still in progress when the log ends correctly omits
  its outcome/turn-end footer rather than erroring on missing data), and
  confirmed the transcript route still renders unchanged after factoring
  the shared header into `_header.erb` (same message/tool-block count as
  before the refactor).
- **Still open:** the lesson's own qualitative calls — whether either
  trace view (Jaeger/Tempo) beats the transcript for understanding *why*
  the agent did something rather than *how long* it took, and separately
  whether the Story view's collapsed-by-default reasoning/tool-call
  presentation actually reads better than the transcript's flat,
  always-expanded one or just hides detail that mattered. Both
  deliberately left as judgment calls for whoever runs the comparison
  rather than asserted here.

## Usage

See the new "OpenTelemetry tracing (optional)" section in
[QUICKSTART.md](../../QUICKSTART.md) for the tracing stack.

For the Story view: run `log_viz` as usual (see
[QUICKSTART.md](../../QUICKSTART.md)'s Log Viewer command), open a
session's transcript, and click **Story view** in the toggle under the
header — or go straight to `/sessions/:id/story`. The session index page
also links directly to `story` next to each session ID.

## Outcome

Stack and instrumentation are built, wired, and confirmed working
end-to-end: the observability stack came up cleanly (after clearing an
unrelated home-network MTU/routing problem that was breaking large Docker
Hub pulls — not a stack or instrumentation issue), the agent ran against
it with tracing enabled, and the resulting trace showed up correctly in
both Jaeger and Grafana Tempo.

The Story view prototype is also built and confirmed rendering correctly
against real session data, running side by side with the existing
transcript in the same `log_viz` app. Judging Jaeger vs. Tempo vs.
transcript, and separately Story view vs. transcript, is left to whoever
runs the comparison to observe firsthand — that comparison is the actual
point of the lesson, not something to pre-decide here.
