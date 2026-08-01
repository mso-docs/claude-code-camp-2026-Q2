"""Deterministic scoring for one eval trial.

Reads two things produced by a boukensha_agent.run_once() call: the agent's
working_dir (did it produce the goal artifact?) and its session.jsonl log
(how did it get there?). No LLM-judge scoring here — see 09_journal /
15_otel_tracing.md's own verdict on trace-UI legibility for why deterministic,
game-state-grounded checks are preferred over another model's opinion.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _relativize(path_str: str | None) -> str | None:
    """Local absolute paths (e.g. /home/<you>/code/.../evals/results/<batch>/...)
    never reach evals/results/*.jsonl — every scenario runner funnels through
    score_run(), so this is the one place that has to get it right for it to
    be true "by standard" rather than a convention each new run_*.py script
    has to remember. Relative-to-RESULTS_DIR rather than a flat redacted
    placeholder: it stays useful (log_viz's transcript/story/trace links
    depend on being able to locate the file) while dropping everything
    machine-specific — no home directory, no username, nothing that isn't
    already implied by being inside this repo's own evals/results/."""
    if not path_str:
        return path_str
    try:
        return str(Path(path_str).resolve().relative_to(RESULTS_DIR))
    except ValueError:
        return path_str  # not under evals/results/ at all — leave it alone rather than guess


def _scrub_local_paths(text: str | None) -> str | None:
    """Same idea as _relativize(), for free text (stderr_tail) rather than a
    single path field — a Python traceback embeds the repo's full absolute
    path in every "File ..." line."""
    if not text:
        return text
    return text.replace(str(REPO_ROOT) + "/", "")


def _read_log(log_path: Path) -> list[dict]:
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
    """run_result is whatever boukensha_agent.run_once() returned."""
    log_path = Path(run_result["log_path"])
    entries = _read_log(log_path)

    # A model that never connected has been caught fabricating a whole
    # plausible-looking file from imagination alone — a qwen3.6:35b-a3b run
    # where every mud_connect() attempt timed out still wrote a complete
    # invented bakery menu ("Dragon Bread", "Magic Leavened Loaf") and
    # called the task done. Content keywords alone can't catch that if the
    # invented content happens to contain the keyword too (see bakery.py's
    # EXPECTED_MENU_KEYWORDS comment on why plain "bread" got dropped) — so
    # this checks something the model can't fabricate around: whether
    # mud.py's mud_connect() tool itself ever actually reported success in
    # the log, straight from the MUD server's own response text, not
    # anything the model said about it.
    mud_connected = any(
        e.get("phase") == "tool_result"
        and e.get("name") == "mud_connect"
        and e.get("ok", True)
        and isinstance(e.get("result"), str)
        and not e["result"].strip().lower().startswith("error:")
        for e in entries
    )

    # Two kinds of scenario, two kinds of content check. Most (bakery) write
    # a file — checked against OUTPUT_FILE/EXPECTED_MENU_KEYWORDS. A recovery
    # scenario (return_to_midgaard.py) has no file to write at all; its goal
    # is a *place*, checked against the final `look` boukensha_agent.py
    # already captures for every trial (see _driver.py's FINAL_ROOM_B64) —
    # that check is already MUD-grounded on its own (an unconnected agent's
    # final `look` comes back "error: not connected...", which can't match
    # a real room name), but mud_connected still applies to it below for a
    # second, independent line of evidence.
    success_room = getattr(scenario, "SUCCESS_ROOM", None)
    if success_room:
        output_text = (run_result.get("final_room") or "").strip()
        content_matched = success_room.lower() in output_text.lower()
    else:
        working_dir = Path(run_result["working_dir"])
        output_path = working_dir / scenario.OUTPUT_FILE
        output_text = output_path.read_text().strip() if output_path.exists() else ""

        # A non-empty file isn't proof of task success on its own — a model
        # that can't find the real target has been observed writing a
        # plausible-looking substitute (a bar's menu, in its own words
        # because no bakery could be found) and calling it done. If the
        # scenario defines expected content keywords, require at least one
        # to actually show up (case-insensitive); scenarios that don't
        # define any keep the old file-non-empty-only check.
        expected_keywords = getattr(scenario, "EXPECTED_MENU_KEYWORDS", None)
        if expected_keywords:
            content_matched = any(kw.lower() in output_text.lower() for kw in expected_keywords)
        else:
            content_matched = bool(output_text)

    tool_calls = [e for e in entries if e.get("phase") == "tool_call"]
    tool_results = [e for e in entries if e.get("phase") == "tool_result"]
    iterations = [e for e in entries if e.get("phase") == "iteration"]
    # Total actions taken across every turn, not the last turn's own n —
    # run_reprompted() gives each reprompt a *fresh* Agent whose iteration
    # counter restarts at 0 (boukensha/agent.py), so a max(n) here would
    # silently drop everything but the final turn's count.
    iteration_count = len(iterations)
    session_start = next((e for e in entries if e.get("phase") == "session_start"), {})
    max_iterations = session_start.get("max_iterations") or scenario.MAX_TURNS
    dispatch_errors = [e for e in tool_results if not e.get("ok", True)]
    # mud.py's tools catch guard()/ValueError internally and return an
    # "error: ..." string with ok=True rather than raising — those don't
    # show up in dispatch_errors above, so they're counted separately.
    mud_rejections = [
        e for e in tool_results
        if e.get("ok", True) and isinstance(e.get("result"), str) and e["result"].strip().lower().startswith("error:")
    ]
    # One turn_end per Agent.run() call (per boukensha/agent.py) — so its
    # count is 1 + however many reprompts actually fired (which can be
    # fewer than run_result["max_reprompts"] if the agent stopped early on
    # its own). Only the *last* turn's reason matters for "did it ultimately
    # run out of budget" — an earlier turn hitting the limit is what
    # triggers a reprompt in the first place, not a final-outcome failure.
    turn_ends = [e for e in entries if e.get("phase") == "turn_end"]
    turn_count = len(turn_ends)
    reprompt_count = max(turn_count - 1, 0)
    final_reason = turn_ends[-1].get("reason") if turn_ends else None
    hit_turn_limit = final_reason == "max_iterations"

    result = {
        "task_success": bool(output_text) and content_matched and mud_connected,
        "output_written": bool(output_text),
        "content_matched": content_matched,
        "mud_connected": mud_connected,
        "output_chars": len(output_text),
        "tool_call_count": len(tool_calls),
        "iteration_count": iteration_count,
        "max_iterations": max_iterations,
        "turn_count": turn_count,
        "reprompt_count": reprompt_count,
        "final_reason": final_reason,
        "dispatch_error_count": len(dispatch_errors),
        "mud_rejection_count": len(mud_rejections),
        "hit_turn_limit": hit_turn_limit,
        "process_failed": bool(run_result.get("timed_out")) or run_result.get("returncode") not in (0, None),
        "timed_out": bool(run_result.get("timed_out")),
        **run_result,
    }

    # Local-path redaction — last step, after everything above has already
    # used the real absolute paths to actually read files off disk.
    result["working_dir"] = _relativize(result.get("working_dir"))
    result["log_path"] = _relativize(result.get("log_path"))
    result["stderr_tail"] = _scrub_local_paths(result.get("stderr_tail"))

    return result
