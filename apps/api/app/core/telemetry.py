"""Application-owned tracing with a privacy boundary before OTLP export."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from contextlib import asynccontextmanager, nullcontext, suppress
from contextvars import ContextVar
from urllib.parse import urlsplit

from httpx import AsyncClient
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

logger = logging.getLogger(__name__)
_exporting = ContextVar("telemetry_exporting", default=False)
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT", "TRACE"}
_OPERATIONS = {
    "fastapi.dependencies",
    "fastapi.endpoint",
    "fastapi.serialization",
    "fastapi.background_task",
}
_SCOPES = {
    "fastapi",
    "opentelemetry.instrumentation.httpx",
    "opentelemetry.instrumentation.requests",
    "opentelemetry.instrumentation.sqlalchemy",
}
_HEALTH = {"/health", "/healthz", "/readyz", "/health/live", "/health/ready"}


class HealthTelemetryMiddleware:
    """Exclude exact health paths from child instrumentation as well as native tracing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") in _HEALTH:
            with suppress_instrumentation():
                await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


class _ExportLogFilter(logging.Filter):
    def filter(self, record):
        # HTTPX logs complete collector URLs; suppress only this export task's transport logs.
        return not _exporting.get()


def _parse_headers(value: str) -> dict[str, str]:
    return {
        key.strip(): val.strip()
        for item in value.split(",")
        if "=" in item
        for key, val in [item.split("=", 1)]
        if key.strip()
    }


def _sanitize(payload, routes: frozenset[str], resource_attributes: dict[str, str]):
    """Allow only fixed names, registered templates, enums, IDs and timing fields."""
    for resource in payload.resource_spans:
        resource.schema_url = ""
        resource.resource.Clear()
        for key, value in resource_attributes.items():
            item = resource.resource.attributes.add(key=key)
            item.value.string_value = value
        for scope in resource.scope_spans:
            scope.schema_url = ""
            name = scope.scope.name
            scope.scope.Clear()
            scope.scope.name = name if name in _SCOPES else "application"
            for span in scope.spans:
                attributes = {item.key: item.value for item in span.attributes}
                method = attributes.get("http.request.method") or attributes.get("http.method")
                method = (
                    method.string_value if method and method.string_value in _METHODS else "HTTP"
                )
                route = attributes.get("http.route")
                route = route.string_value if route and route.string_value in routes else ""
                kept = []
                if route:
                    kept.append(("http.route", route))
                if method != "HTTP":
                    kept.append(("http.request.method", method))
                for key in ("http.response.status_code", "http.status_code"):
                    value = attributes.get(key)
                    if (
                        value
                        and value.WhichOneof("value") == "int_value"
                        and 100 <= value.int_value <= 599
                    ):
                        kept.append(("http.response.status_code", value.int_value))
                        break
                system = attributes.get("db.system") or attributes.get("db.system.name")
                if system and system.string_value in {
                    "postgresql",
                    "sqlite",
                    "mysql",
                    "mssql",
                    "oracle",
                }:
                    kept.append(("db.system", system.string_value))
                if span.kind == 2:
                    span.name = f"{method} {route}".rstrip()
                elif name == "fastapi" and span.name in _OPERATIONS:
                    pass
                elif name == "opentelemetry.instrumentation.sqlalchemy":
                    span.name = "SQL"
                elif name in {
                    "opentelemetry.instrumentation.httpx",
                    "opentelemetry.instrumentation.requests",
                }:
                    span.name = method
                else:
                    span.name = "operation"
                del span.attributes[:]
                for key, value in kept:
                    item = span.attributes.add(key=key)
                    if isinstance(value, int):
                        item.value.int_value = value
                    else:
                        item.value.string_value = value
                span.trace_state = ""
                span.status.message = ""
                del span.events[:]
                for link in span.links:
                    link.trace_state = ""
                    del link.attributes[:]
    return payload


class _ExportProcessor(SpanProcessor):
    """Encode through the public API; retain only sanitized, bounded queue entries."""

    def __init__(self, routes, resource_attributes, endpoint, headers, export_timeout):
        self.routes = routes
        self.resource_attributes = resource_attributes
        self.endpoint = endpoint
        self.export_timeout = export_timeout
        self.loop = asyncio.get_running_loop()
        self.queue = queue.Queue(maxsize=256)
        self.lock = threading.Lock()
        self.accepting = True
        self.queue_warning_reported = False
        self.wake_pending = False
        self.wake = asyncio.Event()
        self.client = AsyncClient(
            headers={**headers, "content-type": "application/x-protobuf"},
            timeout=export_timeout,
            trust_env=False,
            follow_redirects=False,
        )
        self.task = asyncio.create_task(self._run())

    def on_end(self, span):
        if not self.accepting:
            return
        token = _exporting.set(True)
        try:
            payload = _sanitize(encode_spans([span]), self.routes, self.resource_attributes)
            with self.lock:
                if not self.accepting:
                    return
                self.queue.put_nowait(payload)
                if not self.wake_pending:
                    self.wake_pending = True
                    self.loop.call_soon_threadsafe(self._notify)
        except queue.Full:
            with self.lock:
                if self.queue_warning_reported:
                    return
                self.queue_warning_reported = True
            logger.warning("Telemetry queue full; span dropped")
        except Exception:
            logger.warning("Telemetry encoding failed; span dropped")
        finally:
            _exporting.reset(token)

    def _notify(self):
        with self.lock:
            self.wake_pending = False
        self.wake.set()

    async def _run(self):
        while self.accepting or not self.queue.empty():
            await self.wake.wait()
            self.wake.clear()
            while not self.queue.empty():
                batch = ExportTraceServiceRequest()
                for _ in range(128):
                    try:
                        batch.MergeFrom(self.queue.get_nowait())
                    except queue.Empty:
                        break
                await self._send(batch.SerializeToString())

    async def _send(self, content):
        token = _exporting.set(True)
        try:
            with suppress_instrumentation():
                # A total deadline also covers streaming response closure. No provider body is read.
                async with asyncio.timeout(self.export_timeout):
                    async with self.client.stream(
                        "POST", self.endpoint, content=content
                    ) as response:
                        if not 200 <= response.status_code < 300:
                            logger.warning("Telemetry export failed")
        except Exception:
            logger.warning("Telemetry export failed")
        finally:
            _exporting.reset(token)

    async def close(self, timeout):
        deadline = self.loop.time() + timeout
        with self.lock:
            self.accepting = False
        self.wake.set()
        try:
            async with asyncio.timeout(timeout):
                await self.task
        except TimeoutError:
            logger.warning("Telemetry shutdown deadline reached")
        finally:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            try:
                async with asyncio.timeout(max(0.001, deadline - self.loop.time())):
                    await self.client.aclose()
            except Exception:
                logger.warning("Telemetry transport closure failed")
            while not self.queue.empty():
                self.queue.get_nowait()

    def shutdown(self):
        self.accepting = False


class TelemetryManager(trace.TracerProvider):
    """Stable public provider facade; each lifespan owns a fresh SDK and transport."""

    def __init__(self, settings, engine, websocket_routes=()):
        self.settings = settings
        self.engine = engine
        self.websocket_routes = websocket_routes
        self.provider = None
        self.enabled = bool(settings.OTEL_ENABLED and settings.OTEL_EXPORTER_OTLP_ENDPOINT)

    @property
    def native_config(self):
        return {
            "tracer_provider": self,
            "tracing": self.enabled,
            "operation_spans": self.enabled,
            "logs": False,
            "metrics": False,
            "auto_configure": False,
            "exclude": lambda scope: scope.get("path") in _HEALTH,
        }

    def get_tracer(self, *args, **kwargs):
        provider = self.provider or trace.NoOpTracerProvider()
        return provider.get_tracer(*args, **kwargs)

    def suppress_health(self, path):
        """Raw executor workers must enter suppression themselves; they do not copy context."""
        return suppress_instrumentation() if self.enabled and path in _HEALTH else nullcontext()

    @asynccontextmanager
    async def lifespan(self, app):
        if not self.enabled:
            yield
            return
        if self.provider is not None:
            raise RuntimeError("Telemetry lifespan already active")
        try:
            endpoint = urlsplit(self.settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        except ValueError:
            raise ValueError("Telemetry endpoint is invalid") from None
        if (
            endpoint.scheme not in {"http", "https"}
            or not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError(
                "Telemetry endpoint must be an HTTP URL without credentials, query or fragment"
            )
        resource_attributes = {
            "service.name": self.settings.OTEL_SERVICE_NAME
            or self.settings.GCP_SERVICE_NAME
            or "crm-api",
            "deployment.environment": self.settings.ENV,
        }
        provider = TracerProvider(
            resource=Resource(resource_attributes),
            sampler=ParentBased(TraceIdRatioBased(self.settings.OTEL_SAMPLE_RATE)),
            meter_provider=NoOpMeterProvider(),
            shutdown_on_exit=False,
        )
        processor = None
        instrumentors = []
        log_filter = _ExportLogFilter()
        transport_loggers = [
            logging.getLogger(name)
            for name in (
                "httpx",
                "httpcore.connection",
                "httpcore.http11",
                "httpcore.http2",
                "httpcore.proxy",
                "httpcore.socks",
                "opentelemetry.exporter.otlp.proto.common._internal",
            )
        ]
        try:
            try:
                for transport_logger in transport_loggers:
                    transport_logger.addFilter(log_filter)
                routes = frozenset(app.openapi()["paths"]) | frozenset(self.websocket_routes)
                processor = _ExportProcessor(
                    routes,
                    resource_attributes,
                    self.settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                    _parse_headers(self.settings.OTEL_EXPORTER_OTLP_HEADERS.get_secret_value()),
                    self.settings.OTEL_EXPORT_TIMEOUT_SECONDS,
                )
                provider.add_span_processor(processor)
                self.provider = provider
                for instrumentor, kwargs in (
                    (SQLAlchemyInstrumentor(), {"engine": self.engine}),
                    (HTTPXClientInstrumentor(), {}),
                    (RequestsInstrumentor(), {}),
                ):
                    if instrumentor.is_instrumented_by_opentelemetry:
                        raise RuntimeError(
                            "Telemetry instrumentor is already owned by another provider"
                        )
                    instrumentor.instrument(
                        tracer_provider=provider, meter_provider=NoOpMeterProvider(), **kwargs
                    )
                    instrumentors.append(instrumentor)
            except Exception:
                raise RuntimeError("Telemetry initialization failed") from None
            yield
        finally:
            self.provider = None
            for instrumentor in reversed(instrumentors):
                try:
                    instrumentor.uninstrument()
                except Exception:
                    logger.warning("Telemetry instrumentor cleanup failed")
            try:
                if processor:
                    await processor.close(self.settings.OTEL_SHUTDOWN_TIMEOUT_SECONDS)
            finally:
                provider.shutdown()
                for transport_logger in transport_loggers:
                    transport_logger.removeFilter(log_filter)
