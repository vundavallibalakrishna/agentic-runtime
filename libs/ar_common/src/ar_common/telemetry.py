"""OpenTelemetry bootstrap. Spec: docs/03-specs/18-observability-eval.md §1."""

import os
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from ar_common.logging import get_logger
from ar_common.settings import get_settings

try:
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
except ImportError:  # pragma: no cover - optional extra
    AsyncPGInstrumentor = None  # type: ignore[misc, assignment]
try:
    from opentelemetry.instrumentation.redis import RedisInstrumentor
except ImportError:  # pragma: no cover - optional extra
    RedisInstrumentor = None  # type: ignore[misc, assignment]
try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
except ImportError:  # pragma: no cover - optional extra
    SQLAlchemyInstrumentor = None  # type: ignore[misc, assignment]

if TYPE_CHECKING:
    from ar_common.settings import BaseServiceSettings


class _TelemetryState:
    ready = False


_log = get_logger(__name__)
_DISABLED = frozenset({"", "off", "none", "disabled"})
_EXPORT_TIMEOUT_S = 2.0
_QUEUE = 2048
# The exporter treats an empty retry set as "use the defaults". OK is never an
# export error, so naming it turns retries off without importing grpc here.
_NO_RETRY_ENV = "OTEL_PYTHON_EXPORTER_OTLP_GRPC_RETRYABLE_ERROR_CODES"


class _QuietSpans:
    """Export spans on the batch thread. A failure is dropped, never raised."""

    def __init__(self, inner: object) -> None:
        self._inner = inner

    def export(self, spans: object) -> SpanExportResult:
        try:
            result = self._inner.export(spans)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - a missing collector must not surface
            _log.info("telemetry_dropped", signal="traces")
            return SpanExportResult.FAILURE
        return result if isinstance(result, SpanExportResult) else SpanExportResult.FAILURE

    def shutdown(self) -> None:
        try:
            self._inner.shutdown()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - shutdown is best-effort
            return

    def force_flush(self, timeout_millis: int = 1000) -> bool:
        del timeout_millis
        return True


def _otel_channel(target: str, *, insecure: bool) -> tuple[str, tuple[tuple[str, str], ...] | None]:
    """Dial the approved address. TLS still checks the original hostname."""
    from ar_common.egress_http import approved_address  # noqa: PLC0415
    from ar_common.egress_policy import closed_egress  # noqa: PLC0415

    if not closed_egress():
        return target, None
    host, port = _split_host(target)
    dial = approved_address(host)
    shown = f"[{dial}]" if ":" in dial else dial
    endpoint = f"{shown}:{port}" if port else shown
    if insecure:
        return endpoint, None
    return endpoint, (("grpc.ssl_target_name_override", host),)


def _split_host(target: str) -> tuple[str, str]:
    """Host and port of a gRPC target. Bracketed IPv6 stays one host."""
    if target.startswith("["):
        host, _, rest = target[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
        return host, port
    if target.count(":") > 1:
        return target, ""
    host, separator, port = target.partition(":")
    return host, port if separator else ""


def _grpc_target(endpoint: str) -> tuple[str, bool]:
    insecure = endpoint.startswith("http://")
    target = endpoint.removeprefix("http://").removeprefix("https://").rstrip("/")
    return target, insecure


def setup(service_name: str, settings: BaseServiceSettings | None = None) -> None:
    """Configure tracers, meters and auto-instrumentation once per process."""
    if _TelemetryState.ready:
        return
    current = settings
    if current is None:
        current = get_settings()
    resource = Resource.create({"service.name": service_name})
    from ar_common.egress_policy import closed_egress, decide_url  # noqa: PLC0415

    if closed_egress():
        problem = decide_url(
            current.otel_exporter_otlp_endpoint, [], closed=True, check_private=False
        )
        if problem is not None:
            _log.info("telemetry_skipped", reason="egress_closed")
            _TelemetryState.ready = True
            return
        from ar_common.egress_http import EgressDenied, pinned_host  # noqa: PLC0415

        host = _grpc_target(current.otel_exporter_otlp_endpoint)[0].split("/")[0].split(":")[0]
        try:
            pinned_host(host)
        except EgressDenied:
            _log.info("telemetry_skipped", reason="egress_closed")
            _TelemetryState.ready = True
            return
        current_endpoint = current.otel_exporter_otlp_endpoint
    else:
        current_endpoint = current.otel_exporter_otlp_endpoint
    if current_endpoint.strip().lower() in _DISABLED:
        _log.info("telemetry_disabled", reason="no_endpoint")
        _TelemetryState.ready = True
        return
    os.environ[_NO_RETRY_ENV] = "OK"
    target, insecure = _grpc_target(current_endpoint)
    target, channel_options = _otel_channel(target, insecure=insecure)
    options = (
        ("grpc.enable_retries", 0),
        *(() if channel_options is None else channel_options),
    )
    sampler = ParentBased(TraceIdRatioBased(current.trace_sample_ratio))
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            _QuietSpans(
                OTLPSpanExporter(
                    endpoint=target,
                    insecure=insecure,
                    timeout=_EXPORT_TIMEOUT_S,
                    channel_options=options,  # type: ignore[arg-type]
                )
            ),
            max_queue_size=_QUEUE,
            schedule_delay_millis=500,
            max_export_batch_size=256,
            export_timeout_millis=int(_EXPORT_TIMEOUT_S * 1000),
        )
    )
    trace.set_tracer_provider(tracer_provider)
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=target,
            insecure=insecure,
            timeout=_EXPORT_TIMEOUT_S,
            channel_options=options,  # type: ignore[arg-type]
        ),
        export_interval_millis=60_000,
        export_timeout_millis=int(_EXPORT_TIMEOUT_S * 1000),
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    _instrument_optional()
    _TelemetryState.ready = True
    _log.info("telemetry_ready", service=service_name)


def _instrument_optional() -> None:
    _try_instrument("sqlalchemy", SQLAlchemyInstrumentor)
    _try_instrument("asyncpg", AsyncPGInstrumentor)
    _try_instrument("redis", RedisInstrumentor)


def _try_instrument(name: str, instrumentor: object) -> None:
    if instrumentor is None:
        _log.info("instrumentation_skipped", name=name)
        return
    try:
        instrumentor().instrument()  # type: ignore[operator]
    except Exception:  # noqa: BLE001 - optional instrumentors must not stop the process
        _log.info("instrumentation_skipped", name=name)


def reset_for_tests() -> None:
    """Allow a later ``setup`` call from a test."""
    _TelemetryState.ready = False


def record_model_call(*, model: str, tokens_in: int, tokens_out: int) -> None:
    """GenAI span for one model call. Message text is not an attribute."""
    span = trace.get_tracer("ar.genai").start_span("model_step")
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.request.model", model)
    span.set_attribute("gen_ai.usage.input_tokens", tokens_in)
    span.set_attribute("gen_ai.usage.output_tokens", tokens_out)
    span.end()


def record_run(run_id: str) -> str:
    """One span per run. The attribute is the run id. Prompts are not attached.

    Returns the trace id, or an empty string when the tracer has no context.
    """
    span = trace.get_tracer("ar.run").start_span("ar.run")
    span.set_attribute("ar.run_id", run_id)
    context = span.get_span_context()
    span.end()
    if context is None or not context.trace_id:
        return ""
    return format(context.trace_id, "032x")


def record_tool_call(*, tool: str, status: str) -> None:
    """GenAI span for one tool call. Arguments and results stay off the span."""
    span = trace.get_tracer("ar.genai").start_span("tool_call")
    span.set_attribute("gen_ai.operation.name", "execute_tool")
    span.set_attribute("gen_ai.tool.name", tool)
    span.set_attribute("gen_ai.tool.status", status)
    span.end()
