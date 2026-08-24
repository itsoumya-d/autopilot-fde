"""gen_ai.* observability for tool calls and agent lifecycle events.

Emits spans carrying the OpenTelemetry GenAI semantic conventions that became
the enterprise baseline in mid-2026:

    gen_ai.system            always "autopilot-fde"
    gen_ai.request.model     when the enrichment model is configured
    gen_ai.tool.name         every dispatched adapter call
    gen_ai.agent.id          the deployed branch responsible
    gen_ai.usage.input_tokens / output_tokens   when the caller knows them

Dependency policy: OpenTelemetry is an OPTIONAL extra
(``pip install -r requirements-observability.txt``). Without it, spans are
structured no-ops with the same surface, so instrumented code paths behave
identically and the core stays zero-dependency. Exporter wiring (OTLP/console)
belongs to the deployment, not to library code.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

GEN_AI_SYSTEM = "autopilot-fde"

try:  # optional extra; absence must never change behavior
    from opentelemetry import trace as _otel_trace

    _TRACING_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via flag flip in tests
    _otel_trace = None
    _TRACING_AVAILABLE = False


class _NoopSpan:
    """Duck-typed stand-in so callers never branch on tracing availability."""

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def set_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        return None

    def record_exception(self, exception: BaseException) -> None:
        return None


def tracer():
    """Return a real OTel tracer when installed, else a no-op factory."""
    if _TRACING_AVAILABLE:
        return _otel_trace.get_tracer("autopilot-fde")
    return _NoopTracer()


class _NoopTracer:
    @contextmanager
    def start_as_current_span(self, _name: str, **_kwargs) -> Iterator[_NoopSpan]:
        yield _NoopSpan()


def configured_model() -> str | None:
    """The enrichment model when LLM enhancement is configured."""
    if os.getenv("AUTOPILOT_LLM_ENHANCE", "0") != "1":
        return None
    return os.getenv("LLM_MODEL") or "unspecified"


@contextmanager
def tool_span(
    tool_name: str,
    *,
    step_name: str | None = None,
    agent_id: str | None = None,
) -> Iterator[Any]:
    """Span for one dispatched tool/adapter call.

    Yields a span-like object; ``span.set_token_usage(in, out)`` attaches
    gen_ai.usage.* attributes when the caller has real numbers. Exception
    recording is the caller's job (domain-aware); re-raised errors propagate.
    """
    span_name = f"autopilot.tool.{tool_name}"
    with tracer().start_as_current_span(span_name) as span:
        span.set_attribute("gen_ai.system", GEN_AI_SYSTEM)
        span.set_attribute("gen_ai.tool.name", tool_name)
        if step_name:
            span.set_attribute("autopilot.step.name", step_name)
        if agent_id:
            span.set_attribute("gen_ai.agent.id", agent_id)
        model = configured_model()
        if model:
            span.set_attribute("gen_ai.request.model", model)

        def set_token_usage(input_tokens: int, output_tokens: int) -> None:
            span.set_attribute("gen_ai.usage.input_tokens", int(input_tokens))
            span.set_attribute("gen_ai.usage.output_tokens", int(output_tokens))

        span.set_token_usage = set_token_usage  # type: ignore[method-assign]
        yield span
