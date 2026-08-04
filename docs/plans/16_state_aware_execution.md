# Final Week · State-Aware Execution & Efficient Memory

**Lives in:** `week2_capable/`, as a successor to
`week1_baseline/python/12_context/` rather than a modification of the frozen
baseline.
**Builds on:** [13 · Structured Knowledge Base](13_knowledge_observability.md),
[14 · Navigator Tool](14_navigator_tool.md), and the deterministic eval harness
in `evals/`.
**Status:** Planned — architecture and staged verification are defined below;
implementation has not started.
**Journal:** [Final Week — Making Boukensha Capable](../journal/3_capable.md).

## Goal

Make Boukensha more capable while reducing the amount of context and the
number of model/tool round trips it needs to finish a stateful task.

The central change is to stop treating memory as a pair of prose documents
that the model must continually read, rewrite, and verify. The harness will
maintain a small working-state projection automatically, store durable
observations in a structured database, and retrieve only the knowledge needed
for the current decision.

This week is successful only if the agent becomes measurably better on the
existing MUD evals. A dashboard or a larger memory store by itself is not a
capability improvement.

## Problem statement

The current durable-memory prompt creates expensive bookkeeping:

1. Read both complete Markdown memory files at session start.
2. Read a memory file before every update.
3. Rewrite the complete document after a state change.
4. Read it back to verify the write.
5. Keep all of those tool calls and results in conversation history.

The prompt also requires a checkpoint after at most four MUD commands and
after almost every meaningful state change. This protected discoveries during
the early experiments, but it makes the agent spend a significant part of its
action and token budget maintaining memory instead of pursuing the objective.
Smaller open models are especially affected because long prompts and large
tool menus make tool selection less reliable.

Context compaction does not currently solve the problem. It drops 40 percent
of messages by count, not by token size or complete interaction boundary. It
does not preserve a semantic state summary, its `target_fraction` argument is
unused, and automatic compaction is checked only once when `Agent.run()`
starts. A long tool loop can therefore grow past the threshold without another
check.

## Design principles

1. **State is maintained by the harness.** The model uses state; it does not
   spend actions copying state between files.
2. **Raw evidence and prompt context are different products.** Full MUD output
   belongs in the session log. The next model request normally needs only a
   concise observation.
3. **Working memory is small and replaceable.** There is one current projection,
   not a growing series of summaries.
4. **Durable memory is structured and evidence-backed.** Beliefs retain their
   provenance, confidence, and freshness.
5. **Retrieval is targeted.** The agent is not given the entire known world on
   every request and should not need a recall call before every action.
6. **Deterministic code handles deterministic work.** Parsing exits, updating a
   counter, finding a shortest path, validating tool arguments, and checking a
   fixed success condition do not require an LLM.
7. **Unexpected state interrupts automation.** Composite actions stop on room
   mismatch, combat, death, disconnection, blocked travel, or other surprising
   output and return control to the model.
8. **Capability is demonstrated by ablation.** Each layer must justify itself
   through pass rate, calls, tokens, latency, or recovery behavior.

## Target architecture

```text
user objective
      │
      ▼
┌──────────────────── Prompt assembly ─────────────────────┐
│ stable system prompt + selected tools                    │
│ current WorkingState (bounded, replaced in place)        │
│ relevant knowledge projection (bounded, cached)          │
│ newest complete interactions (token budget)              │
└──────────────────────────┬───────────────────────────────┘
                           ▼
                         model
                           │ tool call
                           ▼
┌──────────────────── Tool dispatcher ─────────────────────┐
│ validate/default arguments                               │
│ execute tool                                              │
│ log full raw result                                       │
│ reduce result into observations and WorkingState          │
│ persist durable observations/beliefs                      │
│ return a concise structured result                        │
└──────────────────────────┬───────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
  knowledge.sqlite3                  session JSONL
  durable/queryable                  complete evidence
```

## Memory model

### Layer 1 — bounded working state

`WorkingState` is an in-memory dataclass owned by the harness. It is rendered
into a single compact block for each request and replaced rather than appended.
It is not exposed through `read_memory`/`write_memory` tools.

Initial fields:

```python
@dataclass
class WorkingState:
    objective: str
    phase: str
    location: Location | None
    vitals: Vitals | None
    plan: list[str]             # at most three immediate steps
    last_action: Action | None
    last_result: str | None
    open_questions: list[str]   # bounded
    warnings: list[str]         # combat, hunger, stale location, etc.
    actions_used: int
    actions_remaining: int | None
    knowledge_version: int
```

Rules:

- Render as compact JSON or terse labeled text, whichever produces better
  tool-use eval results.
- Target 500–800 tokens; enforce a hard configurable ceiling.
- Keep no more than three plan steps and three open questions.
- Update timestamps and counters in code, not by asking the model.
- Mark live state as unknown or stale after disconnect instead of carrying it
  forward as fact.
- Let the model propose a plan or correction only when judgment is necessary;
  ordinary movement and observation updates are automatic.

### Layer 2 — recent complete interactions

The model receives the newest complete assistant-tool interaction groups,
bounded by tokens rather than message count. An interaction contains the
assistant tool request and every associated result, so pruning cannot orphan a
tool result or cut a multi-tool response in half.

Old verbose results are replaced with deterministic records such as:

```text
move(east) -> arrived "Market Square"; exits=n,e,s,w
check(score) -> hp=16/16; move=81; gold=110; hungry=true
```

The full response remains in session JSONL for debugging and evidence.

### Layer 3 — durable knowledge

Use `.boukensha/knowledge.sqlite3` from plan 13, with two refinements:

- Add an append-only `observations` table containing session ID, tool-call ID,
  timestamp, observation type, normalized payload, and a digest or reference to
  raw evidence. Current `rooms`, `exits`, `entities`, and player-state tables are
  derived belief projections, not the only surviving record.
- Do not identify a room by name alone. Prefer a server room ID. If one is not
  available, use an area plus normalized name and description fingerprint, with
  an alias table for colloquial names. Duplicate room names must remain distinct.

Store confidence/status and `last_observed_at` on beliefs. An old position is a
lead, not proof of current live state.

Markdown `player.md` and `world.md` remain available during migration, but are
read-only legacy inputs after the structured pipeline is trusted. They are not
deleted until an end-to-end session proves that every required fact has a
structured home.

## Retrieval policy

Retrieval should normally be automatic and cached, not another mandatory model
action.

Before each request, build a bounded knowledge projection from:

- the current room and its confirmed outgoing exits;
- one-hop neighboring rooms and frontier exits;
- known entities or rooms matching the objective;
- an already computed route, if one exists;
- current player constraints relevant to the next action;
- unresolved contradictions or stale beliefs that require verification.

Cache the result by `(knowledge_version, current_room_id, objective_signature)`.
Invalidate it only when a relevant belief changes. Explicit `recall` remains an
escape hatch for unusual questions, not a required precondition for normal play.

Initial retrieval budget: 1,000–1,500 tokens. Test smaller and larger budgets in
evals rather than assuming more context is better.

## Tool interface improvements

### Correct JSON Schema

The current backend adapters mark every parameter as required even when the
Python function supplies defaults and its description calls the parameter
optional. Replace `Tool.parameters`' implicit format with an explicit schema:

```python
Tool(
    name="look",
    input_schema={
        "type": "object",
        "properties": {...},
        "required": [],
        "additionalProperties": False,
    },
)
```

All backends serialize the same schema rather than independently constructing
`required = list(properties)`. Add enums for directions, check kinds, attack
styles, positions, and other closed sets. The dispatcher applies safe defaults
and returns a short validation error before execution.

Keep a backwards-compatible decorator path long enough to port tools
incrementally, but fail tests if a tool description says an argument is
optional while its schema requires it.

### Smaller phase-specific toolsets

Define tool groups such as connection, navigation, combat, commerce, and
inventory. Select the relevant groups from `WorkingState.phase`; always retain
safe escape and status tools. A navigation request should not advertise every
spell, communication, equipment, filesystem, and combat operation.

Compare this against the full tool registry in evals. Dynamic selection is kept
only if it improves validity or latency enough to offset reduced prompt-prefix
stability.

### Concise results with complete logs

Each tool produces two representations:

- `raw_result`: complete server response, written to the logger and observation
  evidence;
- `model_result`: normalized, concise result returned to the conversation.

If parsing is uncertain, include the relevant raw excerpt and set
`parse_status="partial"`; never silently invent a normalized fact.

### Composite capability tools

Add narrowly scoped tools that remove predictable round trips:

- `snapshot()` — one request that gathers and normalizes room, exits, vitals,
  inventory, and equipment. Individual inspection tools remain available.
- `navigator(target, current_location=None)` — resolve the target and compute a
  confirmed directed route as specified in plans 13 and 14.
- `navigate_to(target)` — execute a known route, stopping on arrival or the first
  unexpected condition. Return completed steps, current location, and stop
  reason.

`navigate_to` must not blindly batch commands. It validates the observed room
after each move and stops on combat, death, disconnection, a blocked exit,
insufficient funds, exhausted movement, or disagreement with the route.

## Automatic state reduction

Add a reducer layer around `Registry.dispatch`:

```text
ToolResult(raw, normalized, observations, state_delta, status)
```

Reducers are tool-specific and deterministic where possible:

- `mud_connect`/`mud_disconnect` update connection state and freshness.
- `look` recognizes room, exits, visible entities, and descriptions.
- `move` records the attempted directed edge, destination on success, and a
  failed edge observation on failure.
- `check` updates only the requested player-state fields.
- inventory, equipment, shop, practice, and combat tools emit their relevant
  observations and warnings.

The database transaction and working-state update complete before the concise
result is returned to the model. A persistence failure does not hide a
successful game action: return `action_status="ok"` and
`memory_status="error"`, retain the raw log, and mark working state dirty for a
retry.

## Context assembly and compaction

Replace message-count deletion with a prompt budget:

```text
context window
  - reserved output tokens
  - system/tool schema budget
  - working-state budget
  - retrieved-knowledge budget
  = recent-interaction budget
```

Implementation rules:

- Check estimated pressure before every LLM request, including iterations
  inside one `Agent.run()` call.
- Use actual provider input-token counts to correct future estimates.
- Prune only complete interaction groups.
- Prefer deterministic reduction of known tool output over LLM summarization.
- Preserve the objective, working state, unresolved errors, latest valid
  location evidence, and recent interactions.
- Compact toward a real target fraction, initially 50–60 percent.
- Remove or mark wind-down instructions as ephemeral so an old "do not call
  tools" message cannot interfere with a later reprompt.
- Validate the effective runtime context independently of advertised model
  limits. Do not automatically allocate an unverified 128K/256K Ollama context
  when 16K or 32K performs better and uses less KV-cache memory.

When a backend supports prompt/KV caching, keep the system prompt and stable
tool-schema prefix unchanged. Put volatile working state and retrieval after the
stable prefix.

## Recovery and completion controls

### Loop detector

Track a signature of `(tool name, normalized arguments, result class,
location)`. If the same failed action occurs twice without new evidence, block
the third execution and return a structured recovery event. Trigger reflection
only then, or after another unexpected state, rather than paying for a separate
planning call on every iteration.

### Proof-based completion

An assistant `end_turn` is not automatically proof that a scenario succeeded.
Allow callers/evals to register deterministic completion predicates. Before
accepting success, check the predicate and, if incomplete, add one concise
message listing the missing evidence and continue within the remaining budget.

For the bakery scenario, proof includes:

- evidence of a live MUD interaction;
- evidence that the intended bakery/menu was observed;
- the expected artifact at the expected path;
- content matching specific known menu evidence, not a generic bakery word.

Interactive requests without a predicate retain normal conversational
completion.

### Conditional model escalation

Keep one primary open model for ordinary execution. Make escalation an optional
policy activated only by repeated failure, unresolved target matching, or a
low-confidence parse. Record every escalation in eval results. This must be
evaluated against simply giving the primary model more turns; a larger model is
not assumed to be better.

## Implementation stages

Each stage ends with its own tests and an eval checkpoint. Do not build the
dashboard first; it can display data only after the state pipeline is reliable.

### Stage 0 — freeze the baseline and define measurements

- [ ] Keep `week1_baseline/python/12_context` unchanged as the comparison
  implementation.
- [ ] Scaffold `week2_capable/` as an independently runnable successor with its
  own tests and package configuration.
- [ ] Add a capability configuration snapshot to every run: working-memory
  mode, result-reduction mode, retrieval budget, tool-selection mode,
  compaction target, and navigator availability.
- [ ] Extend eval output with total input tokens, total output tokens, LLM
  requests, tool calls, invalid calls, repeated calls, compactions, peak prompt
  size, time-to-first-token where available, and model/runtime context.
- [ ] Run a baseline batch before changing behavior.

**Gate:** a baseline trial remains runnable and its metrics can be compared with
later configurations without reading a transcript manually.

### Stage 1 — repair tool schemas

- [ ] Add explicit JSON Schema and `required` handling to `Tool`/`Registry`.
- [ ] Port every backend to serialize the common schema.
- [ ] Add enums, safe defaults, and `additionalProperties: false`.
- [ ] Add backend contract tests and dispatch-validation tests.
- [ ] Run the bakery eval with no memory changes to isolate schema impact.

**Gate:** optional calls such as bare `look()` validate on every backend, invalid
enum values fail before execution, and existing required arguments remain
required.

### Stage 2 — add WorkingState and state reducers

- [ ] Implement the bounded dataclass and deterministic renderer.
- [ ] Add tool-result and state-delta types.
- [ ] Wrap dispatch so raw logging, reduction, and model-result generation are
  one lifecycle.
- [ ] Implement connection, look, move, and check reducers first.
- [ ] Inject one current working-state block during prompt assembly.
- [ ] Add fixtures for successful travel, blocked travel, disconnect, malformed
  output, combat interruption, and stale state.

**Gate:** a short MUD session keeps the correct current room and last action
without any memory-file calls, and the rendered state stays below its ceiling.

### Stage 3 — make durable knowledge automatic

- [ ] Create/migrate `knowledge.sqlite3`, including observations, room aliases,
  belief tables, provenance, freshness, and change log.
- [ ] Persist reducer observations transactionally.
- [ ] Resolve duplicate room-name identity safely.
- [ ] Build the bounded automatic retrieval projection and cache.
- [ ] Retain explicit correction/note tools as escape hatches.
- [ ] Run a dual-write diagnostic session comparing structured projections with
  legacy Markdown before retiring model-driven Markdown updates.

**Gate:** reconnecting in a fresh process restores useful knowledge, verifies
live position, and continues without reading or rewriting the complete Markdown
files.

### Stage 4 — make context token-aware

- [ ] Group messages into complete interactions.
- [ ] Add deterministic reducers for old tool results.
- [ ] implement per-request budget calculation and mid-loop pressure checks.
- [ ] Preserve required state while pruning old evidence already in durable
  storage.
- [ ] Make wrap-up directives ephemeral.
- [ ] Test 8K, 16K, and 32K operational contexts on selected open models.

**Gate:** no orphaned tool results, no request exceeds its configured budget,
and a long synthetic session retains objective/location while using materially
less replayed input than baseline.

### Stage 5 — navigation and action compression

- [ ] Implement confirmed, directed, weighted route planning from plans 13/14.
- [ ] Add target aliases and conservative semantic resolution.
- [ ] Implement `snapshot()` and interruption-safe `navigate_to()`.
- [ ] Add fixture graphs for duplicate names, one-way travel, tolls, unknown
  destinations, and route changes during execution.
- [ ] Compare individual movement calls with `navigate_to` in evals.

**Gate:** known-route tasks require fewer model requests while unexpected state
still returns control after the first surprising step.

### Stage 6 — recovery and verified completion

- [ ] Add repeat-loop signatures and third-attempt blocking.
- [ ] Trigger reflection only on recovery events and milestones.
- [ ] Add optional scenario completion predicates.
- [ ] Add optional escalation policy and logging.
- [ ] Test false completion, fabricated output, repeated blocked moves, and
  unavailable model escalation.

**Gate:** the agent cannot pass the bakery eval by writing plausible invented
content, and repeated identical failures consume fewer actions than baseline.

### Stage 7 — ablation evaluation and documentation

- [ ] Run multiple repetitions for baseline, working state only, working state
  plus pruning, structured retrieval, and full navigator configurations.
- [ ] Use the same starting-state/recovery controls and model parameters.
- [ ] Compare at least one small and one stronger open tool-calling model.
- [ ] Report failures as well as successes; inspect transcripts for metric
  anomalies.
- [ ] Update the journal with measured results and decisions.
- [ ] Build only the minimum dashboard views needed to inspect current beliefs
  after the capability pipeline is proven.

**Gate:** the final report can attribute improvement to specific layers rather
than comparing only a monolithic before/after system.

## Evaluation matrix

| Variant | Working state | Reduced results | Structured retrieval | Navigator | Recovery guards |
| --- | --- | --- | --- | --- | --- |
| A — baseline | No | No | No | No | Existing only |
| B — state | Yes | No | No | No | Existing only |
| C — efficient context | Yes | Yes | No | No | Existing only |
| D — durable memory | Yes | Yes | Yes | No | Existing only |
| E — capable | Yes | Yes | Yes | Yes | Yes |

Primary metrics:

- deterministic task success rate;
- median LLM requests and tool calls per successful trial;
- total replayed input tokens and peak per-request context;
- invalid and repeated tool-call rate;
- median wall-clock time and local inference throughput;
- recovery success rate;
- false-completion/fabrication rate.

Secondary metrics include durable-memory precision against a hand-inspected
transcript fixture, route optimality, retrieval size, compaction count, and
escalation frequency.

Use at least five repetitions per important model/variant when runtime allows.
Do not claim improvement from a single stochastic run.

## Tests

### Unit tests

- Working-state rendering, bounds, stale-state transitions, and deltas.
- Tool JSON Schema serialization on every backend.
- Parser fixtures for representative MUD responses and malformed responses.
- Observation upsert, provenance, contradiction, and duplicate room names.
- Retrieval relevance, caching, invalidation, and hard token limits.
- Interaction grouping and token-aware compaction.
- Loop signatures and completion predicates.
- Directed weighted pathfinding and interruption conditions.

### Integration tests

- Fake client → model tool call → registry → reducer → state/database → next
  prompt.
- Persistence failure after a successful game action.
- Fresh process loading durable knowledge but verifying live state.
- Long synthetic tool loop crossing the compaction threshold mid-turn.
- Backend payload validation for Ollama and one hosted-compatible backend.

### End-to-end tests

- Bakery task from the controlled starting room.
- Return-to-Midgaard recovery from several known locations.
- A known route interrupted by a blocked exit or combat.
- A resume task in a fresh agent process using prior durable knowledge.

## Risks and mitigations

- **Parser mistakes become memory mistakes.** Store raw evidence and parser
  confidence; uncertain parses do not overwrite confirmed beliefs.
- **Automatic writes hide behavior.** Log observations, belief changes, and
  working-state deltas as first-class session events.
- **Composite tools over-automate play.** Validate after every internal action
  and stop on the first unexpected condition.
- **Retrieval omits a crucial fact.** Keep explicit recall as an escape hatch and
  surface retrieval metadata in logs.
- **Structured memory becomes a large side project.** Implement only fields
  required by current evals first; defer dashboard polish and broad semantic
  search.
- **Dynamic toolsets hurt prompt caching.** Measure both modes and retain the
  full stable schema if dynamic selection does not improve outcomes.
- **A large configured context slows local models.** Benchmark operational
  contexts and record actual runtime settings with every eval.
- **Legacy and new memory disagree.** Dual-write only for validation, define
  structured observations as authoritative after the migration gate, and never
  merge contradictions silently.

## Scope boundaries

In scope:

- working and durable memory;
- prompt/context efficiency;
- tool-schema reliability;
- targeted retrieval;
- safe navigation and reduced round trips;
- recovery, completion verification, and evals.

Deferred unless all capability gates pass:

- a polished multi-tab knowledge dashboard;
- general-purpose vector search;
- autonomous multi-agent planning;
- training or fine-tuning a model;
- replacing the MUD server or protocol;
- broad support for arbitrary games beyond the current structured tool layer.

## Definition of done

The final-week capability is complete when:

1. A fresh process can resume from structured durable knowledge while
   re-verifying live state.
2. Normal play does not require model-driven memory read/write/read-back loops.
3. Working state remains within its configured bound and old raw tool output is
   not replayed indefinitely.
4. Tool schemas correctly distinguish required and optional parameters across
   backends.
5. Compaction is token-aware, preserves complete interactions, and can occur
   during a long turn.
6. Navigation reduces model round trips without crossing an unconfirmed edge or
   hiding an unexpected event.
7. Loop detection and deterministic completion checks prevent known repeated
   failure and false-success modes.
8. Multi-run ablations show the effect on success, tokens, calls, and latency.
9. The journal records what actually worked, what failed, and which planned
   features were intentionally deferred.

## Outcome

Pending. Fill this section with implementation commits, eval tables, and the
final architectural verdict after the staged gates have been run.
