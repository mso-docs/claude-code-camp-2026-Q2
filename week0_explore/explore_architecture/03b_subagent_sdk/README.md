# Claude Agent SDK Two-Player MUD

This folder mirrors `03_subagent_sdk`, but its two subagents are Python
`AgentDefinition` values in `scripts/run_agent.py`. No
`.claude/agents/*.md` or OpenCode agent file is used.

The Python coordinator runs the primary player and Smarty concurrently with
`asyncio.gather`. Each inline definition gets a separate foreground SDK
process, preventing one Claude CLI transport from closing while the other
player is still working. Their network sessions, credentials, player files,
and checkpoints are isolated; confirmed world and command knowledge is shared.

The active challenge requires both sessions to participate while Smarty
live-confirms and records age, gender, class, and current stats.

The existing Smarty player file and the git-ignored local credential profile
are ready. Configure the primary credentials described in `PLAN.md`, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/run_agent.py --check
python3 scripts/test-mud-login.py
python3 scripts/run_agent.py start
```

If the SDK reports `Not logged in`, authenticate Claude Code inside this WSL
environment (a Windows-side login is separate):

```bash
claude
# At the interactive prompt, enter: /login
```

Alternatively, configure an Anthropic API key as `ANTHROPIC_API_KEY` in the
repository-root git-ignored `.env`.

The Claude Agent SDK only supports Claude models for these `AgentDefinition`
subagents. A Qwen-backed version would use the OpenCode SDK architecture from
`03_subagent_sdk` instead.
