# Preweek Journal

During preweek, I explored the tbaMUD environment, ran local agents with Ollama, and compared several models on a stateful gameplay task.

## Journal Entries

- [Dummy's Midgaard Sewer Expedition](0_preweek/exploration.md) — the accidental sewer crawl, maps, final statistics, and gameplay lessons
- [Local Ollama and Pi Setup](0_preweek/ollama-pi-setup.md) — reproducible Ollama, model, and Pi configuration
- [Agent Progress Comparison](0_preweek/agent-results.md) — outcomes from Codex 5.6 Sol, Qwen 3.5, Qwen3-Coder:30B, and Qwen 3.6

## Highlights

- Manually mapped a large section of Midgaard's sewer system.
- Advanced Dummy from level 2 to level 3 before completing the original tutorial objective.
- Configured Pi to use models running locally via Ollama.
- Compared four agent or model configurations on the same MUD bakery task.
- Codex 5.6 Sol and Qwen 3.6 completed the task using persistent terminal sessions.
- Qwen 3.6 created a reusable `tmux` command bridge under `data/code`.

## Main Lesson

The model was only one part of the agent architecture. Stateful environments such as MUDs also require a reliable connection layer that preserves the same session between tool calls. The successful attempts used either a persistent PTY or a `tmux` bridge instead of sending the complete login sequence through a short-lived shell pipeline.
