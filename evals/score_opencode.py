"""Scorer for OpenCode agent trials (run_bakery_opencode.py) — a different
log shape from boukensha's session.jsonl (see score.py), but the same output
contract: task_success/mud_connected/content_matched/output_written and
friends, so results from both agents are comparable side by side.

`opencode run --format json` streams one JSON object per line — not the same
shape as boukensha's phase-tagged entries, so this doesn't reuse score.py's
_read_log()/score_run(), only its path-redaction helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

from score import RESULTS_DIR, _relativize, _scrub_local_paths  # noqa: F401 (RESULTS_DIR re-exported for callers)

# login-mud's own success marker (see .opencode/skills/login-mud/SKILL.md and
# data/code/mud-session.py) — printed by the MUD driver itself straight into
# the tmux pane on a real successful login. This is stronger evidence than
# model narration, although it is a convention rather than a cryptographic
# guarantee because the scorer scans general Bash-tool output.
LOGIN_OK_MARKER = "MUD_LOGIN_OK"


def _read_events(log_path: Path) -> list[dict]:
    entries = []
    if not log_path.exists():
        return entries
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # truncated final line from a killed/timed-out process
    return entries


def score_run(scenario, run_result: dict) -> dict:
    """run_result is whatever run_bakery_opencode.py's _run_trial() returned."""
    log_path = Path(run_result["log_path"])
    entries = _read_events(log_path)

    tool_events = [e for e in entries if e.get("part", {}).get("type") == "tool"]
    bash_events = [e for e in tool_events if e["part"].get("tool") == "bash"]

    # A successful mud-login.sh (start or send) always echoes MUD_LOGIN_OK
    # into the captured tmux output somewhere in its lifetime. Treat that as
    # driver-produced connection evidence; it is not cryptographically
    # unforgeable because this scorer scans general Bash-tool output.
    mud_connected = any(
        LOGIN_OK_MARKER in str(e["part"].get("state", {}).get("output", ""))
        for e in bash_events
    )

    working_dir = Path(run_result["working_dir"])
    output_path = working_dir / scenario.OUTPUT_FILE
    output_text = output_path.read_text().strip() if output_path.exists() else ""

    expected_keywords = getattr(scenario, "EXPECTED_MENU_KEYWORDS", None)
    if expected_keywords:
        content_matched = any(kw.lower() in output_text.lower() for kw in expected_keywords)
    else:
        content_matched = bool(output_text)

    step_finishes = [e for e in entries if e.get("type") == "step_finish"]
    final_reason = step_finishes[-1]["part"].get("reason") if step_finishes else None
    total_tokens = sum((e["part"].get("tokens") or {}).get("total", 0) for e in step_finishes)

    result = {
        "task_success": bool(output_text) and content_matched and mud_connected,
        "output_written": bool(output_text),
        "content_matched": content_matched,
        "mud_connected": mud_connected,
        "output_chars": len(output_text),
        "tool_call_count": len(tool_events),
        "bash_call_count": len(bash_events),
        "step_count": len(step_finishes),
        "final_reason": final_reason,
        "total_tokens": total_tokens,
        "agent": "opencode",
        **run_result,
    }
    result["working_dir"] = _relativize(result.get("working_dir"))
    result["log_path"] = _relativize(result.get("log_path"))
    result["stderr_tail"] = _scrub_local_paths(result.get("stderr_tail"))
    return result
