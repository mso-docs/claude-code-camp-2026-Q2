from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from . import state

DEFAULT_SESSION_DIR = "sessions"


class Logger:
    """Records each agent run as structured JSON Lines — a file logger, not
    display output. One .jsonl file per session under .boukensha/sessions/."""

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

    def iteration(self, *, n: int, max: int) -> None:
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, *, kind: str, n: int, max: int) -> None:
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, *, reason: str, iterations: int, tokens: int | None = None) -> None:
        self._write_log({"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens})

    def prompt(self, *, messages, tools) -> None:
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
            }
        )

    def tool_call(self, *, name: str, args: dict) -> None:
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, *, name: str, result, ok: bool = True, error: str | None = None) -> None:
        self._write_log({"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error})

    def response(self, *, text, usage=None, stop_reason=None, task=None, backend=None) -> None:
        event = {
            "phase": "response",
            "text": (text or "").strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(self._execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, *, data) -> None:
        if not state.is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def close(self) -> None:
        if self._log_io:
            self._log_io.close()

    # ---------- private -----------------------------------------------

    def _default_dir(self) -> Path:
        return Path(state.config().dir) / DEFAULT_SESSION_DIR

    def _write_log(self, event: dict) -> None:
        full_event = {
            **event,
            "session_id": self.session_id,
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self._log_io.write(json.dumps(full_event) + "\n")
        self._log_io.flush()

    @staticmethod
    def _generate_session_id() -> str:
        return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"

    @staticmethod
    def _serialize_message(msg) -> dict:
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(self, *, task, backend, usage) -> dict:
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": getattr(backend, "model", None) if backend else None,
            "usage_unit": getattr(backend, "usage_unit", None) if backend else None,
            "usage_level": getattr(backend, "usage_level", None) if backend else None,
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _task_name(task) -> str | None:
        if task is None:
            return None
        return getattr(task, "task_name", None) or str(task)

    @staticmethod
    def _provider_name(backend) -> str | None:
        if backend is None:
            return None
        name = type(backend).__name__
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()

    def _usage_tokens(self, usage) -> dict:
        usage = usage or {}
        return {
            "input": self._first_integer(usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"),
            "output": self._first_integer(usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"),
        }

    @staticmethod
    def _first_integer(d: dict, *keys: str) -> int | None:
        for key in keys:
            value = d.get(key)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
        return None

    @staticmethod
    def _estimate_cost(backend, tokens: dict):
        if backend is None or not hasattr(backend, "estimate_cost"):
            return None
        if tokens["input"] is None or tokens["output"] is None:
            return None
        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
