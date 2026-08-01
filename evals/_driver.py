"""Subprocess entry point that runs one boukensha.run_reprompted() call
(--max-reprompts 0 behaves exactly like a single boukensha.run() call).

Invoked by boukensha_agent.run_once() using the week1_baseline/python/12_context
venv's interpreter, with BOUKENSHA_DIR pointed at a per-run throwaway config
dir (settings.yaml + .env) so model/backend/max_iterations/mud credentials
are isolated per run without touching the real ~/.boukensha or repo-root
.boukensha used for interactive play.
"""

import argparse
import base64
import sys
from pathlib import Path

from opentelemetry import trace as otel_trace

BOUKENSHA_PKG_DIR = Path(__file__).resolve().parents[1] / "week1_baseline" / "python" / "12_context"
sys.path.insert(0, str(BOUKENSHA_PKG_DIR))

import boukensha  # noqa: E402


def _disable_save(dsl: boukensha.RunDSL) -> None:
    """Removes save_character from the registry entirely, rather than
    shadowing it with a tool that just says "disabled" — mud_tools.register()
    has already added it by the time this block runs (see run_reprompted()'s
    call order), and Registry.tool()/register_tool() ultimately just write
    into context.tools (context.py), a plain dict, so popping the entry back
    out makes it genuinely gone: it never appears in the tool list built for
    the model at all, not just a tool that exists and refuses. If a model
    somehow calls it anyway (hallucinating a tool name outside what it was
    offered), Registry.dispatch() raises UnknownToolError, which agent.py's
    existing tool-call handling already turns into an
    "ERROR: UnknownToolError: No tool registered as 'save_character'"
    result — reading exactly like an unrecognized command, no bespoke
    "disabled" message needed.

    Why remove it at all: CircleMUD already preserves the live character's
    room across reconnects whether or not this command is called, so this
    does not solve within-batch position drift. An explicit save can also
    make the current room durable in the player file used after a real server
    restart, however, extending that drift beyond the live process. Eval
    tasks have no reason to mutate that durable checkpoint. Real play via
    `boukensha.run()`/`repl()` outside evals is unaffected — this only applies
    to the block evals/boukensha_agent.py passes in.
    """
    dsl.registry.context.tools.pop("save_character", None)


def _capture_registry_and_disable_save(captured: dict):
    """Returns a block= callback that both disables save_character and stashes
    the registry in `captured["registry"]` so main() can issue one last `look`
    after the trial ends — the character's position drifts on every trial
    regardless of save_character (CircleMUD resumes in place on both a clean
    quit and a raw disconnect — see evals/README.md), so logging where a
    trial actually left the character is the practical alternative to
    preventing drift altogether."""

    def block(dsl: boukensha.RunDSL) -> None:
        captured["registry"] = dsl.registry
        _disable_save(dsl)

    return block


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--working-dir", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--max-reprompts", type=int, default=0)
    ap.add_argument("--scenario", default=None)
    args = ap.parse_args()

    # Same tracing.configure() run()/repl() already call — a no-op unless
    # OTEL_EXPORTER_OTLP_ENDPOINT is set (boukensha_agent.py sets it for
    # every eval trial). Called explicitly, and before the span below, since
    # run_reprompted() would otherwise call it for the first time *inside*
    # the span-opening call, too late to matter for this specific span.
    boukensha.tracing.configure()

    trace_id_hex = None
    exit_code = 0
    captured: dict = {}
    with boukensha.tracing.tracer.start_as_current_span(
        "eval.trial",
        attributes={k: v for k, v in {
            "eval.scenario": args.scenario,
            "eval.backend": args.backend,
            "eval.model": args.model,
            "eval.max_reprompts": args.max_reprompts,
        }.items() if v is not None},
    ) as span:
        ctx = span.get_span_context()
        if ctx.is_valid:  # invalid/all-zero when tracing is off — nothing to report
            trace_id_hex = format(ctx.trace_id, "032x")

        try:
            boukensha.run_reprompted(
                task=args.task,
                max_reprompts=args.max_reprompts,
                backend=args.backend,
                model=args.model,
                working_dir=args.working_dir,
                log=args.log,
                block=_capture_registry_and_disable_save(captured),
            )
        except Exception as e:  # noqa: BLE001 — reported to the adapter via stderr, not re-raised
            span.record_exception(e)
            span.set_status(otel_trace.Status(otel_trace.StatusCode.ERROR, str(e)))
            print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            exit_code = 1

    # One last `look` after the trial ends (success, failure, or a caught
    # exception — just not a timeout kill, which SIGKILLs before this ever
    # runs) so the eval result records exactly which room the trial left the
    # character in. `look`'s own guard() returns a plain "error: not
    # connected" string rather than raising if mud_connect() never succeeded,
    # so this is safe to attempt unconditionally whenever mud tools were
    # registered at all.
    final_room = None
    registry = captured.get("registry")
    if registry is not None:
        try:
            final_room = registry.dispatch("look", {})
        except Exception:  # noqa: BLE001 — best-effort, never worth failing the trial over
            final_room = None

    # BatchSpanProcessor exports asynchronously (default ~5s schedule) — this
    # subprocess exits right after this function returns, so without an
    # explicit flush the last batch (very possibly including the span above)
    # can be silently dropped. force_flush is a no-op on the default no-op
    # provider (tracing off), safe either way.
    provider = otel_trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()

    # Both parsed by boukensha_agent.py out of captured stdout. Base64 for
    # final_room since it's multi-line free text (room name + description) —
    # keeps it on one stdout line like TRACE_ID, rather than needing a
    # multi-line-aware parser.
    if trace_id_hex:
        print(f"TRACE_ID={trace_id_hex}")
    if final_room:
        print(f"FINAL_ROOM_B64={base64.b64encode(final_room.encode()).decode()}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
