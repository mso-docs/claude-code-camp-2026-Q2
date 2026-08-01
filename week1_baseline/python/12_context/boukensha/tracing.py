"""Opt-in OpenTelemetry tracing for the agent loop.

Wiring is gated entirely on OTEL_EXPORTER_OTLP_ENDPOINT: if it's unset,
configure() returns without touching the global tracer provider, and every
`tracer.start_as_current_span(...)` call elsewhere in the codebase becomes a
no-op (the OTel API hands back a no-op span when no provider has been
registered) — so instrumentation is always safe to leave in place even when
nobody has the collector stack running.

`tracer` is obtained once at import time via trace.get_tracer(), before
configure() may have run. That's intentional, not a bug: get_tracer() before
any provider is registered returns a proxy that defers to whatever provider
is registered later, per the OTel Python API's documented behavior — so
importers don't need to care about init order.
"""

from __future__ import annotations

import os

from opentelemetry import trace

_configured = False


def configure() -> None:
    """Wires a real OTLP exporter when OTEL_EXPORTER_OTLP_ENDPOINT is set.
    Safe to call more than once (e.g. from both run() and repl()) — only the
    first call takes effect."""
    global _configured
    if _configured:
        return
    _configured = True

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return

    # Imports deferred until actually needed — nothing under opentelemetry.sdk
    # is touched at all when tracing is off.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "boukensha-agent")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


tracer = trace.get_tracer("boukensha")
