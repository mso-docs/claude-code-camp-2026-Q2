# Week 2 · Navigator Tool — Semantic Matching, Weighted Pathing & Reasoned Targets

**Lives in:** `week2_capable/` (alongside the knowledge base in
[13_knowledge_observability.md](13_knowledge_observability.md))
**Builds on:** the `rooms`/`exits`/`entities` schema and the
`have_i_been`/`plan_route` design from plan 13
**Status:** Planned
**Prompted by:** an instructor whiteboard example contrasting two task
shapes — "find the bakery (known location)" vs. "find a danish (reason
the location)" — feeding a single `navigator` tool, plus notes calling
out semantic name-matching, Dijkstra specifically, and an unresolved
hazard question.

## Goal

One `navigator` tool the agent calls with a target and its current
position, that works whether the target is a location the agent already
knows by name, or a *thing* it has to first reason its way to a location
for. Plan 13's `plan_route` covered the first case with plain BFS over
unweighted, exact-name-matched edges; this plan refines that into what
the whiteboard actually specifies — weighted pathing and a name/target
resolution step in front of it.

## Two task shapes, one tool

**Case 1 — known location** ("find the bakery"): the agent already has
`Have I been there? / Do I know an ideal path from my current location?`
answered by the knowledge base directly. This is plan 13's
`have_i_been` + `plan_route`, largely unchanged.

**Case 2 — reasoned location** ("find a danish"): the target isn't a
room name at all — it's a thing that must first be resolved to a
location. "Danish" isn't in `rooms`; it's the kind of thing a bakery
sells. This needs a resolution step *before* pathfinding can start:
search `entities` (and room `notes`/descriptions) for something matching
the target conceptually, arrive at a candidate room, *then* hand that
room to the same pathing logic as case 1. The whiteboard only sketches
this branch (a single arrow, no worked example) — treat the resolution
step as the open design problem it is, not a solved one.

`navigator(target, current_location=None)` is the single entry point for
both; internally it either finds `target` directly in `rooms`
(name/alias match) or falls through to the reasoning-resolution step
before pathing.

## Design — semantic name matching

The whiteboard's own worked example is the reason this needs a step of
its own: "The Golden Bakery <> Bakery — semantic matching worked." The
agent (or the user) will refer to places by shorthand/common names that
don't equal the stored room name string. Plan 13's `have_i_been` was
specified as "exact, falling back to fuzzy" — this plan makes that
concrete: matching needs to handle a colloquial target name against a
formal stored room name, not just typos. Open question on mechanism —
substring/keyword matching, an embedding-similarity lookup, or handing
the candidate list to the model itself and letting it pick — no decision
made yet, but whichever is chosen has to run *before* `plan_route`, since
pathing needs a resolved `room_id` to start from.

## Design — weighted pathing (Dijkstra, not BFS)

Plan 13 specified breadth-first search on the assumption that every exit
costs one uniform "hop." The whiteboard note ("djikstra pathing",
highlighted) points at something plain BFS can't do: shortest-*hop-count*
and cheapest-*actual-cost* aren't always the same route once exits carry
different costs. This project's own `player.md` already documents a case
where they diverge — some directions require paying a gold toll to pass.
"Ideal path" has to mean cheapest weighted path, not fewest rooms.

This means `exits` needs a `cost` column (default `1`, overridden where a
toll or other penalty is known) and `plan_route` needs to become an
actual Dijkstra/weighted-shortest-path implementation over that column,
superseding plan 13's plain-BFS description. Directedness and the
confirmed-edges-only rule from plan 13 still apply unchanged — this only
changes how a route's cost is computed, not which edges are eligible.

## Open question — hazard awareness

The whiteboard's last line, unresolved even there: "But what if there is
a volcano." A cheapest-by-gold-cost route could still route through a
room known to be dangerous (hostile entities, an environmental hazard).
Options, none decided:

- Fold hazard into the same `cost` weighting (a dangerous room/exit gets
  a high cost rather than being a separate concern) — simplest, but
  conflates "expensive" with "risky," which may not be the same
  trade-off a caller wants to make.
- A separate exclusion filter (avoid rooms tagged hazardous entirely
  unless no other route exists) — cleaner semantically, more moving
  parts.
- Out of scope for a first pass — ship weighted pathing without hazard
  awareness, note the limitation, revisit once there's an actual
  hazardous-room case in captured play to design against instead of a
  hypothetical volcano.

Leaning toward the third (ship the simpler version, extend once there's
a real case), but flagging rather than deciding, since it wasn't
resolved on the whiteboard either.

## Scope — what this changes in plan 13

- `exits` gains a `cost` column (plan 13's schema listed `id,
  from_room_id, direction, to_room_id, status, notes` — add `cost
  INTEGER DEFAULT 1`).
- `plan_route`'s algorithm changes from BFS to Dijkstra (or equivalent
  weighted shortest-path); the confirmed-edges-only and
  directed-graph-only rules carry over unchanged.
- `have_i_been` gains the semantic-matching step described above rather
  than exact-match-with-fuzzy-fallback.
- New: a `navigator` tool that wraps target resolution (case 1 direct,
  case 2 reasoned) in front of `plan_route`, rather than the agent
  calling `have_i_been`/`plan_route` separately for every task.

## Verification plan

- Weighted routing: a fixture graph where the fewest-hops route and the
  cheapest-cost route differ (a toll on the short path) — confirm
  `plan_route` returns the cheaper one, not the shorter one.
- Semantic matching: "Bakery" resolves to a stored room named "The
  Golden Bakery" (or similar formal/shorthand mismatch); an unrelated
  target returns no match rather than a false positive.
- Reasoned-location case: given a target that isn't a room name (e.g.
  "danish") but the knowledge base has an entity/description linking it
  to a room (e.g. a bakery's menu), confirm resolution lands on that
  room before `plan_route` is invoked — and confirm a target with *no*
  plausible match returns an explicit "can't resolve" result rather than
  guessing.
- Regression: existing plan-13 confirmed-edges-only and directed-graph
  behavior still holds under the new weighted algorithm.

## Outcome

Pending — not yet built.
