#!/usr/bin/env python3
"""Run two programmatically defined Claude SDK MUD subagents."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from dotenv import load_dotenv

from mud import mud_server, smarty_server


PROJECT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = next(
    (parent for parent in PROJECT_DIR.parents if (parent / ".git").exists()),
    PROJECT_DIR,
)
load_dotenv(REPO_ROOT / ".env")
load_dotenv(PROJECT_DIR / ".env", override=True)

PRIMARY_TOOLS = [
    "mcp__mud__doctor",
    "mcp__mud__start",
    "mcp__mud__status",
    "mcp__mud__capture",
    "mcp__mud__send",
    "mcp__mud__memory",
    "mcp__mud__checkpoint",
]
SMARTY_TOOLS = [
    "mcp__smarty__doctor",
    "mcp__smarty__start",
    "mcp__smarty__status",
    "mcp__smarty__capture",
    "mcp__smarty__send",
    "mcp__smarty__memory",
    "mcp__smarty__checkpoint",
]

PLAYER_RULES = """
You are an execution subagent playing exactly one CircleMUD character. Execute
the assigned objective; do not merely explain commands.

At startup call your memory tool, doctor tool, and start tool in that order.
Call start exactly once and require MUD_LOGIN_OK plus recognizable room output.
Your MCP tools are the only permitted login, server, session, and gameplay
path. Never create another telnet, socket, tmux, expect, login, or server
script, and never type credentials or login/menu responses yourself.

Send exactly one game command at a time and inspect all returned output.
Checkpoint after important discoveries, movements or state changes, purchases,
training, combat, milestones, and always before exceeding four commands.
Maintain your character-specific player file and the shared data/world.md.
Only add commands to data/commands.md after live evidence proves them.

Prefer observation before risky actions. Confirm movement from room output.
Stop immediately on death. Coordinate with the other character through the
objective and confirmed shared world state; do not operate the other
character's tools. Before claiming completion, live-confirm it, send one final
save, verify success, checkpoint, and read back changed memory.
""".strip()

PRIMARY_AGENT = AgentDefinition(
    description="Play the primary MUD character and cooperate with Smarty.",
    prompt=(
        PLAYER_RULES
        + "\n\nYou control only the primary character through mcp__mud__*. "
        "Your player file is data/player.md. Remain active while Smarty gathers "
        "character information, and complete at least one confirmed gameplay "
        "action while both sessions are live."
    ),
    tools=[*PRIMARY_TOOLS, "Read", "Edit"],
    model="sonnet",
    background=False,
)

SMARTY_AGENT = AgentDefinition(
    description="Play the Smarty MUD character and cooperate with the primary player.",
    prompt=(
        PLAYER_RULES
        + "\n\nYou are Smarty and control only that character through "
        "mcp__smarty__*. Your player file is data/smarty/player.md. Obtain live "
        "evidence for your age, gender, class, and every displayed stat. Record "
        "exact values and explicitly mark anything the server does not reveal."
    ),
    tools=[*SMARTY_TOOLS, "Read", "Edit"],
    model="sonnet",
    background=False,
)


def build_player_options(
    agent: AgentDefinition, server_name: str, server: object
) -> ClaudeAgentOptions:
    """Convert an inline AgentDefinition into one foreground SDK process."""
    return ClaudeAgentOptions(
        cwd=str(PROJECT_DIR),
        model=os.getenv("CLAUDE_MODEL", agent.model or "sonnet"),
        system_prompt=agent.prompt,
        mcp_servers={server_name: server},
        allowed_tools=agent.tools or [],
        permission_mode="acceptEdits",
        max_turns=100,
    )


async def run_player(
    name: str,
    agent: AgentDefinition,
    server_name: str,
    server: object,
    prompt: str,
) -> tuple[str, list[str], str | None]:
    """Run one player to completion on its own foreground CLI transport."""
    output: list[str] = []
    error: str | None = None
    try:
        async for message in query(
            prompt=prompt,
            options=build_player_options(agent, server_name, server),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        output.append(block.text)
                        print(f"[{name}] {block.text}", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"[{name}] -> {block.name}({block.input})", flush=True)
            elif isinstance(message, UserMessage) and isinstance(message.content, list):
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        status = "error" if block.is_error else "ok"
                        print(f"[{name}] <- {status}: {block.content}", flush=True)
            elif isinstance(message, ResultMessage) and message.is_error:
                error = str(message.result or message.subtype)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return name, output, error


async def run(prompt: str) -> int:
    # Python owns concurrency and waits for both foreground CLI transports.
    results = await asyncio.gather(
        run_player(
            "play-mud",
            PRIMARY_AGENT,
            "mud",
            mud_server,
            f"Team request: {prompt}\nPlay your primary-character role now.",
        ),
        run_player(
            "smarty",
            SMARTY_AGENT,
            "smarty",
            smarty_server,
            f"Team request: {prompt}\nPlay Smarty's role and gather the required live facts now.",
        ),
    )

    failed = False
    for name, messages, error in results:
        print(f"\n=== {name} ===")
        if messages:
            print("\n".join(messages))
        if error:
            print(f"Agent SDK error: {error}")
            failed = True
        elif not messages:
            print("Agent returned no text.")
            failed = True
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the two-player MUD team.")
    parser.add_argument("prompt", nargs="*", help="start, status, continue, quit, or an objective")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate configuration without calling a model",
    )
    args = parser.parse_args()

    required = [PROJECT_DIR / "QUEST.md", PROJECT_DIR / ".ollama/.agents/tools/mud.sh"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        parser.error(f"missing required files: {', '.join(missing)}")
    if args.check:
        definitions = {"play-mud": PRIMARY_AGENT, "smarty": SMARTY_AGENT}
        assert all(agent.background is False for agent in definitions.values())
        primary_options = build_player_options(PRIMARY_AGENT, "mud", mud_server)
        smarty_options = build_player_options(SMARTY_AGENT, "smarty", smarty_server)
        assert set(primary_options.mcp_servers) == {"mud"}
        assert set(smarty_options.mcp_servers) == {"smarty"}
        print(
            "Two inline AgentDefinitions and two supervised foreground SDK "
            "processes are configured."
        )
        return 0
    return asyncio.run(run(" ".join(args.prompt).strip() or "start"))


if __name__ == "__main__":
    raise SystemExit(main())
