#!/usr/bin/env python3
"""HTTP bridge exposing mud.sh actions so n8n (Code Tool / HTTP Request Tool
nodes on an AI Agent) can drive the persistent tmux-backed CircleMUD session.

n8n's Python (beta) Code node runs in a sandboxed interpreter with no
subprocess, no tmux, and no local filesystem access, so mud.py's
Claude-Agent-SDK tools (which shell out to mud.sh and read/write markdown
memory files) cannot run inside n8n directly. This service keeps that logic
on the host, next to the real tmux session and Docker Compose MUD server, and
exposes it as plain HTTP so n8n only ever needs to make a request.

The AI Agent node's own "Simple Memory" covers conversational turns; the
/memory and /checkpoint endpoints here are for durable game state (quest
progress, player facts, world facts) that must survive across separate
agent runs, which conversational memory does not.

Run (from this directory, using the existing 03b_subagent_sdk venv):
    ../03b_subagent_sdk/.venv/bin/python -m pip install fastapi uvicorn
    ../03b_subagent_sdk/.venv/bin/uvicorn mud_bridge:app --host 0.0.0.0 --port 8787

Every endpoint is namespaced by character profile: "mud" (primary) or
"smarty". Example: POST /mud/send  {"command": "look"}
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

PROJECT_DIR = Path(
    os.environ.get("MUD_PROJECT_DIR", Path(__file__).resolve().parent.parent / "03b_subagent_sdk")
).resolve()
MUD_EXECUTABLE = PROJECT_DIR / ".ollama/.agents/tools/mud.sh"
COMMAND_LIMIT = 4
BRIDGE_TOKEN = os.environ.get("MUD_BRIDGE_TOKEN")  # optional shared secret


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


PROFILES: dict[str, MudProfile] = {
    "mud": MudProfile(
        server_name="mud",
        username_variable="MUD_USERNAME",
        password_variable="MUD_PASSWORD",
        tmux_session="subagent-sdk-03b-primary",
        player_file="data/player.md",
        session_file="data/session.md",
        checkpoints_file="data/checkpoints.md",
    ),
    "smarty": MudProfile(
        server_name="smarty",
        username_variable="MUD_SMARTY_USERNAME",
        password_variable="MUD_SMARTY_PASSWORD",
        tmux_session="subagent-sdk-03b-smarty",
        player_file="data/smarty/player.md",
        session_file="data/smarty/session.md",
        checkpoints_file="data/smarty/checkpoints.md",
    ),
}


def get_profile(name: str) -> MudProfile:
    try:
        return PROFILES[name]
    except KeyError:
        raise HTTPException(404, f"Unknown profile '{name}'; use 'mud' or 'smarty'.") from None


def require_project() -> None:
    missing = [str(p) for p in (PROJECT_DIR / "QUEST.md", MUD_EXECUTABLE) if not p.exists()]
    if missing:
        raise HTTPException(500, f"03b_subagent_sdk is incomplete; missing: {', '.join(missing)}")


def profile_environment(profile: MudProfile) -> dict[str, str]:
    username = os.getenv(profile.username_variable)
    password = os.getenv(profile.password_variable)
    if not username or not password:
        raise HTTPException(
            500,
            f"Set {profile.username_variable} and {profile.password_variable} "
            "in the environment the bridge process runs under.",
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


async def run_mud(profile: MudProfile, action: str, command: str | None = None) -> str:
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
        raise HTTPException(504, f"{profile.server_name} {action} exceeded {timeout}s") from None

    output = b"\n".join(p for p in (stdout, stderr) if p).decode("utf-8", errors="replace").strip()
    if process.returncode:
        raise HTTPException(502, output or f"{profile.server_name} {action} exited with {process.returncode}")
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
            f"===== {relative} =====\n{(PROJECT_DIR / relative).read_text(encoding='utf-8').strip()}"
            for relative in files
        )

    return await asyncio.to_thread(read_all)


class CheckpointBody(BaseModel):
    status: str
    room: str
    summary: str
    player_changes: str
    world_changes: str
    next_action: str


async def persist_checkpoint(profile: MudProfile, body: CheckpointBody) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    session = (
        "# MUD Session Handoff\n\n"
        f"- Character profile: {profile.server_name}\n"
        f"- Updated: {timestamp}\n"
        f"- Objective status: {body.status}\n"
        f"- Last verified room: {body.room}\n"
        "- Commands since checkpoint: 0\n"
        f"- Last result: {body.summary}\n"
        f"- Player changes: {body.player_changes}\n"
        f"- World changes: {body.world_changes}\n"
        f"- Next action: {body.next_action}\n"
    )
    history = (
        f"\n## {timestamp}\n\n"
        f"- Status: {body.status}\n"
        f"- Room: {body.room}\n"
        f"- Result: {body.summary}\n"
        f"- Player changes: {body.player_changes}\n"
        f"- World changes: {body.world_changes}\n"
        f"- Next action: {body.next_action}\n"
    )

    def persist() -> None:
        (PROJECT_DIR / profile.session_file).write_text(session, encoding="utf-8")
        with (PROJECT_DIR / profile.checkpoints_file).open("a", encoding="utf-8") as stream:
            stream.write(history)

    await asyncio.to_thread(persist)
    profile.commands_since_checkpoint = 0
    return (
        f"{profile.server_name} checkpoint persisted. Merge confirmed character "
        f"facts into {profile.player_file} and shared facts into data/world.md."
    )


class SendBody(BaseModel):
    command: str


def check_auth(x_bridge_token: str | None) -> None:
    if BRIDGE_TOKEN and x_bridge_token != BRIDGE_TOKEN:
        raise HTTPException(401, "Missing or invalid X-Bridge-Token header.")


app = FastAPI(title="mud-bridge", version="1.0.0")


@app.get("/{profile_name}/doctor")
async def doctor(profile_name: str, x_bridge_token: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(x_bridge_token)
    profile = get_profile(profile_name)
    return {"output": await run_mud(profile, "doctor")}


@app.post("/{profile_name}/start")
async def start(profile_name: str, x_bridge_token: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(x_bridge_token)
    profile = get_profile(profile_name)
    output = await run_mud(profile, "start")
    profile.commands_since_checkpoint = 0
    return {"output": output}


@app.get("/{profile_name}/status")
async def status(profile_name: str, x_bridge_token: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(x_bridge_token)
    profile = get_profile(profile_name)
    return {"output": await run_mud(profile, "status")}


@app.get("/{profile_name}/capture")
async def capture(profile_name: str, x_bridge_token: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(x_bridge_token)
    profile = get_profile(profile_name)
    return {"output": await run_mud(profile, "capture")}


@app.post("/{profile_name}/send")
async def send(
    profile_name: str, body: SendBody, x_bridge_token: str | None = Header(default=None)
) -> dict[str, Any]:
    check_auth(x_bridge_token)
    profile = get_profile(profile_name)
    command = body.command.strip()
    if not command or "\n" in command or "\r" in command:
        raise HTTPException(400, "send requires one non-empty command line")
    if profile.commands_since_checkpoint >= COMMAND_LIMIT:
        raise HTTPException(409, "Checkpoint required before another command.")
    output = await run_mud(profile, "send", command)
    profile.commands_since_checkpoint += 1
    return {
        "output": output,
        "commands_since_checkpoint": profile.commands_since_checkpoint,
        "command_limit": COMMAND_LIMIT,
    }


@app.get("/{profile_name}/memory")
async def memory(profile_name: str, x_bridge_token: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(x_bridge_token)
    profile = get_profile(profile_name)
    return {"output": await load_memory(profile)}


@app.post("/{profile_name}/checkpoint")
async def checkpoint(
    profile_name: str, body: CheckpointBody, x_bridge_token: str | None = Header(default=None)
) -> dict[str, Any]:
    check_auth(x_bridge_token)
    profile = get_profile(profile_name)
    if body.status not in {"in_progress", "blocked", "complete"}:
        raise HTTPException(400, "status must be one of: in_progress, blocked, complete")
    return {"output": await persist_checkpoint(profile, body)}
