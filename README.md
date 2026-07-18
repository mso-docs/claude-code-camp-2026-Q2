# Claude Code Camp

This is my repository for the [Claude Code Camp operated by ExamPro](https://www.exampro.co).

## Preweek: Exploring Agent Architecture

My preweek project uses a local tbaMUD game as a test environment for stateful AI agents. I began by exploring the game manually, then compared several coding agents on the same navigation task, and finally converted the most successful interaction patterns into reusable Agent Skills.

Start with the [Preweek Journal](docs/journal/0_preweek.md) for the complete overview, or read [Exploring Agent Architecture](docs/exploring-architecture.md) for the architectural conclusions.

### What I explored

- Ran local models through Ollama with Pi as the coding-agent harness.
- Compared Codex 5.6 Sol, Qwen 3.5, Qwen3-Coder:30B, and Qwen 3.6 on the same MUD bakery task.
- Tested persistent PTY and `tmux` approaches for controlling a long-running interactive connection.
- Added player and world memory so agents could preserve discoveries between tool calls and tests.
- Generated initial Agent Skills with Ollama's `cmdmbox/skill-expert` model and refined them with task-specific workflows and guardrails.
- Extended the evaluation into combat, guild navigation, and a longer Newbie Training objective.

### Results

| Agent or model | Outcome |
| --- | --- |
| Codex 5.6 Sol | Completed the bakery task using a persistent PTY. |
| Qwen 3.5 | Did not complete the interactive login through short-lived shell pipelines. |
| Qwen3-Coder:30B | Encountered tool-call problems before completing the task. |
| Qwen 3.6 | Completed the bakery task using a `tmux` bridge and later passed the combat and guild-location tests. Its longer Test 4 remains incomplete. |

The main finding was that model capability alone did not determine success. A MUD requires a persistent, timing-sensitive connection, while coding-agent shell tools are usually designed around discrete commands. Agent Skills and frequent memory checkpoints improved the workflow, but Qwen 3.6's later login regression showed that the approach was still not consistently reliable. A dedicated MUD client, SDK, custom tool, or MCP server would provide a stronger foundation.

## Repository Guide

- [Preweek journal](docs/journal/0_preweek.md) — summary of the full preweek project and its lessons
- [Manual exploration](docs/journal/0_preweek/exploration.md) — Dummy's Midgaard sewer expedition, maps, and gameplay discoveries
- [Ollama and Pi setup](docs/journal/0_preweek/ollama-pi-setup.md) — local model, coding harness, and Agent Skill setup
- [OpenCode MUD guide](docs/opencode-mud-guide.md) — configure OpenCode, start the MUD evaluator, and run checkpointed tests
- [Agent results](docs/journal/0_preweek/agent-results.md) — comparison of the initial bakery-task attempts
- [`001_playing_agent`](week0_explore/explore_architecture/001_playing_agent) — agent instructions, prompts, state files, helper code, and completion reports
- [`002_agent_skills`](week0_explore/explore_architecture/002_agent_skills) — Agent Skills architecture, reusable skills, and extended Qwen 3.6 test reports
- [Current challenge](week0_explore/CHALLENGES.md) — level up and defeat the Massive Minotaur in the Newbie Zone

## Current Status

The bakery, combat-practice, and starting-guild objectives produced successful results. The longer Test 4 is preserved as an in-progress experiment: the agent explored additional parts of Midgaard but did not locate the Newbie Training area or defeat the Massive Minotaur.
