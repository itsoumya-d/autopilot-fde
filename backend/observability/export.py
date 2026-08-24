"""OTLP trace-export wiring, driven by environment configuration.

Completes the gen_ai.* story: spans exist without the observability extra
(structured no-ops); with the extra installed AND an OTLP endpoint configured,
this module wires a real TracerProvider at app startup:

    AUTOPILOT_OTEL_OTLP_ENDPOINT=http://collector:4318   (preferred)
    OTEL_EXPORTER_OTLP_ENDPOINT=...                      (standard fallback)
    AUTOPILOT_SERVICE_NAME=autopilot-fde                 (resource attribute)

Traces go to ``<endpoint>/v1/traces`` per OTLP/HTTP convention. Every failure
mode degrades to a disabled status dict — exporting must never break boot.
"""

from __future__ import annotations

import logging
from typing import Any

from .tracing import _TRACING_AVAILABLE

logger = logging.getLogger("autopilot.otel")

ENDPOINT_ENV = "AUTOPILOT_OTEL_OTLP_ENDPOINT"
STD_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
SERVICE_ENV = "AUTOPILOT_SERVICE_NAME"
DEFAULT_SERVICE = "autopilot-fde"


def resolve_endpoint() -> str | None:
    """Configured OTLP base endpoint, or None."""
    for env in (ENDPOINT_ENV, STD_ENDPOINT_ENV):
        value = os_getenv(env).strip()
        if value:
            return value.rstrip("/")
    return None


def os_getenv(key: str) -> str:
    import os

    return os.getenv(key, "")


def trace_url(base: str) -> str:
    """OTLP/HTTP traces path appended to a base endpoint."""
    return f"{base}/v1/traces" if not base.endswith("/v1/traces") else base


def _load_deps() -> Any | None:
    """Import the SDK/exporter surface; None when pieces are missing."""
    if not _TRACING_AVAILABLE:
        return None
    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        return SimpleDeps(
            TracerProvider=TracerProvider,
            BatchSpanProcessor=BatchSpanProcessor,
            OTLPSpanExporter=OTLPSpanExporter,
            Resource=Resource,
            trace=otel_trace,
        )
    except ImportError:  # pragma: no cover - optional extra absent
        return None


class SimpleDeps:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def configure_from_env(deps: Any | None = None) -> dict[str, Any]:
    """Wire the provider when possible; always return an honest status."""
    endpoint = resolve_endpoint()
    if not endpoint:
        return {"enabled": False, "reason": "no OTLP endpoint configured"}
    deps = deps or _load_deps()
    if deps is None:
        return {
            "enabled": False,
            "reason": ("opentelemetry extra not installed "
                       "(requirements-observability.txt)"),
        }

    service = os_getenv(SERVICE_ENV) or DEFAULT_SERVICE
    try:
        resource = deps.Resource.create({"service.name": service})
        provider = deps.TracerProvider(resource=resource)
        exporter = deps.OTLPSpanExporter(endpoint=trace_url(endpoint))
        provider.add_span_processor(deps.BatchSpanProcessor(exporter))
        already = getattr(deps.trace.get_tracer_provider(), "resource", None)
        if already is not None:  # a provider exists; add processor to it instead
            deps.trace.get_tracer_provider().add_span_processor(
                deps.BatchSpanProcessor(exporter))
            logger.info("OTel OTLP export attached to existing provider (%s)",
                        trace_url(endpoint))
        else:
            deps.trace.set_tracer_provider(provider)
            logger.info("OTel OTLP export enabled -> %s (service=%s)",
                        trace_url(endpoint), service)
        return {"enabled": True, "endpoint": trace_url(endpoint),
                "service": service}
    except Exception as error:  # noqa: BLE001 - telemetry never breaks boot
        logger.warning("OTel OTLP wiring failed: %s", error)
        return {"enabled": False, "reason": f"wiring error: {error}"}
