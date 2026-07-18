# Using OpenCode for the MUD Evaluation

This guide configures OpenCode to use the repository's Ollama server, read the MUD instructions, start CircleMUD when necessary, maintain one authenticated session, execute Tests 2–4 sequentially, update memory during play, and write separate OpenCode completion reports.

## Prerequisites

Install or confirm:

- OpenCode CLI
- Docker with the Compose plugin
- `nc`, `tmux`, and Python 3
- Access to the Ollama server configured by `OLLAMA_HOST`

Install OpenCode through npm if needed:

```bash
npm install -g opencode-ai
hash -r
opencode --version
```

OpenCode's official documentation also lists other installation methods: <https://opencode.ai/docs>.

## Configure the Environment

The repository-root `.env` is ignored by Git. Define these variables without committing the file:

```dotenv
OLLAMA_HOST=http://your-ollama-server:11434
MUD_USERNAME=your-character-name
MUD_PASSWORD=your-character-password
```

Do not put credentials in scripts, reports, memory files, or command arguments.

The checked-in [`opencode.json`](../opencode.json) uses `OLLAMA_HOST` and selects `ollama/qwen3.6:35b-a3b` by default. Confirm the configured models with:

```bash
opencode models ollama
```

## How the Repository Integration Works

OpenCode uses four layers:

1. `opencode.json` configures the Ollama provider and default model.
2. `.opencode/agents/mud-evaluator.md` defines the primary evaluation agent and its permissions.
3. `.opencode/skills/` provides server, login, gameplay, report, durable-memory, and CLI-tool workflows.
4. `week0_explore/explore_architecture/001_playing_agent/AGENTS.md` defines the test objectives, checkpoint cadence, memory requirements, and stop/continue protocol.

Launch from the directory containing `AGENTS.md`. OpenCode discovers project configuration and skills while walking up to the Git worktree, but it does not search downward from the repository root for nested `AGENTS.md` files.

## Start the MUD Evaluation Agent

From the repository root:

```bash
cd week0_explore/explore_architecture/001_playing_agent
opencode --agent mud-evaluator
```

When the TUI opens, enter:

```text
start
```

The agent will:

1. Read `AGENTS.md`, `data/player.md`, and `data/world.md`.
2. Select the earliest unfinished OpenCode test from Test 2 through Test 4.
3. Create its OpenCode report with `Status: In Progress` before connecting.
4. Ensure the Docker service and port 4000 are ready.
5. Establish or reuse one persistent authenticated MUD session.
6. Execute only the selected test.
7. Update player memory, world memory, and the report at every checkpoint.
8. Finish and verify the report before asking whether to continue.

After a completed test, respond in the same OpenCode session:

```text
yes
```

Control messages are:

| Message | Behavior |
| --- | --- |
| `start` | Run the earliest unfinished OpenCode test |
| `yes` | Run the next test in sequence |
| `test N` | Run only the specified test |
| `retry` | Retry the most recently attempted test |
| `quit` | Stop without starting another test |

The agent executes no more than one top-level test per message.

For Test 2, "practice `kick`" means training with Dummy's Sentress guildmaster,
not using `kick` against an NPC. The destination is the Tournament and Practice
Yard inside the Guild of Swordsmen. From the Temple, the confirmed navigation
lead is `s, s, e, e, s, e, s`; the agent must still verify each room live and
then issue `practice kick` while the guildmaster is present.

## OpenCode Completion Reports

The evaluator writes new reports without overwriting the earlier Qwen/Pi results:

```text
week0_explore/explore_architecture/002_agent_skills/completion-report/
├── opencode-qwen3.6-35b-a3b-test2-completion.md
├── opencode-qwen3.6-35b-a3b-test3-completion.md
└── opencode-qwen3.6-35b-a3b-test4-completion.md
```

Only these reports control OpenCode test selection. Existing `qwen3.6-test*-completion.md` statuses are context, not proof that an OpenCode run passed.

The `write-completion-report` skill initializes the selected report before
gameplay and updates it after each numbered test step and memory checkpoint.
The `manage-mud-memory` skill reads `data/player.md`, `data/world.md`,
`data/commands.md`, and the selected report at the start of every session, then
writes and verifies durable handoffs throughout the test. `data/commands.md` is
a positive-only TBA MUD glossary: only commands proven to work by captured game
output are added, while failed guesses remain in the current report. This
file-backed memory lets a new model session resume verified state; it does not
retrain or modify the model itself.

## Server Commands

The `manage-mud-server` skill uses:

```bash
data/code/mud-server.sh status
data/code/mud-server.sh ensure
data/code/mud-server.sh logs
```

- `status` checks Compose and port 4000 without changing state.
- `ensure` starts only the `circlemud` service when necessary and waits for readiness.
- `logs` shows recent bounded service logs.

The tool intentionally does not provide volume deletion, pruning, or `down -v` operations.

## Login and Session Commands

The `login-mud` skill uses:

```bash
data/code/mud-login.sh start
data/code/mud-login.sh status
data/code/mud-login.sh capture
printf '%s\n' 'look' | data/code/mud-login.sh send
data/code/mud-login.sh stop
```

`start` waits through client detection and the name/password/menu prompts on one socket. The authenticated connection remains alive in the `opencode-mud` tmux session. Each `send` call counts as one MUD command for checkpoint purposes.

Do not stop the session until the selected test's report and memory checkpoint are complete.

## Troubleshooting

### Agent not found

Restart OpenCode after creating or changing `.opencode/agents/mud-evaluator.md`, then launch from the `001_playing_agent` directory:

```bash
opencode --agent mud-evaluator
```

### Model or provider not found

Run from the repository worktree so OpenCode loads `opencode.json` and the root `.env`:

```bash
opencode models ollama
```

Verify that `OLLAMA_HOST` points to the Ollama API host without adding `/v1`; `opencode.json` adds that suffix.

### Connection refused on port 4000

Run:

```bash
data/code/mud-server.sh ensure
```

If startup fails, inspect:

```bash
data/code/mud-server.sh logs
```

### Missing MUD credentials

Add `MUD_USERNAME` and `MUD_PASSWORD` to the ignored repository-root `.env`. Never pass the password on the command line.

### Stale or failed login session

Inspect before retrying:

```bash
data/code/mud-login.sh status
data/code/mud-login.sh capture
```

Close only the managed session when recovery requires a fresh socket:

```bash
data/code/mud-login.sh stop
```

Then run `start` once. Do not create repeated parallel connections.

### Run stops near 20K tokens before completing the objective

Do not assume this means the evaluator has a 20,000-token or 20-step limit. The `mud-evaluator` agent does not currently define a step limit. OpenCode continues an agent loop while the model requests tools; it stops when the provider returns a normal completion without another tool call.

One observed Qwen 3.6 run ended with these session values:

```text
Last request input:       19,726 tokens
Last generated output:     1,024 tokens
Provider finish reason:     stop
Compaction performed:       no
Agent step limit:            none
```

The final response said it was about to send another movement command, but it did not contain a tool call. Most of its response allowance had been consumed by reasoning, and the response ended at exactly 1,024 generated tokens. Because the Ollama-compatible endpoint reported `stop` instead of a length error, OpenCode treated that incomplete response as the end of the agent turn.

The roughly 20K figure shown for the last turn was the current request/context size, not all work performed during the session. OpenCode resends the growing conversation on successive model calls. In the observed run, 14 assistant turns accumulated 231,055 input tokens even though the largest individual request contained 19,726 tokens.

This failure therefore has three distinct parts:

1. The custom model configuration does not declare its context and output limits.
2. The final Qwen response reached an apparent 1,024-token response ceiling before producing its next tool call.
3. The provider labeled the result as a normal stop, so OpenCode had no error that would cause it to recover or compact.

This is different from a true context-window failure. A true context failure normally ends at the server's complete context boundary and may report a finish reason such as `length`. Increasing only the output limit will not fix that case; the Ollama runtime context and OpenCode's configured context must agree.

#### Declare the model limits

For custom providers, OpenCode recommends declaring each model's `limit.context` and `limit.output`. Add limits to the Qwen model entry in `opencode.json`:

```json
"qwen3.6:35b-a3b": {
  "name": "Qwen 3.6 35B",
  "limit": {
    "context": 32768,
    "output": 8192
  }
}
```

The `32768` value is an example, not a guaranteed value for this server. Set it to the context window actually configured on the machine running Ollama. OpenCode metadata cannot enlarge the Ollama runtime context. If the server uses `OLLAMA_CONTEXT_LENGTH` or a model/runtime `num_ctx` value, keep those settings aligned with `limit.context`.

An `8192` output allowance gives a reasoning model substantially more room to reach its next tool call and checkpoint. It does not mean every response should be that long; the evaluator should still checkpoint early and keep narration brief.

#### Configure compaction

Add a top-level compaction block alongside `provider` and `model` in `opencode.json`:

```json
"compaction": {
  "auto": true,
  "prune": true,
  "reserved": 8192
}
```

Automatic compaction lets OpenCode summarize an expanding session before it exhausts the declared context. Pruning removes older tool output that is no longer useful, and the reserved space leaves room for the next model response. Compaction helps long sessions, but it does not replace the required memory and report checkpoints.

After changing model limits, restart OpenCode so the provider configuration is reloaded. Resume from the saved report with:

```text
retry
```

Before trusting the retry, confirm that the evaluator selects the intended Test 2–4 OpenCode report. A file such as `completion-report/test1-in-progress.md` is not one of the report paths used by `mud-evaluator` and indicates that the run did not follow the evaluator's OpenCode-specific test-selection protocol.

For deeper diagnosis, inspect the session's final input count, output count, finish reason, and whether compaction occurred. A response that ends exactly at the configured output allowance but reports `stop` should be treated as a likely provider/model cutoff, especially when its final text promises an action but contains no tool call.

## Verify Files Before Committing

The `.env`, OpenCode dependency cache, and other generated directories should remain ignored. Before committing the configuration or guide, inspect:

```bash
git status --short --ignored
git diff --check
git diff --cached --name-only
```

Commit only the intended agent, skills, tools, configuration, and documentation—not credentials or generated dependency folders.

## OpenCode References

- <https://opencode.ai/docs/agents>
- <https://opencode.ai/docs/config/>
- <https://opencode.ai/docs/providers/>
- <https://opencode.ai/docs/rules>
- <https://opencode.ai/docs/skills>
- <https://opencode.ai/docs/cli>
