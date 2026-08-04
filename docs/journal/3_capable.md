# Final Week Journal — Making Boukensha Capable

**Started:** August 4, 2026  
**Status:** Planning complete; implementation not started  
**Implementation plan:**
[State-Aware Execution & Efficient Memory](../plans/16_state_aware_execution.md)

## Where this week begins

The assignment for the final week is "capable": improve the agent itself, not
just the interface around it. My first instinct was to add working memory. The
earlier MUD experiments had already shown why memory matters: an agent operating
in a persistent world cannot safely reconstruct its location, discoveries, and
unfinished objective from guesses after every interruption.

The existing solution proved the value of memory, but it also exposed the wrong
way to scale it. Boukensha currently keeps `player.md` and `world.md` as
canonical prose files. The model must read both at startup and repeatedly read,
rewrite, and verify them as it plays. Because each tool call and complete file
contents also enter the conversation, the mechanism intended to preserve state
quickly becomes a major source of context growth.

That is the tension this week will address: the agent should remember more while
the model has to read and do less.

## Evidence from the baseline

This direction is based on behavior already present in the repository rather
than a hypothetical memory problem.

- The system prompt mandates both memory-file reads before gameplay and a
  checkpoint at least every four MUD commands.
- A checkpoint requires read, full-document rewrite, and read-back verification.
- Entering a room, learning an exit, changing location or vitals, combat, and
  purchases all independently trigger immediate checkpoints. In an exploration
  task, that is close to every useful action.
- The memory files are several kilobytes of prose and include route tables,
  current state, old discoveries, caveats, and next actions together.
- Every tool result remains in the message history sent again on later model
  calls.
- Current compaction drops messages by count. It does not know that one result
  may contain an entire memory file while another is a one-line acknowledgement.
- Automatic compaction happens before a turn starts, so a single long-running
  tool loop can continue growing without another pressure check.
- Backend tool schemas currently mark every property required, even for Python
  tool functions and descriptions that define optional arguments. This creates
  unnecessary failure pressure for smaller tool-calling models.
- Some configured local-model context windows are estimates, yet Ollama is asked
  to allocate that entire value through `num_ctx`. A large theoretical window
  may therefore cost memory and latency without improving the active reasoning
  context.

The eval work reinforced the larger lesson. Models fabricated plausible output,
repeated unproductive actions, stopped before completing promised work, and
varied in reliability in ways that did not track parameter count cleanly. The
harness and task design matter as much as the model.

## The architectural decision

Working memory will not be another document or another pair of tools.

It will be a small state object maintained by the harness and refreshed as a
side effect of ordinary tool execution. The model will see the current
projection automatically on its next request. It will not spend an action
reading it, writing it, or checking whether its own write succeeded.

The memory system will have three layers:

1. **Working state:** objective, phase, current location, short plan, most recent
   action/result, immediate warnings, and unresolved questions. This is bounded
   and replaced in place.
2. **Recent interactions:** only the newest complete tool-call/result groups.
   Older verbose results become short deterministic records.
3. **Durable knowledge:** structured observations and beliefs in SQLite,
   retrieved only when relevant to the current location or objective.

The complete raw output remains available in session logs. Prompt context is a
decision aid, not an audit log.

## How this changes the earlier knowledge plan

Plans 13 and 14 proposed a structured knowledge database and a navigator. Those
remain useful foundations, but the first design still expected the model to
call tools such as `remember_room`, `remember_exit`, and `record_stat` as part of
normal play. That is better than rewriting Markdown, but it still charges the
model an action for deterministic bookkeeping.

The revised design moves ordinary memory writes into the tool dispatcher:

```text
move east
  -> receive the MUD response
  -> log the full evidence
  -> parse the room and exits
  -> update current working state
  -> persist observations and beliefs
  -> return one concise result to the model
```

Explicit memory tools remain useful for corrections, uncertain interpretations,
and notes that require judgment. They should be the exception rather than the
path every movement command takes.

The database will also preserve append-only observations and provenance instead
of holding only the newest belief. If a parser or model gets something wrong, I
want to be able to trace the belief back to the session and tool result that
created it.

## What "more capable" means here

This week is not successful merely because `knowledge.sqlite3` exists or a
dashboard can display it. Capability has operational definitions:

- complete the same task more often;
- use fewer model requests and fewer bookkeeping tool calls;
- replay fewer total input tokens;
- avoid invalid and duplicate calls;
- resume safely in a fresh process;
- use known routes without re-exploring them;
- interrupt automation when the live world differs from memory;
- refuse to declare deterministic tasks complete without the required evidence.

These definitions deliberately connect architecture to the eval harness. They
also make it possible for a simpler feature to beat a more impressive-looking
one. If bounded working state improves results and a semantic retrieval layer
does not, the correct outcome is to keep the former and defer the latter.

## Planned build sequence

### 1. Capture a trustworthy baseline

Before changing behavior, preserve the step-12 implementation and run the
existing scenario with expanded metrics. Record pass/fail, model requests,
tool calls, repeated/invalid calls, total replayed input, peak prompt size,
duration, and actual runtime context configuration.

This prevents the final comparison from becoming a memory-based impression of
whether the new agent "felt better."

### 2. Repair tool contracts

Required and optional arguments need to be represented correctly in every
backend. Closed choices such as directions and check kinds should be enums, and
unknown properties should be rejected before dispatch. This is a small change
with a clean ablation: run the same task before adding working memory and see
whether schema correctness alone improves open-model tool use.

### 3. Add harness-owned working state

Implement a bounded `WorkingState`, tool-specific state deltas, and one compact
rendered state block in prompt assembly. Start with connection, `look`, `move`,
and `check`, since they cover the core navigation loop.

The important test is not whether the dataclass can be serialized. It is
whether a real short session maintains the correct current room and next-action
context without any model-driven memory-file calls.

### 4. Persist observations automatically

Add the structured database, append-only evidence, current belief projections,
and targeted retrieval. During migration, compare structured state with the
legacy Markdown output rather than immediately deleting the old files.

Room identity needs special care. A name is not necessarily unique, so a server
identifier is preferred; otherwise the store needs area/fingerprint identity
and aliases.

### 5. Bound the active context

Group history by complete interaction, reduce old raw outputs, and calculate a
real token budget before each request. Working state, the objective, unresolved
errors, and current location survive compaction. Old evidence already captured
in SQLite does not need to stay in the prompt forever.

I will also benchmark realistic operational contexts for local models rather
than assuming their largest advertised or estimated window is the best choice.

### 6. Turn knowledge into action

The navigator makes durable memory useful. It resolves known targets, computes
only confirmed directed routes, accounts for weighted costs, and can execute a
route while verifying every step. A route stops immediately on a blocked exit,
combat, death, disconnection, resource problem, or unexpected room.

A composite `snapshot` tool will similarly combine the predictable set of
state checks needed at startup or recovery.

### 7. Add recovery and proof

Detect repeated identical failures and block a third blind attempt. Reflection
is triggered by this event rather than added as an expensive extra model call
after every action.

For deterministic scenarios, an ordinary text completion is not sufficient.
The harness checks scenario proof and returns missing criteria if the agent
stops early. This builds the lessons from the fabricated bakery menus directly
into the agent loop.

### 8. Run ablations

Evaluate baseline, working state, reduced context, structured retrieval, and the
full navigator/recovery configuration separately. Use repeated trials on at
least one small and one stronger open model. The goal is to identify which
layers create the improvement, not merely show that the final bundle differs
from baseline.

## Decisions made now

- The frozen baseline remains intact; capability work lives in
  `week2_capable/`.
- Working state is harness-owned and has a hard size bound.
- Raw evidence remains in logs, not indefinitely in prompts.
- Ordinary memory updates happen during tool dispatch.
- Structured observations retain provenance and uncertainty.
- Retrieval is automatic, bounded, and cached; explicit recall is an escape
  hatch.
- Deterministic parsing/pathfinding/validation stays deterministic.
- Composite movement verifies after every step and stops on surprises.
- The full knowledge dashboard is lower priority than capability and evals.
- Open models are compared by measured task behavior, not parameter count or
  theoretical context alone.

## Questions to answer through implementation

- Is compact JSON or terse labeled text easier for the tested open models to
  use as working state?
- What working-state and retrieval budgets preserve the right facts without
  distracting smaller models?
- How much raw MUD output can be reduced deterministically before useful nuance
  is lost?
- Does a phase-specific tool menu improve tool validity enough to compensate
  for changing the otherwise stable prompt prefix?
- Which room outputs can be parsed with rules, and where is a fallback extractor
  genuinely necessary?
- Does `navigate_to` improve success, or only reduce calls on tasks the agent
  already solves?
- At what active context size do the local models achieve their best balance of
  reliability, latency, and memory use?
- Is escalation to a stronger open model more effective than giving the primary
  model another bounded recovery attempt?

## Implementation log

This section will be updated as work lands. Each entry should include the
change, verification performed, measured result, surprise or failure, and the
decision that followed.

### 2026-08-04 — Planning

Reviewed the baseline memory prompt, context implementation, agent loop, tool
schemas, existing structured-knowledge/navigation plans, and eval lessons. The
initial idea of "add working memory" became a broader state-aware execution
design after identifying that model-managed memory was itself creating much of
the context and tool-call overhead.

The detailed staged plan was written in
`docs/plans/16_state_aware_execution.md`. No capability code has been changed
yet, and no result is being claimed in advance.

### 2026-08-04 — Runtime Ollama discovery and tool-loop probes

The eval runner no longer needs a manually maintained list of installed Ollama
tags. It resolves the existing configured host, reads `/api/tags`, inspects
`/api/show` capabilities, deduplicates aliases by digest, and can select all
tool-advertising completion models. The backend's static model table now
supplies verified metadata only instead of rejecting every unknown tag.

An optional two-request probe was added before full MUD trials. It verifies an
exact tool call and the model's next completion after the result, using the
same message ordering as Boukensha. Live checks passed for `gemma4:latest`,
`gemma4:26b`, and `qwen3.5:0.8b`. This rules out the minimal Ollama round trip as
the sole cause of earlier Gemma gameplay loops while leaving the larger tool
schema/action-selection problem open. No private Ollama hostname is embedded or
written to eval output.

### Stage 0 — Baseline and metrics

Pending.

### Stage 1 — Tool schemas

Pending.

### Stage 2 — Working state and reducers

Pending.

### Stage 3 — Durable knowledge and retrieval

Pending.

### Stage 4 — Context budgeting

Pending.

### Stage 5 — Navigation

Pending.

### Stage 6 — Recovery and completion proof

Pending.

### Stage 7 — Ablation results

Pending.

## Expected final reflection

The final entry should answer a narrower question than "did memory help?":

> Which state should be maintained by code, which knowledge should be retrieved,
> and which decisions still benefit from the model?

That boundary is the real capability lesson. A model becomes a better agent not
only by receiving more information, but by having the surrounding system carry
state, validate actions, and perform deterministic work so the model can spend
its limited context and inference time on decisions that actually require it.
