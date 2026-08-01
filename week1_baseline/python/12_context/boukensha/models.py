"""Static model → capability table.

context_window is a known *model* fact — the physical input ceiling — not a
value the user sets. The agent looks it up from its configured model id; the
user never configures it in settings.yaml. Unknown models fall back to a
conservative default so an unrecognised id can't silently assume a huge
window."""

from __future__ import annotations

TABLE = {
    "claude-opus-4-8": {"context_window": 200_000},
    "claude-sonnet-4-6": {"context_window": 200_000},
    "claude-haiku-4-5": {"context_window": 200_000},
    # Local-testing additions (not in the Ruby reference, which is
    # Anthropic-only here) — without an entry, context_window() falls back
    # to DEFAULT_CONTEXT_WINDOW (32_000), which would make compaction fire
    # almost immediately against a real 256k-context local model.
    "qwen3.6:27b": {"context_window": 256_000},
    "qwen3.6:35b-a3b": {"context_window": 256_000},
    "qwen3.5:4b": {"context_window": 128_000},
}

DEFAULT_CONTEXT_WINDOW = 32_000


def context_window(model: str) -> int:
    entry = TABLE.get(str(model))
    return entry["context_window"] if entry else DEFAULT_CONTEXT_WINDOW
