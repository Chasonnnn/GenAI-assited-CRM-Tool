"""Native tracing privacy and lifespan contracts using real SDK encoding."""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import httpx
import pytest
import requests
from fastapi import BackgroundTasks, FastAPI
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Link, SpanContext, TraceFlags, TraceState
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core import telemetry
from app.core.config import settings


def configured_settings(**overrides):
    config = settings.model_copy(deep=True)
    for key, value in {
        "OTEL_ENABLED": True,
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://collector.example/private-endpoint/v1/traces",
        "OTEL_EXPORTER_OTLP_HEADERS": SecretStr("authorization=collector-private-credential"),
        "OTEL_SAMPLE_RATE": 1.0,
        "OTEL_EXPORT_TIMEOUT_SECONDS": 0.1,
        "OTEL_SHUTDOWN_TIMEOUT_SECONDS": 0.3,
        **overrides,
    }.items():
        setattr(config, key, value)
    return config


@pytest.fixture
def collector(monkeypatch):
    payloads = []
    clients = []
    client_type = httpx.AsyncClient

    async def respond(request):
        assert request.url.path == "/private-endpoint/v1/traces"
        assert request.headers["authorization"] == "collector-private-credential"
        payloads.append(ExportTraceServiceRequest.FromString(request.content))
        return httpx.Response(200)

    def create_client(**kwargs):
        client = client_type(transport=httpx.MockTransport(respond), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(telemetry, "AsyncClient", create_client)
    return payloads, clients


def exported_spans(payloads):
    return [
        span
        for payload in payloads
        for resource in payload.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    ]


@asynccontextmanager
async def running_app(app):
    messages = asyncio.Queue()
    messages.put_nowait({"type": "lifespan.startup"})
    ready = asyncio.Event()

    async def send(message):
        if message["type"] == "lifespan.startup.complete":
            ready.set()
        elif message["type"].endswith(".failed"):
            raise RuntimeError(message.get("message", "Application lifespan failed"))

    task = asyncio.create_task(
        app({"type": "lifespan", "asgi": {"version": "3.0"}}, messages.get, send)
    )
    started = asyncio.create_task(ready.wait())
    try:
        done, _ = await asyncio.wait(
            {task, started}, timeout=2, return_when=asyncio.FIRST_COMPLETED
        )
        if task in done:
            await task
        assert ready.is_set(), "Application startup timed out"
        yield
    finally:
        started.cancel()
        messages.put_nowait({"type": "lifespan.shutdown"})
        await task


@pytest.mark.asyncio
async def test_native_operations_and_all_child_instrumentors_export_without_private_data(
    collector, caplog, monkeypatch
):
    payloads, clients = collector
    engine = create_engine("sqlite://")
    manager = telemetry.TelemetryManager(configured_settings(), engine)
    app = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)
    client_type = httpx.AsyncClient
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    metric_reader = InMemoryMetricReader()
    external_metrics = MeterProvider(metric_readers=[metric_reader])
    monkeypatch.setattr(metrics, "get_meter_provider", lambda: external_metrics)
    monkeypatch.setenv("OTEL_PYTHON_SDK_INTERNAL_METRICS_ENABLED", "true")

    @app.get("/records/{token}")
    async def record(token: str, background: BackgroundTasks):
        with engine.connect() as connection:
            connection.execute(text("SELECT 'private-sql-literal'"))
        async with client_type(
            transport=httpx.MockTransport(lambda _: httpx.Response(200))
        ) as outgoing:
            HTTPXClientInstrumentor.instrument_client(
                outgoing, tracer_provider=manager, meter_provider=metrics.NoOpMeterProvider()
            )
            try:
                await outgoing.get(
                    "https://provider.example/private-outbound-path?q=private-search"
                )
            finally:
                HTTPXClientInstrumentor.uninstrument_client(outgoing)
        session = requests.Session()

        class Adapter(requests.adapters.BaseAdapter):
            def send(self, request, **kwargs):
                response = requests.Response()
                response.status_code = 200
                response._content = b"synthetic"
                return response

            def close(self):
                pass

        session.mount("https://", Adapter())
        with session:
            session.get("https://provider.example/private-requests-token?q=private-search")
        context = SpanContext(
            123, 456, False, TraceFlags.SAMPLED, TraceState([("secret", "private-state")])
        )
        with manager.get_tracer(
            "application-private-scope",
            instrumenting_library_version="private-scope-version",
            schema_url="https://private-scope-schema",
            attributes={"secret": "private-scope-attribute"},
        ).start_as_current_span(
            "private-span-name", links=[Link(context, {"secret": "private-link"})]
        ) as span:
            span.set_attribute("http.route", "/unregistered/{private-route}")
            span.set_attribute("private-canary-key", 2**100)
            span.set_attribute("private-surrogate", "private-value\ud800")
            span.record_exception(ValueError("private-exception"))
            span.set_status(trace.Status(trace.StatusCode.ERROR, "private-description"))
        background.add_task(lambda: None)
        return {"ok": True}

    caplog.set_level(logging.DEBUG, logger="httpx")
    async with running_app(app):
        async with client_type(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as incoming:
            response = await incoming.get(
                "/records/private-path-token?q=private-query",
                headers={
                    "traceparent": f"00-{trace_id}-00f067aa0ba902b7-01",
                    "tracestate": "secret=private-state",
                },
            )
        assert response.status_code == 200
    engine.dispose()

    spans = exported_spans(payloads)
    server = [span for span in spans if span.kind == 2]
    assert len(server) == 1
    assert server[0].name == "GET /records/{token}"
    assert server[0].trace_id.hex() == trace_id
    assert {
        "fastapi.dependencies",
        "fastapi.endpoint",
        "fastapi.serialization",
        "fastapi.background_task",
    } <= {span.name for span in spans}
    scopes = {
        scope.scope.name
        for payload in payloads
        for resource in payload.resource_spans
        for scope in resource.scope_spans
    }
    assert {
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.sqlalchemy",
    } <= scopes
    assert all(span.trace_id.hex() == trace_id for span in spans)
    wire = b"".join(payload.SerializeToString() for payload in payloads)
    assert b"private-" not in wire
    assert all(client.is_closed for client in clients)
    collector_logs = [
        record.getMessage()
        for record in caplog.records
        if "collector.example" in record.getMessage()
    ]
    assert collector_logs == []
    assert "private-canary" not in caplog.text
    assert "private-surrogate" not in caplog.text
    assert metric_reader.get_metrics_data() is None
    external_metrics.shutdown()


@pytest.mark.asyncio
async def test_disabled_apps_ignore_environment_and_external_global_provider(
    monkeypatch, collector
):
    payloads, clients = collector
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://unused.example")
    external = TracerProvider()
    external_exporter = InMemorySpanExporter()
    external.add_span_processor(SimpleSpanProcessor(external_exporter))
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: external)
    engine = create_engine("sqlite://")
    manager = telemetry.TelemetryManager(configured_settings(OTEL_ENABLED=False), engine)
    app = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)

    @app.get("/test")
    async def endpoint():
        return {"ok": True}

    async with running_app(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            assert (await client.get("/test")).status_code == 200
    from app import worker_service

    monkeypatch.setattr(worker_service, "_sync_clamav_signatures", lambda: None)
    monkeypatch.setattr(worker_service, "_ensure_attachment_scanner_available", lambda: None)

    async def worker_loop(stop_event):
        await stop_event.wait()

    monkeypatch.setattr(worker_service, "worker_loop", worker_loop)
    async with running_app(worker_service.app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(worker_service.app), base_url="http://test"
        ) as client:
            assert (await client.get("/health")).status_code == 200
    assert external_exporter.get_finished_spans() == ()
    assert payloads == []
    assert clients == []
    external.shutdown()
    engine.dispose()


@pytest.mark.asyncio
async def test_health_unmatched_paths_and_repeated_lifespans(collector):
    payloads, clients = collector
    engine = create_engine("sqlite://", poolclass=NullPool)
    manager = telemetry.TelemetryManager(configured_settings(), engine)
    app = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)

    app.add_middleware(telemetry.HealthTelemetryMiddleware)

    @app.get("/health/live")
    def health_endpoint():
        with engine.connect() as connection:
            connection.execute(text("SELECT 'private-health-sql'"))
        return {"ok": True}

    @app.get("/health/live-extra")
    async def endpoint():
        return {"ok": True}

    @app.get("/threaded")
    def threaded():
        with engine.connect() as connection:
            connection.execute(text("SELECT 'private-thread-sql'"))
        return {"ok": True}

    for _ in range(2):
        async with running_app(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                await client.get("/health/live")
                await client.get("/health/live-extra")
                await client.get("/private-unmatched-token")
                await client.get("/threaded")
    spans = exported_spans(payloads)
    assert [span.name for span in spans if span.kind == 2].count("GET /health/live-extra") == 2
    assert sum(span.kind == 2 for span in spans) == 6
    assert sum(span.name == "SQL" for span in spans) == 4  # connect and query, once per lifespan
    assert b"private-unmatched-token" not in b"".join(
        payload.SerializeToString() for payload in payloads
    )
    assert len(clients) == 2 and all(client.is_closed for client in clients)
    engine.dispose()


@pytest.mark.asyncio
async def test_startup_failure_closes_resources_and_allows_fresh_lifespan(collector):
    payloads, clients = collector
    engine = create_engine("sqlite://")
    manager = telemetry.TelemetryManager(configured_settings(), engine)

    @asynccontextmanager
    async def failed_startup(app):
        async with manager.lifespan(app):
            raise RuntimeError("Application startup failed")
            yield

    app = FastAPI(lifespan=failed_startup, telemetry=manager.native_config)
    with pytest.raises(RuntimeError):
        async with running_app(app):
            pass
    assert len(clients) == 1 and clients[0].is_closed
    recovered = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)
    async with running_app(recovered):
        with manager.get_tracer("test").start_as_current_span("recovered"):
            pass
    assert len(exported_spans(payloads)) == 1
    assert len(clients) == 2 and all(client.is_closed for client in clients)
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["response", "network", "header", "endpoint"])
async def test_collector_failures_never_expose_credentials_or_provider_bodies(
    failure, monkeypatch, caplog
):
    client_type = httpx.AsyncClient
    clients = []

    async def respond(request):
        if failure == "network":
            raise httpx.ConnectError("private-network-body", request=request)
        return httpx.Response(503, text="private-provider-body")

    def create_client(**kwargs):
        client = client_type(transport=httpx.MockTransport(respond), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(telemetry, "AsyncClient", create_client)
    config = configured_settings()
    if failure == "header":
        config.OTEL_EXPORTER_OTLP_HEADERS = SecretStr("authorization=private-credential-\u00e9")
    if failure == "endpoint":
        config.OTEL_EXPORTER_OTLP_ENDPOINT = "https://[private-invalid-host/v1/traces"
    engine = create_engine("sqlite://")
    manager = telemetry.TelemetryManager(config, engine)
    app = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)
    caplog.set_level(logging.DEBUG, logger="httpx")
    if failure in {"header", "endpoint"}:
        with pytest.raises(RuntimeError) as error:
            async with running_app(app):
                pass
        assert "private-" not in str(error.value)
    else:
        async with running_app(app):
            with manager.get_tracer("test").start_as_current_span("synthetic"):
                pass
        assert "Telemetry export failed" in caplog.text
    assert "private-" not in caplog.text
    assert "collector.example" not in caplog.text
    assert all(client.is_closed for client in clients)
    engine.dispose()


@pytest.mark.asyncio
async def test_shutdown_cancels_blocked_collector_and_closes_transport(monkeypatch, caplog):
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    clients = []
    client_type = httpx.AsyncClient

    async def blocked(_):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    def create_client(**kwargs):
        client = client_type(transport=httpx.MockTransport(blocked), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(telemetry, "AsyncClient", create_client)
    engine = create_engine("sqlite://")
    manager = telemetry.TelemetryManager(
        configured_settings(OTEL_EXPORT_TIMEOUT_SECONDS=5, OTEL_SHUTDOWN_TIMEOUT_SECONDS=0.05),
        engine,
    )
    app = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)
    lifecycle = running_app(app)
    await lifecycle.__aenter__()
    with manager.get_tracer("test").start_as_current_span("synthetic"):
        pass
    await asyncio.wait_for(entered.wait(), timeout=2)
    await asyncio.wait_for(lifecycle.__aexit__(None, None, None), timeout=0.5)
    assert cancelled.is_set()
    assert all(client.is_closed for client in clients)
    assert "Telemetry shutdown deadline reached" in caplog.text
    engine.dispose()


def test_sampling_configuration_rejects_out_of_range_values():
    for value in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            configured_settings(OTEL_SAMPLE_RATE=value)


@pytest.mark.asyncio
async def test_queue_saturation_and_late_spans_do_not_survive_lifespan_restart(
    collector, caplog, monkeypatch
):
    payloads, clients = collector
    engine = create_engine("sqlite://")
    manager = telemetry.TelemetryManager(configured_settings(), engine)
    app = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)
    async with running_app(app):
        tracer = manager.get_tracer("test")
        late = tracer.start_span("private-late-span")
        # Block the loop while a worker bursts spans: payloads and scheduled wakeups stay bounded.
        loop = asyncio.get_running_loop()
        scheduled = []
        original_schedule = loop.call_soon_threadsafe

        def schedule(*args, **kwargs):
            scheduled.append(None)
            return original_schedule(*args, **kwargs)

        def burst():
            for _ in range(300):
                with tracer.start_as_current_span("synthetic"):
                    pass

        with monkeypatch.context() as scoped:
            scoped.setattr(loop, "call_soon_threadsafe", schedule)
            worker = threading.Thread(target=burst)
            worker.start()
            worker.join(timeout=2)
            assert not worker.is_alive()
        assert len(scheduled) <= 1
    first = exported_spans(payloads)
    assert 0 < len(first) <= 256
    assert "Telemetry queue full; span dropped" in caplog.text
    assert (
        sum(
            record.getMessage() == "Telemetry queue full; span dropped" for record in caplog.records
        )
        == 1
    )
    async with running_app(app):
        late.end()
        with manager.get_tracer("test").start_as_current_span("fresh"):
            pass
    all_spans = exported_spans(payloads)
    assert len(all_spans) == len(first) + 1
    late_id = late.get_span_context().span_id.to_bytes(8, "big")
    assert all(span.span_id != late_id for span in all_spans)
    assert len(clients) == 2 and all(client.is_closed for client in clients)
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.request_metrics
async def test_health_metrics_executor_writes_sql_without_exporting_health_spans(
    collector, monkeypatch, db_engine
):
    from app import main
    from app.db.models import RequestMetricsRollup

    payloads, clients = collector
    engine = create_engine(db_engine.url, poolclass=NullPool, hide_parameters=True)
    sessions = sessionmaker(bind=engine)
    manager = telemetry.TelemetryManager(configured_settings(), engine)
    app = FastAPI(lifespan=manager.lifespan, telemetry=manager.native_config)
    app.middleware("http")(main.metrics_middleware)
    app.add_middleware(telemetry.HealthTelemetryMiddleware)
    routes = ("/health/ready", "/telemetry-metrics-positive")

    @app.get(routes[0])
    @app.get(routes[1])
    async def endpoint():
        return {"ok": True}

    with sessions() as db:
        before = {
            row.route: row.request_count
            for row in db.scalars(
                select(RequestMetricsRollup).where(RequestMetricsRollup.route.in_(routes))
            )
        }
    executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(main, "telemetry", manager)
    monkeypatch.setattr(main, "MetricsSessionLocal", sessions)
    monkeypatch.setattr(main, "_metrics_executor", executor)
    monkeypatch.setattr(main, "_metrics_capacity", threading.BoundedSemaphore(1))
    try:
        for index, path in enumerate(routes):
            async with running_app(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app), base_url="http://test"
                ) as client:
                    assert (await client.get(path)).status_code == 200
                # A FIFO barrier proves the real raw executor write has finished before shutdown.
                await asyncio.wrap_future(executor.submit(lambda: None))
            if index == 0:
                assert exported_spans(payloads) == []
        assert any(span.name == "SQL" for span in exported_spans(payloads))
        with sessions() as db:
            rows = list(
                db.scalars(
                    select(RequestMetricsRollup).where(RequestMetricsRollup.route.in_(routes))
                )
            )
            assert {row.route for row in rows} == set(routes)
            assert all(row.request_count == before.get(row.route, 0) + 1 for row in rows)
            for row in rows:
                if row.route not in before:
                    db.delete(row)
                else:
                    row.request_count -= 1
                    row.status_2xx -= 1
            db.commit()
        assert len(clients) == 2 and all(client.is_closed for client in clients)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        engine.dispose()
