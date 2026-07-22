# MUD Evaluation Completion Report

**Status:** In Progress
**Harness:** `<harness>`
**Model:** `<display name>`
**Model ID:** `<provider/model-or-model-id>`
**Test:** Test `<N>` — `<objective name>`
**Report key:** `<harness>-<model-slug>-test<N>`
**Started:** `<timestamp>`
**Last updated:** `<timestamp>`

## Objective Checklist

| Step | Objective | Status | Live evidence |
| --- | --- | --- | --- |
| 1 | `<objective>` | Pending | — |

## Starting Memory

- Player state loaded: `<summary>`
- World knowledge loaded: `<summary>`
- Prior attempt or report state: `<summary or none>`
- Initial recommended action: `<action>`

## Attempts and Checkpoints

### Attempt 1

#### Checkpoint 0 — Initialization

- MUD commands since previous checkpoint: 0
- Current objective step: `<step>`
- Findings: `<verified findings>`
- Player-memory changes: `<exact facts or none>`
- World-memory changes: `<exact facts or none>`
- Command-memory changes: `<new live-confirmed working commands or none>`
- Next action: `<action>`

Add a checkpoint subsection after every required checkpoint and numbered test
step. Preserve earlier entries.

## Findings

### Player

- `<verified player fact>`

### World and Routes

- `<verified world fact>`

### Commands and Mechanics

- `<verified command or mechanic>`

## Errors and Recovery

- `<error, evidence, recovery, or none>`

## Final Game Save

- Command: `save`
- Response evidence: `<captured response or not attempted>`
- Persistence verified: No

## Memory Changes

### `data/player.md`

- `<exact fact written>`

### `data/world.md`

- `<exact fact written>`

### `data/commands.md`

- `<new live-confirmed working command or none>`

## Final State

- Location: `<room or unknown>`
- Vitals/status: `<state or unknown>`
- Inventory/equipment/currency: `<relevant state or unknown>`
- Objective state: `<state>`
- Recommended next action: `<action>`

## Result

**Status:** In Progress

- Pass criteria satisfied: No
- Blocker or failure: `<none or exact blocker>`
- Verification performed: `<report and memory read-back status>`
