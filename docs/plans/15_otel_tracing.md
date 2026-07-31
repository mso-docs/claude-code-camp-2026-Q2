# Week 2 · OpenTelemetry Tracing & Error Logs

**Lives in:** `week0_explore/infrastructure/` (the observability stack) and
`week1_baseline/python/12_context/boukensha/` (the instrumentation) — not
`week2_capable/`, since this instruments the existing baseline agent rather
than adding a new capability to it.
**Builds on:** the existing `docker-compose.yml` (CircleMUD service) and the
Python `12_context` agent (`Agent`, `Client`, `Registry.dispatch`).
**Status:** Stack and instrumentation built and smoke-tested; a live
docker + real-session run is still the user's to do (see Outcome).
**Prompted by:** a lesson exercise — stand up an OTel stack, run the agent
against it, look at the resulting trace in both Jaeger and Grafana Tempo,
and judge whether either communicates the agent's decision-making better
than the existing chronological session-log transcript
(`week1_baseline/ruby/log_viz`).

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
- **Not yet done (needs the user's own Docker + credentials):** bring the
  stack up for real (`docker compose up -d` from
  `week0_explore/infrastructure/`), run the actual agent against a live
  session with `OTEL_EXPORTER_OTLP_ENDPOINT` pointed at the collector, and
  open the resulting trace in both Jaeger (`:16686`) and Grafana
  (`:3000` → Tempo). That live comparison — and the lesson's own
  conclusion about whether either trace view beats `log_viz`'s
  chronological transcript for understanding *why* the agent did
  something, versus *how long* it took — is the part this plan
  deliberately leaves to that live run rather than asserting a canned
  answer.

## Usage

See the new "OpenTelemetry tracing (optional)" section in
[QUICKSTART.md](../../QUICKSTART.md).

## Outcome

Stack and instrumentation are built, wired, and unit/smoke-tested without
docker. Bringing the stack up and judging Jaeger vs. Tempo vs. the
transcript view against a real session is left to the user to run and
observe — that comparison is the actual point of the lesson, not something
to pre-decide here.
