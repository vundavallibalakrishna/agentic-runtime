"""OpenTelemetry bootstrap. Spec: docs/03-specs/18-observability-eval.md §1."""

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
from opentelemetry.sdk.trace.export import BatchSpanProcessor
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
    target, insecure = _grpc_target(current.otel_exporter_otlp_endpoint)
    sampler = ParentBased(TraceIdRatioBased(current.trace_sample_ratio))
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=target, insecure=insecure))
    )
    trace.set_tracer_provider(tracer_provider)
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=target, insecure=insecure))
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


def record_tool_call(*, tool: str, status: str) -> None:
    """GenAI span for one tool call. Arguments and results stay off the span."""
    span = trace.get_tracer("ar.genai").start_span("tool_call")
    span.set_attribute("gen_ai.operation.name", "execute_tool")
    span.set_attribute("gen_ai.tool.name", tool)
    span.set_attribute("gen_ai.tool.status", status)
    span.end()
