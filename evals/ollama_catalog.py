"""Runtime Ollama model discovery and tool-loop probing for eval runners.

The caller supplies the host resolved from configuration/environment. This
module never knows the private server name and deliberately omits URLs from its
errors/results so eval artifacts cannot leak OLLAMA_HOST.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable


class OllamaCatalogError(Exception):
    """A sanitized discovery/probe error that never includes the host URL."""


@dataclass(frozen=True)
class OllamaModel:
    name: str
    digest: str
    size: int
    parameter_size: str | None
    quantization: str | None
    capabilities: tuple[str, ...]

    @property
    def supports_completion(self) -> bool:
        return "completion" in self.capabilities

    @property
    def supports_tools(self) -> bool:
        return "tools" in self.capabilities


@dataclass(frozen=True)
class ToolProbeResult:
    model: str
    passed: bool
    status: str
    detail: str
    duration_s: float


RequestJSON = Callable[[str, dict | None, float], dict]


def _request_json(host: str) -> RequestJSON:
    base = str(host).rstrip("/")

    def request(path: str, payload: dict | None, timeout: float) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            base + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            response_body = e.read().decode("utf-8", errors="replace")
            raise OllamaCatalogError(f"Ollama returned HTTP {e.code}: {response_body[:500]}") from e
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            raise OllamaCatalogError(f"Ollama request failed: {type(e).__name__}") from e

    return request


def discover_models(
    host: str,
    *,
    timeout: float = 15,
    request_json: RequestJSON | None = None,
) -> list[OllamaModel]:
    """Return the server's installed models plus /api/show capabilities."""
    request = request_json or _request_json(host)
    tags = request("/api/tags", None, timeout)
    items = list(tags.get("models") or [])

    def inspect(item: dict) -> OllamaModel | None:
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name:
            return None
        shown = request("/api/show", {"model": name, "verbose": False}, timeout)
        details = item.get("details") or shown.get("details") or {}
        return OllamaModel(
            name=name,
            digest=str(item.get("digest") or ""),
            size=int(item.get("size") or 0),
            parameter_size=details.get("parameter_size"),
            quantization=details.get("quantization_level"),
            capabilities=tuple(str(v) for v in (shown.get("capabilities") or [])),
        )

    # /api/show is metadata-only. Inspect a modest number concurrently so a
    # large remote catalog does not pay one network round trip per tag in
    # series; executor.map preserves /api/tags order for readable output.
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(items)))) as executor:
        inspected = executor.map(inspect, items)
        return [model for model in inspected if model is not None]


def select_models(
    models: list[OllamaModel],
    *,
    tools_only: bool,
    include_aliases: bool = False,
) -> list[OllamaModel]:
    """Select completion models and, by default, one tag per model digest."""
    selected = [
        model
        for model in models
        if model.supports_completion and (model.supports_tools or not tools_only)
    ]
    if include_aliases:
        return selected

    seen = set()
    unique = []
    for model in selected:
        # Empty digests should not collapse unrelated malformed catalog rows.
        key = ("digest", model.digest) if model.digest else ("name", model.name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(model)
    return unique


def probe_tool_loop(
    host: str,
    model: str,
    *,
    timeout: float = 120,
    request_json: RequestJSON | None = None,
) -> ToolProbeResult:
    """Test both tool emission and the follow-up after a tool result.

    This intentionally mirrors Boukensha's Ollama message shape, including
    ``tool_name`` on the result and ``think: false``. A model that passes can
    complete a minimal two-request tool loop; it is not guaranteed to solve a
    MUD task, but failures here are cheaper and easier to classify than a full
    trial.
    """
    request = request_json or _request_json(host)
    started = time.monotonic()
    tool = {
        "type": "function",
        "function": {
            "name": "boukensha_probe",
            "description": "Return a caller-provided probe value.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
        },
    }
    messages = [
        {
            "role": "user",
            "content": (
                "Call boukensha_probe exactly once with value "
                "'boukensha-probe'. Do not answer in prose before calling it."
            ),
        }
    ]
    common = {
        "model": model,
        "stream": False,
        "think": False,
        "tools": [tool],
        "options": {"num_ctx": 4096, "num_predict": 128, "temperature": 0},
    }

    try:
        first = request("/api/chat", {**common, "messages": messages}, timeout)
        assistant = first.get("message") or {}
        calls = assistant.get("tool_calls") or []
        if not calls:
            return _probe_result(model, started, False, "no_tool_call", "returned no tool call")
        if len(calls) != 1:
            return _probe_result(model, started, False, "multiple_tool_calls", f"returned {len(calls)} calls")

        fn = calls[0].get("function") or {}
        if fn.get("name") != "boukensha_probe":
            return _probe_result(model, started, False, "wrong_tool", f"called {fn.get('name')!r}")
        arguments = fn.get("arguments") or {}
        if arguments.get("value") != "boukensha-probe":
            return _probe_result(model, started, False, "bad_arguments", f"arguments={arguments!r}")

        messages.extend(
            [
                assistant,
                {"role": "tool", "tool_name": "boukensha_probe", "content": "probe-ok"},
                {
                    "role": "user",
                    "content": "The tool completed. Reply with the exact text probe-complete and call no more tools.",
                },
            ]
        )
        second = request("/api/chat", {**common, "messages": messages}, timeout)
        followup = second.get("message") or {}
        if followup.get("tool_calls"):
            return _probe_result(model, started, False, "tool_loop", "called a tool again after its result")
        content = str(followup.get("content") or "").strip()
        if "probe-complete" not in content.lower():
            return _probe_result(model, started, False, "no_final_completion", f"final={content[:160]!r}")
        return _probe_result(model, started, True, "passed", "valid call and post-tool completion")
    except OllamaCatalogError as e:
        return _probe_result(model, started, False, "api_error", str(e))


def _probe_result(
    model: str,
    started: float,
    passed: bool,
    status: str,
    detail: str,
) -> ToolProbeResult:
    return ToolProbeResult(
        model=model,
        passed=passed,
        status=status,
        detail=detail,
        duration_s=time.monotonic() - started,
    )
