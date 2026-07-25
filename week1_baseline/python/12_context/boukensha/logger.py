from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from . import state

DEFAULT_SESSION_DIR = "sessions"

# Session logs get committed (per course requirements), so secret- and
# infra-shaped content must never reach disk regardless of which tool
# produced it — read_file refusing .env is the first line of defense, this
# is the second for anything else that slips through a tool result
# (run_command cat'ing a dotfile, an `env` dump, etc). Covers both true
# secrets (API keys, passwords, tokens) and identifying infra details
# (internal hostnames/URLs, e.g. a private OLLAMA_HOST) that shouldn't end
# up in a repo shared with an instructor/classmates even though they aren't
# credentials per se.
_SECRET_KV_RE = re.compile(
    r"(?im)\b((?:[A-Z0-9]+_)*(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD"
    r"|HOST|URL|URI|ENDPOINT|DSN)(?:_[A-Z0-9]+)*)(\s*[:=]\s*)(\S+)"
)
_SECRET_LITERAL_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{6,}\b")


def _redact(value):
    if isinstance(value, str):
        value = _SECRET_KV_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", value)
        value = _SECRET_LITERAL_RE.sub("[REDACTED]", value)
        return value
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class Logger:
    """Records each agent run as structured JSON Lines — a file logger, not
    display output. One .jsonl file per session under .boukensha/sessions/.

    Cost/task/provider tracking (execution_metadata and everything that fed
    it — task_name, provider_name, usage_tokens, first_integer, estimate_cost)
    is removed in this step, not simplified — response() no longer takes
    task=/backend= at all. This also deletes the OpenAI provider_name
    quirk's (step 06) only call site."""

    def __init__(
        self,
        *,
        session_id: str | None = None,
        dir: str | Path | None = None,
        log: str | Path | None = None,
        snapshot: dict | None = None,
    ) -> None:
        self.session_id = session_id or self._generate_session_id()
        self.path = Path(log) if log else Path(dir or self._default_dir()) / f"{self.session_id}.jsonl"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._log_io = open(self.path, "a")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def turn(self, *, n: int) -> None:
        self._write_log({"phase": "turn", "n": n})

    def iteration(self, *, n: int, max: int) -> None:
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, *, kind: str, n: int, max: int) -> None:
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, *, reason: str, iterations: int, tokens: int | None = None) -> None:
        self._write_log({"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens})

    def prompt(self, *, messages, tools, context_window: int) -> None:
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
                "context_window": context_window,
            }
        )

    def compaction(self, *, before: int, dropped: int, context_window: int) -> None:
        self._write_log({"phase": "compaction", "before": before, "dropped": dropped, "context_window": context_window})

    def tool_call(self, *, name: str, args: dict) -> None:
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, *, name: str, result, ok: bool = True, error: str | None = None) -> None:
        self._write_log({"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error})

    def response(self, *, text, usage=None, stop_reason=None) -> None:
        self._write_log({"phase": "response", "text": (text or "").strip(), "usage": usage, "stop_reason": stop_reason})

    def reasoning(self, *, text, redacted: bool = False) -> None:
        self._write_log({"phase": "reasoning", "text": str(text or ""), "redacted": redacted})

    def plan(self, *, text) -> None:
        self._write_log({"phase": "plan", "text": (text or "").strip()})

    def raw(self, *, data) -> None:
        if not state.is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def subscribe(self, callback) -> None:
        self._subscribers = getattr(self, "_subscribers", [])
        self._subscribers.append(callback)

    def close(self) -> None:
        if self._log_io:
            self._log_io.close()

    # ---------- private -----------------------------------------------

    def _default_dir(self) -> Path:
        return Path(state.config().dir) / DEFAULT_SESSION_DIR

    def _write_log(self, event: dict) -> None:
        # Redact before this event is ever written to disk or handed to a
        # subscriber (Tui) — a session log gets committed, and a live
        # display is still a leak. See _redact for what this catches.
        event = _redact(event)

        # `event` itself is deliberately left un-merged below — subscribers
        # get the original per-phase dict, not session_id/at added on top.
        full_event = {
            **event,
            "session_id": self.session_id,
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self._log_io.write(json.dumps(full_event) + "\n")
        self._log_io.flush()
        for callback in getattr(self, "_subscribers", None) or []:
            callback(event)

    @staticmethod
    def _generate_session_id() -> str:
        return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"

    @staticmethod
    def _serialize_message(msg) -> dict:
        return {"role": msg.role, "content": msg.content}
