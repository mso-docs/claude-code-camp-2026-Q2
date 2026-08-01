# Week 2 OpenTelemetry Journal

The lesson behind this one had two independent halves: stand up a real
OpenTelemetry stack, run the agent against it, and judge honestly whether
Jaeger or Grafana Tempo communicates the agent's decision-making better
than the plain chronological session transcript `log_viz` already had —
and, separately, prototype an alternative "Story view" for that same
transcript and compare it against the original. Both halves ended in a
considered "no," and that's the actual point of this entry: a negative
result, checked carefully, is still a result.

Full design is in `docs/plans/15_otel_tracing.md`; this is the narrative
version.

## What got built

- A new `week0_explore/infrastructure/observability/` stack — an
  `otel-collector` fanning OTLP out to both `jaeger` and `tempo`, with
  `grafana` pre-provisioned to query Tempo — added as optional services
  alongside the existing `circlemud` container, so a normal run is
  unaffected if you don't bring them up.
- `boukensha/tracing.py`: one span per turn (`agent.turn`), per agent-loop
  iteration (`agent.iteration`), per tool call (`tool.<name>`), and per LLM
  request (`llm.request`, wrapping the whole retry loop as one span rather
  than one span per HTTP attempt). Configuration is a no-op unless
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so the instrumentation stays in the
  code permanently instead of being something to remember to strip out.
- A completely separate experiment in the same session: `log_viz` got a
  second way to view a transcript. `Session#beats` regroups the same flat,
  chronological event log into one narrative "beat" per turn — reasoning
  and tool calls collapsed behind `<details>` toggles, the turn's actual
  reply surfaced as a single prominent block — served at
  `/sessions/:id/story` alongside the original `/sessions/:id`. The shared
  header (banner, token/cost strip, sparkline) was factored out into
  `_header.erb` so the two views differed only in how turn content itself
  was presented, not in surrounding layout — otherwise the comparison
  would've been confounded by unrelated presentation differences.

## The verdict, from actually running the comparison

Both experiments were judged against the same real thing: a multi-turn MUD
session with 20+ reasoning entries and dozens of tool calls, viewed in
Jaeger, in Grafana Tempo, and as both `log_viz` views side by side.

- **Jaeger and Tempo**: genuinely useful for what they're for — call
  timing, retries, error status are all there and correct. Neither UI
  clearly communicated the agent's *overall* decision-making, though. Both
  read as dense and hard to follow, with no color-coding or other visual
  aids keeping different calls visually distinct from each other at a
  glance.
- **Story view vs. transcript**: despite presenting the same information
  differently — collapsed detail by default, one beat per turn instead of
  a flat event stream — it still didn't tell the agent's story as clearly
  as the plain chronological transcript did. Hiding detail by default
  turned out to hide detail that mattered, more often than it clarified
  anything.

## Direction taken as a result

- OpenTelemetry stays wired in and available — it's a real, working
  diagnostics/performance tool, just not the primary way to understand
  what the agent did on a given run.
- The plain transcript remains `log_viz`'s primary view. Story view stays
  live for comparison but gets no further investment.
- No further time went into polishing either trace UI or extending Story
  view. Both were explicitly a learning exercise confirming what doesn't
  work here, not groundwork for a final feature — development moved back
  to gameplay after this, which is what eventually led to the evals work
  (`2.5_evals.md`).

## Main lesson

Instrumentation and visualization are different problems, and "we now have
distributed tracing" doesn't automatically answer "can a human tell what
the agent was thinking." Both experiments in this lesson were built
correctly, verified end-to-end, and then judged on the actual question —
does this help a person understand the run — rather than on whether the
tooling itself worked. It's tempting to treat "the trace shows up in
Jaeger" as success; the more honest bar is whether looking at it beats
just reading the transcript, and here, for both experiments, it didn't.
Shipping the instrumentation anyway (it's real and occasionally useful)
while being honest that it isn't the answer to the original question is
the actual outcome worth recording.
