"""
OTel skill tracer — singleton TracerProvider, two exported functions:
  trace_skill(...)       — wraps a callable in a span
  trace_skill_read(...)  — lightweight span for SKILL.md reads

If Jaeger is unreachable on startup, spans are written to telemetry_spans.json
in the project root instead. Telemetry is triggered directly inside each skill.
"""
from __future__ import annotations

import json
import os
import socket
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

_provider: TracerProvider | None = None
_session_id: str = str(uuid.uuid4())
_SPANS_FILE = Path(__file__).parent.parent / "telemetry_spans.json"


# ── File fallback exporter ────────────────────────────────────────────────────

def _span_to_dict(span: ReadableSpan) -> dict[str, Any]:
    return {
        "trace_id": format(span.context.trace_id, "032x"),
        "span_id": format(span.context.span_id, "016x"),
        "operation": span.name,
        "start_time_ms": (span.start_time or 0) // 1_000_000,
        "end_time_ms": (span.end_time or 0) // 1_000_000,
        "duration_ms": ((span.end_time or 0) - (span.start_time or 0)) / 1_000_000,
        "status": span.status.status_code.name,
        "attributes": dict(span.attributes or {}),
    }


class FileSpanExporter(SpanExporter):
    """Appends finished spans to a JSON array file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        existing: list[dict[str, Any]] = (
            json.loads(self._path.read_text()) if self._path.exists() else []
        )
        existing.extend(_span_to_dict(s) for s in spans)
        self._path.write_text(json.dumps(existing, indent=2))
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


# ── Connectivity probe ────────────────────────────────────────────────────────

def _is_jaeger_up(endpoint: str) -> bool:
    """Return True if a TCP connection to the OTLP endpoint succeeds."""
    try:
        host = endpoint.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(endpoint.rsplit(":", 1)[-1])
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


# ── Provider singleton ────────────────────────────────────────────────────────

def _get_provider() -> TracerProvider:
    global _provider
    if _provider is not None:
        return _provider

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": "claude-skills"})
    _provider = TracerProvider(resource=resource)

    if _is_jaeger_up(endpoint):
        exporter: SpanExporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        print(f"[otel] Jaeger reachable — exporting to {endpoint}")
    else:
        exporter = FileSpanExporter(_SPANS_FILE)
        print(f"[otel] Jaeger unreachable — writing spans to {_SPANS_FILE}")

    _provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(_provider)
    return _provider


def _tracer() -> trace.Tracer:
    return _get_provider().get_tracer("claude-skills")


# ── Public API ────────────────────────────────────────────────────────────────

def trace_skill(
    skill_name: str,
    skill_path: str,
    triggered_by: str,
    fn: Callable[[], Any],
    inputs: dict[str, Any] | None = None,
) -> Any:
    """Wrap fn in a span; capture status, duration_ms, response, and error."""
    result: Any = None
    error: Exception | None = None
    start = time.time()

    with _tracer().start_as_current_span(f"skill.{skill_name}") as span:
        span.set_attribute("skill.name", skill_name)
        span.set_attribute("skill.file_path", skill_path)
        span.set_attribute("skill.triggered_by", triggered_by)
        span.set_attribute("skill.session_id", _session_id)
        if inputs:
            span.set_attribute("skill.input", json.dumps(inputs))
        try:
            result = fn()
            span.set_attribute("skill.status", "ok")
            span.set_attribute("skill.duration_ms", (time.time() - start) * 1000)
            span.set_attribute("skill.response", str(result)[:1024])
            if isinstance(result, dict) and "message" in result:
                span.set_attribute("skill.llm_response", str(result["message"])[:1024])
        except Exception as exc:
            span.set_attribute("skill.status", "error")
            span.set_attribute("skill.duration_ms", (time.time() - start) * 1000)
            span.set_attribute("skill.error", str(exc))
            error = exc

    _get_provider().force_flush()

    if error is not None:
        raise error
    return result


def trace_skill_read(
    skill_name: str,
    skill_path: str,
    query: str,
    triggered: bool,
) -> None:
    """Lightweight span recording that a SKILL.md was read."""
    with _tracer().start_as_current_span(f"skill.read.{skill_name}") as span:
        span.set_attribute("skill.name", skill_name)
        span.set_attribute("skill.file_path", skill_path)
        span.set_attribute("skill.event", "read")
        span.set_attribute("skill.triggered", triggered)
        span.set_attribute("skill.session_id", _session_id)
        if query:
            span.set_attribute("skill.query", query)

    _get_provider().force_flush()
