"""Eval adapter for the week1_baseline/python/12_context boukensha agent.

Each call to run_once() is a fresh subprocess: boukensha.state.config() is a
process-wide singleton (see boukensha/state.py), so a single process can't
swap model/backend/max_iterations between trials — and max_iterations has no
run() kwarg at all, it's config-only (boukensha/agent.py's MAX_ITERATIONS
fallback). A throwaway BOUKENSHA_DIR per run is the only way to control it,
and subprocess isolation also means a hung or crashing trial can't take down
the rest of the batch.

Runs must stay sequential, not parallel — mud.py auto-logs-in the configured
character (settings.yaml's mud.username) as soon as the tools are registered,
and CircleMUD only allows one live session per character.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

import return_to_midgaard

REPO_ROOT = Path(__file__).resolve().parent.parent
BOUKENSHA_PKG_DIR = REPO_ROOT / "week1_baseline" / "python" / "12_context"
VENV_PYTHON = BOUKENSHA_PKG_DIR / ".venv" / "bin" / "python3"
DRIVER = Path(__file__).resolve().parent / "_driver.py"
REAL_ENV_FILE = REPO_ROOT / ".boukensha" / ".env"

# mud_manager is a stdlib-only sibling package to boukensha (socket/re/
# threading/time only — no third-party deps), so it imports fine under
# whatever plain `python3` runs run_bakery.py, without needing the
# boukensha venv the way the actual trial subprocess does.
sys.path.insert(0, str(BOUKENSHA_PKG_DIR))
from mud_manager.session import Error as MudSessionError  # noqa: E402
from mud_manager.session import Session  # noqa: E402


class WrongStartingRoomError(Exception):
    """Internal to this module — raised by check_starting_room() and caught
    inside run_once() itself, which responds by attempting a
    return_to_midgaard recovery run rather than letting this propagate.
    Callers of run_once() should not need to catch this one; see
    RecoveryFailedError for what they should catch instead."""


class PreflightConnectionError(Exception):
    """Raised by run_once() when check_starting_room() couldn't even
    determine where the character is — a connection timeout, reset, or
    login failure (mud_manager.session.Error and its subclasses:
    ConnectionError/LoginError/Timeout), as opposed to a clean answer that
    happens to be the wrong room. Distinct from WrongStartingRoomError on
    purpose: "I don't know" isn't "I checked and it's wrong," and running a
    return_to_midgaard recovery attempt (or the real scenario) against a
    connection that just proved flaky would likely just fail the same way
    again. Wraps the original mud_manager error for the caller to log."""

    def __init__(self, original: Exception) -> None:
        self.original = original
        super().__init__(
            f"couldn't verify the character's starting room — {type(original).__name__}: {original}. "
            "This is a connectivity issue (or CircleMUD/the collector being momentarily busy), not a "
            "wrong-room situation — try again once it's had a moment to settle."
        )


class RecoveryFailedError(Exception):
    """Raised by run_once() when the character wasn't where a scenario
    expected AND the return_to_midgaard recovery attempt also failed to get
    it back to The Temple Of Midgaard. There's no recall/teleport on this MUD
    (checked directly — bare `recall` returns "Huh!?!"), so at this point
    self-healing has been tried and failed: a human needs to walk the
    character back by hand before running more trials. Carries the
    recovery attempt's own run_result so the caller can still log what was
    tried before it stops the batch."""

    def __init__(self, recovery_result: dict) -> None:
        self.recovery_result = recovery_result
        super().__init__(
            "the character wasn't at the expected starting room, and the return_to_midgaard "
            "recovery attempt failed to get it back to The Temple Of Midgaard either — a human needs "
            "to walk it back by hand before running more trials."
        )


def _load_env_vars(env_file: Path) -> dict:
    """Minimal KEY=VALUE .env parser — deliberately not python-dotenv, so
    this stays usable from whatever plain `python3` runs run_bakery.py, not
    just the boukensha venv. Values are read into memory only: never write
    them to a file under evals/results/, which isn't a secrets-safe
    location (run artifacts, not gitignored the way top-level .env is)."""
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


def configured_ollama_host() -> str:
    """Resolve Ollama exactly where eval subprocesses get their setting.

    The returned private URL is for requests only. Callers must not include it
    in logs/results; discovery errors are sanitized by ollama_catalog.py.
    """
    runtime_env = {**os.environ, **_load_env_vars(REAL_ENV_FILE)}
    if runtime_env.get("OLLAMA_HOST"):
        return runtime_env["OLLAMA_HOST"]

    settings_file = REPO_ROOT / ".boukensha" / "settings.yaml"
    if settings_file.exists():
        settings = yaml.safe_load(settings_file.read_text()) or {}
        configured = (settings.get("ollama") or {}).get("host")
        if configured:
            return str(configured)
    return "http://localhost:11434"

# The shared test account every existing manual test run (AGENTS.md Test 1-4)
# already uses — see .boukensha/settings.yaml.
DEFAULT_MUD = {"host": "localhost", "port": 4000, "username": "dummy", "password": "helloworld"}

# How long check_starting_room() waits after its own disconnect before
# returning — see the comment at its call site. Picked empirically-ish
# (CircleMUD's own descriptor cleanup for an abrupt EOF looked fast in
# testing, but the repeated real-world failures argued for erring
# generous over shaving it close again).
SETTLE_SECONDS = 3

# Matches the otel-collector's OTLP/HTTP port from
# week0_explore/infrastructure/observability (see QUICKSTART.md's "OpenTelemetry
# tracing" section) — same endpoint interactive play points at. tracing.configure()
# is a no-op if the collector isn't actually reachable, so this is safe to set
# unconditionally rather than probing for the stack first.
DEFAULT_OTEL_ENDPOINT = "http://localhost:4318"
# Distinct service name so eval traces don't mix into interactive play's
# "boukensha-agent" service in Jaeger/Tempo's service picker.
EVAL_OTEL_SERVICE_NAME = "boukensha-agent-eval"


def check_starting_room(expected_substring: str, mud: dict) -> str:
    """Connects, looks, disconnects immediately — doesn't hold the session
    open, so it can't collide with the actual trial's own mud_connect()
    right after. Returns the room text on a match; raises
    WrongStartingRoomError (case-insensitive substring check) if not.

    This check only observes state: there is no
    recall/teleport command on this MUD server (checked directly — bare
    `recall` returns "Huh!?!"), and CircleMUD resumes a character exactly
    where it was on both a clean quit and a raw disconnect. run_once() can
    respond to a mismatch by launching the navigation-based recovery task,
    but this function itself never mutates the character. It prevents a real
    scenario from silently assuming a starting position that is not true."""
    session = Session(host=mud["host"], port=mud["port"])
    try:
        session.open()
        session.login(mud["username"], mud["password"])
        session.drain()
        session.send_command("look")
        room_text = session.read_until_prompt()
    finally:
        session.close()
        # close() drops the raw TCP connection (no "quit" — see the module
        # docstring on why this can't safely send one), which CircleMUD
        # sees as "WARNING: EOF on socket read (connection broken by peer)"
        # and has to process as a link-death before the character is fully
        # free again. The real trial's own mud_connect() was landing microseconds
        # later — a repeated failure mode (every mud_connect() attempt
        # timing out waiting for the "By what name..." prompt that never
        # arrives) traced to exactly this: the new connection arriving
        # before the server finished cleaning up the old one. A short pause
        # here gives it room to finish first.
        time.sleep(SETTLE_SECONDS)

    if expected_substring.lower() not in room_text.lower():
        raise WrongStartingRoomError(
            f"expected the character to be at {expected_substring!r}, but it isn't. "
            f"Walk it back there by hand (no recall/teleport exists on this server) "
            f"before running more trials. Actual room:\n{room_text.strip()}"
        )
    return room_text


def _run_trial(
    scenario,
    *,
    backend: str,
    model: str,
    run_dir: Path,
    mud: dict,
    timeout: int,
    max_reprompts: int,
) -> dict:
    """Runs one subprocess trial of `scenario`, no preflight room check and
    no recovery logic — just "launch the driver, collect what came back".
    run_once() is the public entry point; this is the part of it that
    actually existed before the return_to_midgaard recovery flow, factored
    out so run_once() can call it twice (recovery, then the real scenario)
    without duplicating the subprocess/settings.yaml/env plumbing.

    Returns a dict with working_dir, log path, timing, and process outcome —
    NOT the scenario's pass/fail score. Call score.score_run() on the result
    separately (keeps "did it run" and "did it succeed" independent).
    """
    run_dir = Path(run_dir)
    working_dir = run_dir / "workdir"
    working_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "session.jsonl"

    boukensha_dir = run_dir / ".boukensha"
    boukensha_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "tasks": {"player": {"provider": backend, "model": model}},
        "agent": {"max_iterations": scenario.MAX_TURNS},
        "mud": mud,
    }
    (boukensha_dir / "settings.yaml").write_text(yaml.safe_dump(settings))

    env = {
        **os.environ,
        **_load_env_vars(REAL_ENV_FILE),
        "BOUKENSHA_DIR": str(boukensha_dir),
        "OTEL_SERVICE_NAME": EVAL_OTEL_SERVICE_NAME,
    }
    env.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTEL_ENDPOINT)

    started = time.monotonic()
    try:
        proc = subprocess.run(
            [
                str(VENV_PYTHON),
                str(DRIVER),
                "--task", scenario.TASK,
                "--backend", backend,
                "--model", model,
                "--working-dir", str(working_dir),
                "--log", str(log_path),
                "--max-reprompts", str(max_reprompts),
                "--scenario", getattr(scenario, "__name__", "unknown").rsplit(".", 1)[-1],
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        timed_out = False
        returncode = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        returncode = None
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")

    trace_id = None
    final_room = None
    for line in (stdout or "").splitlines():
        if line.startswith("TRACE_ID="):
            trace_id = line.removeprefix("TRACE_ID=").strip() or None
        elif line.startswith("FINAL_ROOM_B64="):
            encoded = line.removeprefix("FINAL_ROOM_B64=").strip()
            try:
                final_room = base64.b64decode(encoded).decode() if encoded else None
            except (ValueError, UnicodeDecodeError):
                final_room = None

    return {
        "backend": backend,
        "model": model,
        "working_dir": str(working_dir),
        "log_path": str(log_path),
        "duration_s": time.monotonic() - started,
        "returncode": returncode,
        "timed_out": timed_out,
        "stderr_tail": stderr[-2000:] if stderr else "",
        "max_reprompts": max_reprompts,
        # Includes the count, not just "reprompt" — matches run_bakery.py's
        # own run_dir naming (f"reprompt{max_reprompts}"). A bare "reprompt"
        # would silently merge reprompt2 and reprompt5 batches into one
        # dashboard group, since eval_results.rb groups by [scenario,
        # model_label, mode] — different budgets are different conditions.
        "mode": f"reprompt{max_reprompts}" if max_reprompts > 0 else "strict",
        "trace_id": trace_id,
        "final_room": final_room,
    }


# Recovery gets its own budget, independent of whatever max_reprompts the
# real scenario was asked to run with — "find your way home" is a different,
# usually harder navigation problem than the scenario itself and deserves
# its own room to fail before giving up.
RECOVERY_MAX_REPROMPTS = 1

# A single recovery attempt occasionally loses to a transient MUD hiccup
# rather than a genuinely hard-to-reach starting position — the exact
# "already open" connection bug fixed in mud_manager/session.py looked
# indistinguishable from a real failure until it was traced down. Giving
# recovery one extra fresh attempt (a brand-new subprocess and Session) before
# calling it failed avoids losing an entire unattended batch to one bad
# connection. run_bakery.py's own consecutive-failure circuit breaker is the
# backstop for when retrying here isn't enough.
RECOVERY_ATTEMPTS = 2

# Same rationale as check_starting_room()'s SETTLE_SECONDS: give CircleMUD a
# moment to finish tearing down the previous descriptor before the next
# attempt's mud_connect() lands.
RECOVERY_RETRY_SETTLE_SECONDS = 3


def run_once(
    scenario,
    *,
    backend: str,
    model: str,
    run_dir: Path,
    mud: dict | None = None,
    timeout: int = 300,
    max_reprompts: int = 0,
) -> list[tuple[object, dict]]:
    """Run one trial of `scenario` against the boukensha agent.

    max_reprompts: 0 (default) is the strict hard-budget mode — one
    scenario.MAX_TURNS-iteration attempt, no follow-up. >0 gives the agent a
    fresh scenario.MAX_TURNS-iteration budget up to that many additional
    times, but only when it actually exhausted the previous budget without
    voluntarily ending the turn — see boukensha.run_reprompted()'s
    docstring. Report on both modes per scenario/model to see whether
    reprompting meaningfully changes the outcome or just burns more budget.

    If scenario.EXPECTED_START_ROOM is set and the character isn't there,
    this doesn't just fail the trial or abort the batch outright — it first
    runs return_to_midgaard.py as a recovery attempt (the agent navigating
    itself back, using the same look/move tools any scenario uses), up to
    RECOVERY_ATTEMPTS times (a fresh subprocess/Session each try, in case the
    first failure was just a flaky connection), and only raises
    RecoveryFailedError if every attempt fails to reach Temple Of Midgaard.
    There's no recall/teleport on this MUD, so this is the only automated
    recovery available. Callers (run_bakery.py) don't have to treat a single
    RecoveryFailedError as fatal — see its own circuit breaker for handling
    a genuinely stuck run without losing an entire unattended batch to one
    bad trial.

    Returns a list of (scenario_module, run_result) pairs — normally just
    `[(scenario, result)]`, but `[(return_to_midgaard, recovery_result),
    (scenario, result)]` when a recovery attempt was needed and succeeded.
    Each run_result is NOT the scenario's pass/fail score — call
    score.score_run(scenario_module, run_result) on each pair separately
    (keeps "did it run" and "did it succeed" independent).
    """
    resolved_mud = mud or DEFAULT_MUD
    expected_room = getattr(scenario, "EXPECTED_START_ROOM", None)
    if not expected_room:
        return [(scenario, _run_trial(
            scenario, backend=backend, model=model, run_dir=run_dir,
            mud=resolved_mud, timeout=timeout, max_reprompts=max_reprompts,
        ))]

    try:
        check_starting_room(expected_room, resolved_mud)
    except WrongStartingRoomError:
        pass  # fall through to the recovery attempt below
    except MudSessionError as e:
        # Couldn't even get an answer — a connection timeout/reset/login
        # failure, not a clean "yes/no it's the right room". Treating this
        # as "wrong room, try to recover" would very likely just hit the
        # same connectivity problem again on the recovery attempt's own
        # connection; surfacing it distinctly instead so run_bakery.py can
        # stop cleanly rather than either crash with a raw traceback or
        # silently plow ahead against a starting position that was never
        # actually confirmed.
        raise PreflightConnectionError(e) from e
    else:
        return [(scenario, _run_trial(
            scenario, backend=backend, model=model, run_dir=run_dir,
            mud=resolved_mud, timeout=timeout, max_reprompts=max_reprompts,
        ))]

    recovery_result = None
    recovered = False
    for attempt in range(1, RECOVERY_ATTEMPTS + 1):
        suffix = "recovery" if attempt == 1 else f"recovery{attempt}"
        recovery_result = _run_trial(
            return_to_midgaard, backend=backend, model=model,
            run_dir=Path(run_dir) / suffix, mud=resolved_mud,
            timeout=timeout, max_reprompts=RECOVERY_MAX_REPROMPTS,
        )
        recovered = bool(recovery_result.get("final_room")) and (
            return_to_midgaard.SUCCESS_ROOM.lower() in recovery_result["final_room"].lower()
        )
        if recovered:
            break
        if attempt < RECOVERY_ATTEMPTS:
            time.sleep(RECOVERY_RETRY_SETTLE_SECONDS)
    if not recovered:
        raise RecoveryFailedError(recovery_result)

    real_result = _run_trial(
        scenario, backend=backend, model=model, run_dir=run_dir,
        mud=resolved_mud, timeout=timeout, max_reprompts=max_reprompts,
    )
    return [(return_to_midgaard, recovery_result), (scenario, real_result)]
