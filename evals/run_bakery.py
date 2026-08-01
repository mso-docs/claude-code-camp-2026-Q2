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
import sys
import time
from pathlib import Path

import bakery
import boukensha_agent
import return_to_midgaard
import score

RESULTS_DIR = Path(__file__).resolve().parent / "results"

DEFAULT_TARGETS = [
    ("ollama", "qwen3.6:35b-a3b"),
]


def parse_target(spec: str) -> tuple[str, str]:
    backend, _, model = spec.partition(":")
    if not model:
        raise argparse.ArgumentTypeError(f"expected backend:model, got {spec!r}")
    return backend, model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repetitions", type=int, default=5)
    ap.add_argument("--model", action="append", type=parse_target, dest="targets", help="backend:model, repeatable")
    ap.add_argument("--timeout", type=int, default=300, help="seconds per trial")
    ap.add_argument(
        "--reprompts", action="append", type=int, dest="reprompt_modes",
        help="max_reprompts value to test, repeatable (default: 0 and 2, i.e. strict + reprompt)",
    )
    args = ap.parse_args()
    targets = args.targets or DEFAULT_TARGETS
    reprompt_modes = args.reprompt_modes or [0, 2]

    RESULTS_DIR.mkdir(exist_ok=True)
    results_path = RESULTS_DIR / "bakery.jsonl"
    batch_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    with results_path.open("a") as out:
        for backend, model in targets:
            for max_reprompts in reprompt_modes:
                mode_label = "strict" if max_reprompts == 0 else f"reprompt{max_reprompts}"
                for rep in range(args.repetitions):
                    run_dir = RESULTS_DIR / batch_id / f"{backend}_{model.replace(':', '-')}" / mode_label / str(rep)
                    print(f"[{backend}:{model} {mode_label} rep {rep}] running...", file=sys.stderr)

                    try:
                        trial_results = boukensha_agent.run_once(
                            bakery, backend=backend, model=model, run_dir=run_dir,
                            timeout=args.timeout, max_reprompts=max_reprompts,
                        )
                    except boukensha_agent.RecoveryFailedError as e:
                        # Room mismatch AND the agent's own attempt to
                        # navigate back to The Temple Of Midgaard also failed — self-
                        # healing has been tried, not just skipped. Every
                        # remaining trial in this batch would start from the
                        # same wrong room, so stop outright rather than
                        # write more results against a starting condition
                        # already known to be invalid. The failed recovery
                        # attempt itself is still logged, though — it's a
                        # real trial that really ran.
                        recovery_score = score.score_run(return_to_midgaard, e.recovery_result)
                        recovery_score["batch_id"] = batch_id
                        recovery_score["scenario"] = "return_to_midgaard"
                        recovery_score["repetition"] = rep
                        out.write(json.dumps(recovery_score) + "\n")
                        out.flush()
                        print(f"\n*** BATCH STOPPED — {e}\n", file=sys.stderr)
                        print(f"Results so far (including the failed recovery attempt) are in {results_path}", file=sys.stderr)
                        return 1
                    except boukensha_agent.PreflightConnectionError as e:
                        # Couldn't even confirm the starting room — a
                        # connection hiccup, not a real trial outcome.
                        # Nothing to log (no trial actually ran); stop
                        # cleanly rather than crash with a raw traceback or
                        # press on against an unconfirmed starting position.
                        print(f"\n*** BATCH STOPPED — {e}\n", file=sys.stderr)
                        print(f"Results so far (if any) are in {results_path}", file=sys.stderr)
                        return 1

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
