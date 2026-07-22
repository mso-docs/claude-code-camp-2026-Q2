#!/usr/bin/env python3
"""In-process Claude Agent SDK tools for two isolated MUD characters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool


PROJECT_DIR = Path(__file__).resolve().parent.parent
MUD_EXECUTABLE = PROJECT_DIR / ".ollama/.agents/tools/mud.sh"
COMMAND_LIMIT = 4


@dataclass
class MudProfile:
    server_name: str
    username_variable: str
    password_variable: str
    tmux_session: str
    player_file: str
    session_file: str
    checkpoints_file: str
    commands_since_checkpoint: int = 0


PRIMARY = MudProfile(
    server_name="mud",
    username_variable="MUD_USERNAME",
    password_variable="MUD_PASSWORD",
    tmux_session="subagent-sdk-03b-primary",
    player_file="data/player.md",
    session_file="data/session.md",
    checkpoints_file="data/checkpoints.md",
)
SMARTY = MudProfile(
    server_name="smarty",
    username_variable="MUD_SMARTY_USERNAME",
    password_variable="MUD_SMARTY_PASSWORD",
    tmux_session="subagent-sdk-03b-smarty",
    player_file="data/smarty/player.md",
    session_file="data/smarty/session.md",
    checkpoints_file="data/smarty/checkpoints.md",
)


def text_result(text: str, *, error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": text.strip()}],
    }
    if error:
        result["is_error"] = True
    return result


def require_project() -> None:
    missing = [
        str(path)
        for path in (PROJECT_DIR / "QUEST.md", MUD_EXECUTABLE)
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(f"03b_subagent_sdk is incomplete; missing: {', '.join(missing)}")


def profile_environment(profile: MudProfile) -> dict[str, str]:
    username = os.getenv(profile.username_variable)
    password = os.getenv(profile.password_variable)
    if not username or not password:
        raise RuntimeError(
            f"Set {profile.username_variable} and {profile.password_variable} "
            "in the repository-root .env (values are never printed)."
        )
    environment = os.environ.copy()
    environment.update(
        {
            "MUD_LOGIN_USERNAME": username,
            "MUD_LOGIN_PASSWORD": password,
            "MUD_TMUX_SESSION": profile.tmux_session,
        }
    )
    return environment


async def run_mud(
    profile: MudProfile, action: str, command: str | None = None
) -> str:
    require_project()
    arguments = [str(MUD_EXECUTABLE), action]
    if command is not None:
        arguments.append(command)
    process = await asyncio.create_subprocess_exec(
        *arguments,
        cwd=PROJECT_DIR,
        env=profile_environment(profile),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timeout = 120 if action == "start" else 30
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(f"{profile.server_name} {action} exceeded {timeout}s") from None

    output = b"\n".join(part for part in (stdout, stderr) if part).decode(
        "utf-8", errors="replace"
    ).strip()
    if process.returncode:
        raise RuntimeError(
            output or f"{profile.server_name} {action} exited with {process.returncode}"
        )
    return output


async def load_memory(profile: MudProfile) -> str:
    shared = ("QUEST.md", "data/world.md", "data/commands.md")
    files = (
        shared[0],
        profile.session_file,
        profile.checkpoints_file,
        profile.player_file,
        shared[1],
        shared[2],
    )

    def read_all() -> str:
        return "\n\n".join(
            f"===== {relative} =====\n"
            f"{(PROJECT_DIR / relative).read_text(encoding='utf-8').strip()}"
            for relative in files
        )

    return await asyncio.to_thread(read_all)


async def persist_checkpoint(profile: MudProfile, args: dict[str, Any]) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    session = (
        "# MUD Session Handoff\n\n"
        f"- Character profile: {profile.server_name}\n"
        f"- Updated: {timestamp}\n"
        f"- Objective status: {args['status']}\n"
        f"- Last verified room: {args['room']}\n"
        "- Commands since checkpoint: 0\n"
        f"- Last result: {args['summary']}\n"
        f"- Player changes: {args['player_changes']}\n"
        f"- World changes: {args['world_changes']}\n"
        f"- Next action: {args['next_action']}\n"
    )
    history = (
        f"\n## {timestamp}\n\n"
        f"- Status: {args['status']}\n"
        f"- Room: {args['room']}\n"
        f"- Result: {args['summary']}\n"
        f"- Player changes: {args['player_changes']}\n"
        f"- World changes: {args['world_changes']}\n"
        f"- Next action: {args['next_action']}\n"
    )

    def persist() -> None:
        (PROJECT_DIR / profile.session_file).write_text(session, encoding="utf-8")
        with (PROJECT_DIR / profile.checkpoints_file).open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(history)

    await asyncio.to_thread(persist)
    profile.commands_since_checkpoint = 0
    return (
        f"{profile.server_name} checkpoint persisted. Merge confirmed character "
        f"facts into {profile.player_file} and shared facts into data/world.md."
    )


def build_mud_server(profile: MudProfile):
    @tool("doctor", f"Check tools and hidden credentials for {profile.server_name}.", {})
    async def doctor(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return text_result(await run_mud(profile, "doctor"))
        except Exception as exc:
            return text_result(str(exc), error=True)

    @tool(
        "start",
        f"Create or reuse the one authenticated {profile.server_name} session. This is the only login path.",
        {},
    )
    async def start(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            output = await run_mud(profile, "start")
            profile.commands_since_checkpoint = 0
            return text_result(output)
        except Exception as exc:
            return text_result(str(exc), error=True)

    @tool("status", f"Inspect {profile.server_name} without changing game state.", {})
    async def status(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return text_result(await run_mud(profile, "status"))
        except Exception as exc:
            return text_result(str(exc), error=True)

    @tool("capture", f"Read recent redacted output for {profile.server_name}.", {})
    async def capture(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return text_result(await run_mud(profile, "capture"))
        except Exception as exc:
            return text_result(str(exc), error=True)

    @tool(
        "send",
        f"Send one command as {profile.server_name}; checkpoint after four commands.",
        {"command": str},
    )
    async def send(args: dict[str, Any]) -> dict[str, Any]:
        command = str(args.get("command", "")).strip()
        if not command or "\n" in command or "\r" in command:
            return text_result("send requires one non-empty command line", error=True)
        if profile.commands_since_checkpoint >= COMMAND_LIMIT:
            return text_result("Checkpoint required before another command.", error=True)
        try:
            output = await run_mud(profile, "send", command)
            profile.commands_since_checkpoint += 1
            return text_result(
                f"{output}\n\nSDK_COMMAND_COUNT="
                f"{profile.commands_since_checkpoint}/{COMMAND_LIMIT}"
            )
        except Exception as exc:
            return text_result(str(exc), error=True)

    @tool("memory", f"Load quest and durable memory for {profile.server_name}.", {})
    async def memory(_args: dict[str, Any]) -> dict[str, Any]:
        try:
            return text_result(await load_memory(profile))
        except Exception as exc:
            return text_result(str(exc), error=True)

    @tool(
        "checkpoint",
        f"Persist {profile.server_name}'s resumable handoff and reset its command gate.",
        {
            "status": str,
            "room": str,
            "summary": str,
            "player_changes": str,
            "world_changes": str,
            "next_action": str,
        },
    )
    async def checkpoint(args: dict[str, Any]) -> dict[str, Any]:
        if args.get("status") not in {"in_progress", "blocked", "complete"}:
            return text_result("Invalid checkpoint status.", error=True)
        required = ("room", "summary", "player_changes", "world_changes", "next_action")
        if any(not str(args.get(key, "")).strip() for key in required):
            return text_result(
                f"checkpoint requires: {', '.join(required)}", error=True
            )
        try:
            return text_result(await persist_checkpoint(profile, args))
        except Exception as exc:
            return text_result(str(exc), error=True)

    return create_sdk_mcp_server(
        name=profile.server_name,
        version="1.0.0",
        tools=[doctor, start, status, capture, send, memory, checkpoint],
    )


mud_server = build_mud_server(PRIMARY)
smarty_server = build_mud_server(SMARTY)
