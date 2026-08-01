"""Run the bakery scenario against OpenCode (opencode-ai) instead of the
boukensha agent — a different agent implementation evaluated through the same
task and (mostly) the same scoring contract, so results are comparable.

    python3 evals/run_bakery_opencode.py
    python3 evals/run_bakery_opencode.py --repetitions 3 --model ollama/qwen3.6:35b-a3b

Prerequisites beyond the base evals/README.md list:
  - The `opencode` CLI installed and on PATH (`opencode --version`).
  - `.opencode/agents/bakery-evaluator.md` (this repo) — a single-shot,
    non-interactive agent purpose-built for unattended eval runs. Distinct
    from `.opencode/agents/mud-evaluator.md`, which is the older interactive
    Test 2-4 agent from the preweek exploration and expects a human typing
    start/yes/retry in the TUI — do not point this runner at it.
  - MUD_USERNAME/MUD_PASSWORD in the repository-root .env (read by
    data/code/mud-login.sh under week0_explore/explore_architecture/
    001_playing_agent — the same tmux+telnet bridge the preweek OpenCode
    work already used).

IMPORTANT — potentially shared MUD character: this uses `MUD_USERNAME` while
evals/run_bakery.py defaults to `dummy`. When those resolve to the same
account, the runners reach it through completely separate connection paths
(bash + tmux + telnet here, Python mud_manager.Session in Boukensha).
CircleMUD only allows one live session per character, so matching accounts
must never run at the same time. login-mud's tmux session (`opencode-mud`) also
persists *outside* any single `opencode run` process — left open, it would
sit on the character indefinitely and collide with the next boukensha batch
even after this script exits. _run_trial() explicitly closes it (`mud-login.sh
stop`) after every trial for exactly that reason; don't remove that call.

No position-drift recovery yet (unlike run_bakery.py's return_to_midgaard
flow) and no circuit breaker — this is a first pass for occasional/manual
runs between boukensha batches, not an unattended overnight harness. Add
those if this graduates to regular overnight use.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import bakery
import score_opencode

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"
AGENT_NAME = "bakery-evaluator"
REPO_ROOT_ENV_FILE = REPO_ROOT / ".env"


def _load_env_vars(env_file: Path) -> dict:
    """Minimal KEY=VALUE .env parser, mirroring boukensha_agent.py's own —
    read into memory only, never written back to disk anywhere under
    evals/results/. opencode.json's ollama provider substitutes
    {env:OLLAMA_HOST} at invocation time; without this, a subprocess.run()
    launched from Python (no shell/.env sourcing of its own) fails with
    something like '"/v1/chat/completions" cannot be parsed as a URL' — the
    substitution silently resolves to an empty string instead of a real
    host."""
    if not env_file.exists():
        return {}
    out = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out

# The tmux+telnet bridge from the preweek OpenCode exploration — see this
# file's module docstring. Run from the directory containing AGENTS.md,
# same as .opencode/skills/login-mud/SKILL.md's own instructions.
MUD_LOGIN_SCRIPT_DIR = REPO_ROOT / "week0_explore" / "explore_architecture" / "001_playing_agent"
MUD_LOGIN_SCRIPT = MUD_LOGIN_SCRIPT_DIR / "data" / "code" / "mud-login.sh"


def _stop_mud_session() -> None:
    """Closes the login-mud tmux session so it can't outlive this script and
    collide with a later boukensha batch (see module docstring). Best-effort:
    a failure here shouldn't crash the run, but is worth surfacing loudly
    since a leaked session is exactly the kind of thing that causes a
    confusing connection failure hours later in an unrelated script."""
    try:
        subprocess.run(
            [str(MUD_LOGIN_SCRIPT), "stop"],
            cwd=str(MUD_LOGIN_SCRIPT_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:  # noqa: BLE001 — best-effort cleanup, never worth failing the trial over
        print(f"[run_bakery_opencode] WARNING: could not confirm the MUD tmux session closed cleanly: {e}", file=sys.stderr)


def _run_trial(scenario, *, model: str, run_dir: Path, timeout: int) -> dict:
    run_dir = Path(run_dir)
    working_dir = run_dir / "workdir"
    working_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "events.jsonl"

    env = {**os.environ, **_load_env_vars(REPO_ROOT_ENV_FILE)}

    started = time.monotonic()
    try:
        proc = subprocess.run(
            [
                "opencode", "run",
                "--dir", str(working_dir),
                "--agent", AGENT_NAME,
                "--model", model,
                "--format", "json",
                scenario.TASK,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        timed_out = False
        returncode = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        returncode = None
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
    finally:
        # Always attempt cleanup, timeout or not — a killed `opencode run`
        # leaves the tmux session exactly as alive as a clean exit would.
        _stop_mud_session()

    log_path.write_text(stdout)

    return {
        "model": model,
        "working_dir": str(working_dir),
        "log_path": str(log_path),
        "duration_s": time.monotonic() - started,
        "returncode": returncode,
        "timed_out": timed_out,
        "stderr_tail": stderr[-2000:] if stderr else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repetitions", type=int, default=3)
    ap.add_argument("--model", default="ollama/qwen3.6:35b-a3b", help="provider/model, e.g. ollama/qwen3.6:35b-a3b")
    ap.add_argument("--timeout", type=int, default=300, help="seconds per trial")
    args = ap.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    results_path = RESULTS_DIR / "bakery_opencode.jsonl"
    batch_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    with results_path.open("a") as out:
        for rep in range(args.repetitions):
            run_dir = RESULTS_DIR / f"opencode_{batch_id}" / str(rep)
            print(f"[opencode:{args.model} rep {rep}] running...", file=sys.stderr)

            run_result = _run_trial(bakery, model=args.model, run_dir=run_dir, timeout=args.timeout)
            result = score_opencode.score_run(bakery, run_result)
            result["batch_id"] = batch_id
            result["scenario"] = "bakery"
            result["repetition"] = rep

            out.write(json.dumps(result) + "\n")
            out.flush()
            status = "PASS" if result["task_success"] else "FAIL"
            print(
                f"[opencode:{args.model} rep {rep} :: bakery] {status} "
                f"({result['step_count']} step(s), {result['bash_call_count']} bash calls, "
                f"{result['duration_s']:.1f}s)",
                file=sys.stderr,
            )

    print(f"\nResults appended to {results_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
