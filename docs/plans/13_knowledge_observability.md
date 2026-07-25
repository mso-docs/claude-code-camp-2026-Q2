# Week 2 · Structured Knowledge Base & Observability Dashboard

**Lives in:** `week2_capable/` (currently empty — first build to land there)
**Builds on:** `week1_baseline/python/12_context` (agent, tools, logger),
`week1_baseline/ruby/log_viz` (existing session-log dashboard)
**Status:** Planned
**Prompted by:** an instructor example — a "Knowledge" dashboard tab
(Overview / Rooms / Map / Entities / Frontier / Player / Progression)
reading from a `knowledge.sqlite3`, with a separate Change Log page for
raw per-record history.

## Goal

Give the agent a structured, queryable belief store instead of the two
freeform markdown files it maintains today, and a dashboard that can
show map/entity/stat state as of now *and* how it got there over time —
things prose files can't answer without a human reading every revision.

## Current state (what this replaces)

- `.boukensha/memory/world.md` and `.boukensha/memory/player.md` — the
  agent rewrites these wholesale via the generic `read_file`/`write_file`
  tools ([file_system.py](../../week1_baseline/python/12_context/boukensha/tools/file_system.py)),
  guided only by system-prompt instructions to checkpoint every few
  actions. See both files for what this looks like in practice: room
  tables with a `Status: Confirmed / Unconfirmed` column, explicit
  "do not assume" caveats, an "Unresolved Objectives" section — all of it
  free text the agent composes fresh each checkpoint.
- `week1_baseline/ruby/log_viz` — reads `.boukensha/sessions/*.jsonl` and
  renders a session as a transcript (tool calls, tokens, cost). It shows
  *what the agent did*, not *what the agent currently believes* — there's
  no view of accumulated world/player state at all, and no history of how
  a given belief changed across sessions short of diffing markdown by
  hand.

The gap this plan closes: turn "belief" into rows with timestamps, so a
dashboard can query it directly instead of a human parsing prose.

## Design — `knowledge.sqlite3` schema

One new file, `.boukensha/knowledge.sqlite3`, alongside the existing
`sessions/` and `memory/` directories (`memory/*.md` can stay as the
agent's own scratch/reasoning space, or be retired once the tools below
cover everything it currently holds — open question, see below).

- **`rooms`** — `id, name, description, status (confirmed/partial/unconfirmed),
  first_seen_session_id, last_seen_session_id, notes`. `notes` is a free-text
  escape hatch for exactly the kind of caveat `world.md` uses today
  ("do not label this room X unless a future `look` confirms the title").
- **`exits`** — `id, from_room_id, direction, to_room_id (nullable),
  status (confirmed_by_travel/described/unconfirmed), notes`. A row with
  `to_room_id IS NULL` or `status != confirmed_by_travel` *is* the
  frontier — no separate frontier table needed, just a view/query
  (`WHERE to_room_id IS NULL OR status = 'unconfirmed'`).
- **`entities`** — `id, name, type (npc/monster/shop/item), last_room_id,
  first_seen_session_id, last_seen_session_id, notes`.
- **`player_stats`** — append-only: `id, session_id, recorded_at, stat_name,
  value`. One row per observed change (level, exp, exp_to_next, gold, hp,
  mana, movement, hunger/thirst flags, ...) — this is what feeds the
  screenshot's per-stat sparkline cards ("now X · min-max over N points").
- **`change_log`** — append-only audit trail: `id, session_id, changed_at,
  table_name, record_id, field, old_value, new_value`. Every write to
  `rooms`/`exits`/`entities` appends here (in application code — a tool
  wrapper, not a raw SQLite trigger, so it can also capture *why*, e.g.
  the acting tool call). This is what backs the dashboard's separate
  Change Log page and the Progression tab's "N points over time" framing
  — `player_stats` already is a change log for numeric stats; `change_log`
  covers everything else (a room's status flipping from unconfirmed to
  confirmed, an exit gaining a destination).

## Design — new agent tools

Raw `write_file` can't safely target a database, so this needs dedicated
tools registered the same way `file_system.register` and `mud.register`
are today (`week1_baseline/python/12_context/boukensha/tools/`):

- `remember_room(name, description, status, notes=None)` → upsert by name
- `remember_exit(from_room, direction, to_room=None, status, notes=None)`
- `remember_entity(name, type, room, notes=None)`
- `record_stat(stat_name, value)` — for player vitals/progression
- `recall(query)` or a small set of `list_rooms` / `list_entities` /
  `list_frontier` read tools, so the agent can check its own beliefs
  before acting instead of re-deriving them from the conversation
  transcript each time
- `have_i_been` / `plan_route` — pathfinding over the `exits` graph, see
  its own design section below

Each write tool appends to `change_log` internally — the agent doesn't
manage that table directly. This is the actual behavior change from
today's approach: the agent stops *composing* memory as prose and starts
*reporting facts* through a narrow interface, same shift as any
normalized-storage migration.

## Design — pathfinding tools

**Superseded in part by [14_navigator_tool.md](14_navigator_tool.md)** —
`plan_route`'s algorithm below is written as plain BFS over unweighted
edges; plan 14 revises this to weighted (Dijkstra) pathing once exits
can carry different costs (e.g. gold tolls), and adds a semantic
target-matching step in front of it. The confirmed-edges-only and
directed-graph rules described here still hold unchanged under that
revision.

The reason the knowledge base needs to exist isn't only observability —
it's so the agent can check what it already knows *before* acting instead
of re-exploring blindly. Two more tools alongside the write tools above:

- **`have_i_been(name)`** — match against `rooms` by name (exact, falling
  back to fuzzy), returns whether it's known and, if so, its `status` and
  last-seen info.
- **`plan_route(destination)`** — BFS over `exits` from the player's
  current room, restricted to `status = confirmed_by_travel` edges only
  (an `unconfirmed` or `described` exit is a guess, not a safe route to
  route-plan through). Returns a direction sequence (e.g. `["e", "e",
  "s"]`), or an explicit "no known confirmed path" result if the
  destination isn't reachable yet — itself useful signal, telling the
  agent it needs to explore rather than assume a shortcut exists.

**Exits must be walked as a directed graph, not assumed reversible.**
`world.md` today already documents rooms where the reverse direction
wasn't confirmed (e.g. the western city-wall room's east exit "is
expected to return toward Poor Alley, but this reverse route was not
captured directly"). BFS over `exits` needs to respect edge direction
exactly as recorded — walking only rows where `from_room_id` matches the
current room — or `plan_route` will suggest paths back through exits
that were never actually confirmed, silently reintroducing the same kind
of unverified assumption the `status` column exists to prevent.

Both tools are read-only queries — no `change_log` entries, since they
don't change any belief, only report on the existing one.

## Design — dashboard

Extend the existing `week1_baseline/ruby/log_viz` Sinatra app rather than
standing up a second server: it already owns the "read `.boukensha/`,
render it in a browser" job, and this is a second data source under the
same job description, not a different one. Add:

- A **Knowledge** nav item alongside the current session list, opening
  onto sub-tabs matching the instructor example: Overview, Rooms, Map,
  Entities, Frontier, Player, Progression. A second instructor screenshot
  (the Map tab itself) confirms the header framing that should sit above
  every sub-tab, not just Map: *"What the agent believes about the world,
  read from `knowledge.sqlite3`. Everything here is belief, not fact —
  including the rooms it identified wrongly."* That line matters as a
  design constraint, not just copy — the dashboard's job is to render
  `rooms.status`/`exits.status` honestly (including `unconfirmed` and
  wrong entries) rather than quietly filtering bad beliefs out, which is
  the whole reason those status columns exist in the schema above.
- **Map** — node/edge rendering, rooms as boxes with the connecting exits
  as edges, confirmed against the instructor's Map tab:
  - **Layout**: rooms placed by BFS outward from room `#1` (or whichever
    room the agent started in), following the directions it believes
    connect them — not a force-directed/generic graph layout. Since a
    MUD's room graph isn't planar (two different paths can disagree
    about where a room "should" sit spatially), an edge whose endpoints
    don't reconcile with that grid placement is drawn **dashed** instead
    of forcing a wrong geometry. Worth carrying that specific rule
    forward regardless of rendering-library choice (see open question
    below) — it's a placement/conflict rule, not a styling detail.
  - **Per-room tag badges** — each box shows short tags (materials,
    NPCs present, notable features — e.g. "cityguard", "marble",
    "gold") pulled from `entities.last_room_id` joined against the room,
    plus keywords surfaced from `notes`/`description`. A straightforward
    query-and-render once `entities` exists; no new schema needed.
  - **Controls**: `Fit` (zoom-to-fit), `Centre on player` (recenter on
    the room matching current `player_stats`/session position), `Show
    frontier` (toggle whether unconfirmed/dangling exits render at all —
    ties directly to the frontier query already defined above), `Detail`
    (toggle the tag badges on/off for a denser view).
  - **Summary line**: a room/exit/unvisited count (e.g. "44 rooms · 68
    known exits · 26 unvisited") — cheap aggregate queries
    (`COUNT(*)` on `rooms`, `exits`, and the frontier query), worth
    surfacing on Overview too rather than only above the Map.
- **Progression** queries `player_stats` grouped by `stat_name`, one
  sparkline/line chart per stat, matching the "now / min-max / N points"
  card format shown in the example.
- A separate **Change Log** page, paginated, straight off the
  `change_log` table — the "full per-record change data" the example
  screenshot links out to.
- Read-only, same guarantee `log_viz`'s README already states for session
  logs ("It only reads the `.jsonl` files — nothing is written back") —
  the dashboard should never write to `knowledge.sqlite3`, only the
  agent's own tools do.

## Open questions

- **Does `memory/*.md` disappear entirely, or keep a role?** The prose
  files currently carry judgment calls ("do not infer a fixed route from
  a random `flee` result") that don't map cleanly onto rows. Leaning
  toward: structured tables for anything the dashboard needs to show or
  graph, `notes` columns as the escape hatch, and retiring the markdown
  files once a full session confirms the tools cover the same ground —
  but not deleting them until that's actually verified, not assumed.
- **Map rendering approach** — the *layout algorithm* is no longer open
  (BFS-outward placement from the start room, dashed edges on spatial
  conflict — see above), but *how* to render that is: SVG generated
  server-side, or a small JS graph library client-side handed
  precomputed node positions? Needs a decision before the Map tab is
  built; doesn't block schema or the other tabs.
- **Ruby (`log_viz`) vs. Python for the dashboard** — deliberately
  deferred. Unlike `week1_baseline`, nothing in `week2_capable/` requires
  Ruby — `log_viz` came bundled with the repo's initial commit rather
  than being something written as part of the course exercise, and there
  is no reference implementation to port here. Schema and tool work
  (this plan's other sections) don't depend on this choice, so it can
  proceed now; decide the dashboard's language once that groundwork is
  working. Python keeps one language across the whole project and is
  fastest to build; extending `log_viz` in Ruby is mostly read-only
  querying + templating, a lower-stakes way to start learning Ruby than
  systems-level code would be.
- **Migration of existing sessions** — current `.jsonl` logs and
  `memory/*.md` predate this schema; no backfill planned (Progression
  charts simply start from whenever this ships), but flagging so it
  isn't assumed to happen automatically.

## Verification plan

- Schema round-trip: each tool (`remember_room`, `remember_exit`,
  `remember_entity`, `record_stat`) writes the expected row(s) and the
  matching `change_log` entry, including on update (not just first
  insert) — an upsert that changes `status` from `unconfirmed` to
  `confirmed` must produce an old/new pair in `change_log`, not silently
  overwrite.
- Frontier query returns exactly the exits with `to_room_id IS NULL` or
  non-confirmed `status`, cross-checked by hand against a small fixture
  world.
- `plan_route` against a fixture graph with a deliberately asymmetric
  edge (confirmed one direction, unconfirmed/absent the reverse) —
  confirm it never proposes travel through the unconfirmed direction,
  and returns "no known confirmed path" rather than guessing when the
  destination is only reachable that way. `have_i_been` against both a
  known and an unknown room name, including a fuzzy-match case.
- Dashboard: each tab renders against a fixture `knowledge.sqlite3` with
  a handful of rooms/exits/entities/stats spanning multiple sessions;
  Progression sparkline point counts match the underlying `player_stats`
  row counts per stat.
- End-to-end: run the agent against the MUD for a short session with the
  new tools registered, confirm `knowledge.sqlite3` accumulates rows
  matching what a human reading the transcript would extract, then
  confirm the dashboard reflects it without restart (or documents that a
  restart/refresh is required).

## Outcome

Pending — not yet built.
