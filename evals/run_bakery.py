"""Run the bakery scenario against the boukensha agent across models/repetitions.

    python3 evals/run_bakery.py
    python3 evals/run_bakery.py --repetitions 3 --model ollama:qwen3.6:35b-a3b
    python3 evals/run_bakery.py --reprompts 0        # strict-only, no reprompt mode
    python3 evals/run_bakery.py --reprompts 0 --reprompts 2 --reprompts 5

Runs both a strict hard-budget mode (--reprompts 0: one MAX_TURNS-iteration
attempt, no follow-up) and a reprompt mode (--reprompts N>0: up to N more
fresh MAX_TURNS budgets, only fired when the agent actually exhausted the
previous one — see boukensha.run_reprompted()) by default, so the dashboard
can show whether reprompting meaningfully changes the outcome for a given
scenario/model or just spends more time reaching the same result.

Runs are sequential (see boukensha_agent's module docstring for why) and
results append to evals/results/bakery.jsonl — one line per trial.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import bakery
import boukensha_agent
import ollama_catalog
import return_to_midgaard
import score

RESULTS_DIR = Path(__file__).resolve().parent / "results"

DEFAULT_TARGETS = [
    ("ollama", "qwen3.6:35b-a3b"),
]

# A RecoveryFailedError or PreflightConnectionError on one repetition doesn't
# stop the batch by itself — boukensha_agent.run_once() already retries
# recovery once internally, and the very next repetition gets its own fresh
# preflight check and recovery attempt anyway, so a single stalled trial is
# skipped and logged rather than losing an entire unattended overnight run.
# But CONSECUTIVE_STALL_LIMIT stalls in a row (no successful trial in
# between) stops the batch outright — that pattern means something
# structural is wrong (MUD container down, network dead), not a one-off
# hiccup, and no amount of per-trial retrying will fix it.
CONSECUTIVE_STALL_LIMIT = 3
# Same idea as boukensha_agent.RECOVERY_RETRY_SETTLE_SECONDS — give
# CircleMUD/the MUD container a moment before the next repetition's own
# preflight check reconnects.
STALL_BACKOFF_SECONDS = 5

# A flat 300s --timeout default silently killed 28% of bakery trials during
# the 2026-08-01 overnight batches (see docs/journal/2.5_evals.md) — not by
# the agent exhausting its own iteration/reprompt budget, but by an
# unrelated wall clock racing it and winning, well before that budget was
# used up (killed trials averaged ~14/25 iterations and 0 reprompts used).
# Real observed per-iteration latency against a local Ollama backend: median
# 6.6s, 90th percentile 11.2s — reprompt2 alone promises up to 3 turns *
# MAX_TURNS iterations, which at that pace can take several times the old
# flat default for a single trial. SECONDS_PER_ITERATION_ESTIMATE rounds up
# from the observed 90th percentile for headroom (local model inference is
# the dominant per-iteration cost here, not MUD round-trip time, which is
# typically well under 1s); TIMEOUT_OVERHEAD_SECONDS covers per-trial cost
# outside the iteration loop itself (auto-connect, settle delays).
SECONDS_PER_ITERATION_ESTIMATE = 15.0
TIMEOUT_OVERHEAD_SECONDS = 60


def default_timeout(scenario, max_reprompts: int) -> int:
    """Scales off what --reprompts actually promises for `scenario`, so the
    agent's own iteration/reprompt design stays the deciding factor instead
    of a flat guess that's silently wrong for a slower model/backend (or
    silently way too generous for a fast one). Only used when --timeout
    isn't passed explicitly — see main()."""
    total_iterations = (max_reprompts + 1) * scenario.MAX_TURNS
    return int(total_iterations * SECONDS_PER_ITERATION_ESTIMATE + TIMEOUT_OVERHEAD_SECONDS)


def parse_target(spec: str) -> tuple[str, str]:
    backend, _, model = spec.partition(":")
    if not model:
        raise argparse.ArgumentTypeError(f"expected backend:model, got {spec!r}")
    return backend, model


def model_dir_name(backend: str, model: str) -> str:
    """Filesystem-safe run directory for namespaced tags."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", f"{backend}_{model}").strip("-")


def print_ollama_catalog(models: list[ollama_catalog.OllamaModel]) -> None:
    first_by_digest = {}
    print(f"{len(models)} installed Ollama model tags")
    print("TOOLS  MODEL                                      DIGEST        DETAILS                 CAPABILITIES")
    for model in models:
        alias = ""
        if model.digest:
            first = first_by_digest.setdefault(model.digest, model.name)
            if first != model.name:
                alias = f" alias-of={first}"
        marker = "yes" if model.supports_tools else " no"
        details = " ".join(v for v in (model.parameter_size, model.quantization) if v) or "-"
        capabilities = ",".join(model.capabilities) or "-"
        print(
            f"{marker:>5}  {model.name:<42} {model.digest[:12]:<12}  "
            f"{details:<22} {capabilities}{alias}"
        )


def probe_targets(
    host: str,
    targets: list[tuple[str, str]],
    *,
    timeout: float,
) -> list[tuple[str, str]]:
    """Keep non-Ollama targets and Ollama models passing a two-call probe."""
    kept = []
    for backend, model in targets:
        if backend != "ollama":
            kept.append((backend, model))
            continue
        print(f"[ollama:{model}] probing tool call + result round trip...", file=sys.stderr)
        result = ollama_catalog.probe_tool_loop(host, model, timeout=timeout)
        status = "PASS" if result.passed else "SKIP"
        print(
            f"[ollama:{model}] probe {status}: {result.status} — {result.detail} "
            f"({result.duration_s:.1f}s)",
            file=sys.stderr,
        )
        if result.passed:
            kept.append((backend, model))
    return kept


def unique_targets(targets: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return list(dict.fromkeys(targets))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repetitions", type=int, default=5)
    ap.add_argument("--model", action="append", type=parse_target, dest="targets", help="backend:model, repeatable")
    discovery = ap.add_mutually_exclusive_group()
    discovery.add_argument(
        "--all-ollama-tools",
        action="store_true",
        help="add every unique installed Ollama completion model advertising tool support",
    )
    discovery.add_argument(
        "--all-ollama",
        action="store_true",
        help="add every unique installed Ollama completion model, including models without tool support",
    )
    ap.add_argument(
        "--list-ollama-models",
        action="store_true",
        help="show the runtime Ollama catalog/capabilities resolved from configuration, then exit",
    )
    ap.add_argument(
        "--include-ollama-aliases",
        action="store_true",
        help="keep multiple tags with the same Ollama digest (discovery deduplicates aliases by default)",
    )
    ap.add_argument(
        "--probe-ollama-tools",
        action="store_true",
        help="before MUD trials, require each selected Ollama model to pass a tool-call and post-result completion probe",
    )
    ap.add_argument(
        "--ollama-probe-only",
        action="store_true",
        help="run the selected Ollama tool-loop probes and exit without starting MUD trials",
    )
    ap.add_argument(
        "--ollama-probe-timeout",
        type=float,
        default=120,
        help="seconds allowed for each of the probe's two model requests (default: 120)",
    )
    ap.add_argument(
        "--timeout", type=int, default=None,
        help="seconds per trial (default: auto-scaled from --reprompts and the scenario's MAX_TURNS — see default_timeout())",
    )
    ap.add_argument(
        "--reprompts", action="append", type=int, dest="reprompt_modes",
        help="max_reprompts value to test, repeatable (default: 0 and 2, i.e. strict + reprompt)",
    )
    args = ap.parse_args()

    needs_catalog = args.list_ollama_models or args.all_ollama_tools or args.all_ollama
    catalog = []
    ollama_host = None
    if needs_catalog or args.probe_ollama_tools or args.ollama_probe_only:
        ollama_host = boukensha_agent.configured_ollama_host()
    if needs_catalog:
        try:
            catalog = ollama_catalog.discover_models(ollama_host)
        except ollama_catalog.OllamaCatalogError as e:
            ap.error(f"could not discover Ollama models: {e}")

    if args.list_ollama_models:
        print_ollama_catalog(catalog)
        return 0

    targets = list(args.targets or [])
    if args.all_ollama_tools or args.all_ollama:
        discovered = ollama_catalog.select_models(
            catalog,
            tools_only=args.all_ollama_tools,
            include_aliases=args.include_ollama_aliases,
        )
        targets.extend(("ollama", model.name) for model in discovered)
    if not targets:
        targets = list(DEFAULT_TARGETS)
    targets = unique_targets(targets)

    if args.probe_ollama_tools or args.ollama_probe_only:
        selected_ollama_count = sum(1 for backend, _ in targets if backend == "ollama")
        if selected_ollama_count == 0:
            ap.error("Ollama probing requires at least one selected ollama:model target")
        targets = probe_targets(ollama_host, targets, timeout=args.ollama_probe_timeout)
        passed_ollama_count = sum(1 for backend, _ in targets if backend == "ollama")
        if args.ollama_probe_only:
            return 0 if passed_ollama_count == selected_ollama_count else 2
        if not targets:
            print("No selected models passed the Ollama tool-loop probe; no trials were run.", file=sys.stderr)
            return 2

    reprompt_modes = args.reprompt_modes or [0, 2]

    RESULTS_DIR.mkdir(exist_ok=True)
    results_path = RESULTS_DIR / "bakery.jsonl"
    batch_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    consecutive_stalls = 0

    with results_path.open("a") as out:
        for backend, model in targets:
            for max_reprompts in reprompt_modes:
                mode_label = "strict" if max_reprompts == 0 else f"reprompt{max_reprompts}"
                trial_timeout = args.timeout if args.timeout is not None else default_timeout(bakery, max_reprompts)
                print(f"[{backend}:{model} {mode_label}] timeout per trial: {trial_timeout}s", file=sys.stderr)
                for rep in range(args.repetitions):
                    run_dir = RESULTS_DIR / batch_id / model_dir_name(backend, model) / mode_label / str(rep)
                    print(f"[{backend}:{model} {mode_label} rep {rep}] running...", file=sys.stderr)

                    try:
                        trial_results = boukensha_agent.run_once(
                            bakery, backend=backend, model=model, run_dir=run_dir,
                            timeout=trial_timeout, max_reprompts=max_reprompts,
                        )
                    except boukensha_agent.RecoveryFailedError as e:
                        # Room mismatch AND every retried attempt to navigate
                        # back to The Temple Of Midgaard also failed. Rather
                        # than stopping the whole batch on one stalled
                        # repetition, log the failed recovery attempt (a real
                        # trial that really ran) and move on — the next
                        # repetition gets its own fresh preflight check and
                        # recovery attempt, so a transient hiccup here doesn't
                        # have to end the night. CONSECUTIVE_STALL_LIMIT in a
                        # row is the actual stop condition; see its comment.
                        recovery_score = score.score_run(return_to_midgaard, e.recovery_result)
                        recovery_score["batch_id"] = batch_id
                        recovery_score["scenario"] = "return_to_midgaard"
                        recovery_score["repetition"] = rep
                        out.write(json.dumps(recovery_score) + "\n")
                        out.flush()
                        consecutive_stalls += 1
                        print(
                            f"[{backend}:{model} {mode_label} rep {rep}] RECOVERY FAILED "
                            f"({consecutive_stalls}/{CONSECUTIVE_STALL_LIMIT} in a row) — {e}",
                            file=sys.stderr,
                        )
                        if consecutive_stalls >= CONSECUTIVE_STALL_LIMIT:
                            print(
                                f"\n*** BATCH STOPPED — {CONSECUTIVE_STALL_LIMIT} stalled repetitions in a row. "
                                "That's not one-off bad luck — something structural is likely wrong (MUD container "
                                "down, network dead) and a human needs to check on it before more trials would help.\n",
                                file=sys.stderr,
                            )
                            print(f"Results so far (including failed recovery attempts) are in {results_path}", file=sys.stderr)
                            return 1
                        time.sleep(STALL_BACKOFF_SECONDS)
                        continue
                    except boukensha_agent.PreflightConnectionError as e:
                        # Couldn't even confirm the starting room — a
                        # connection hiccup, not a real trial outcome.
                        # Nothing to log (no trial actually ran); skip this
                        # repetition the same way as a failed recovery,
                        # subject to the same circuit breaker.
                        consecutive_stalls += 1
                        print(
                            f"[{backend}:{model} {mode_label} rep {rep}] CONNECTION CHECK FAILED "
                            f"({consecutive_stalls}/{CONSECUTIVE_STALL_LIMIT} in a row) — {e}",
                            file=sys.stderr,
                        )
                        if consecutive_stalls >= CONSECUTIVE_STALL_LIMIT:
                            print(
                                f"\n*** BATCH STOPPED — {CONSECUTIVE_STALL_LIMIT} stalled repetitions in a row. "
                                "That's not one-off bad luck — something structural is likely wrong (MUD container "
                                "down, network dead) and a human needs to check on it before more trials would help.\n",
                                file=sys.stderr,
                            )
                            print(f"Results so far (if any) are in {results_path}", file=sys.stderr)
                            return 1
                        time.sleep(STALL_BACKOFF_SECONDS)
                        continue

                    consecutive_stalls = 0
                    for scenario_module, run_result in trial_results:
                        result = score.score_run(scenario_module, run_result)
                        result["batch_id"] = batch_id
                        result["scenario"] = scenario_module.__name__.rsplit(".", 1)[-1]
                        result["repetition"] = rep

                        out.write(json.dumps(result) + "\n")
                        out.flush()
                        status = "PASS" if result["task_success"] else "FAIL"
                        print(
                            f"[{backend}:{model} {mode_label} rep {rep} :: {result['scenario']}] {status} "
                            f"({result['turn_count']} turn(s), {result['reprompt_count']} reprompt(s) used, "
                            f"{result['iteration_count']} total iterations, "
                            f"{result['tool_call_count']} tool calls, "
                            f"{result['duration_s']:.1f}s)",
                            file=sys.stderr,
                        )

    print(f"\nResults appended to {results_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
