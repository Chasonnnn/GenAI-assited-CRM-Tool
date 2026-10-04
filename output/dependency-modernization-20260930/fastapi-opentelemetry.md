# FastAPI OpenTelemetry adoption

Audit date: 2026-09-30. Source revision: `595bf5b7`. Proposal only; no application changes, environment installation, collector activation, or live configuration verification.

## Decision

Defer native telemetry activation until exported-data redaction and provider shutdown have acceptance tests. The feature is useful: native spans separate dependency resolution, endpoint execution, serialization, and background tasks, and cover WebSocket connections. Dependency upgrades alone do not adopt it.

Implementing a disabled native configuration is bounded. Replacing the existing enabled pipeline requires a coordinated FastAPI/OTel upgrade, explicit lifecycle ownership, and redaction across server, client, and database instrumentation. Keeping the existing gate off prevents external activation, but does not prove the enabled path is safe.

## Verified versions and contracts

| Component | Declared, locked, installed | Candidate | Coupling |
|---|---|---|---|
| FastAPI | 0.136.3 | 0.142.2 | Native telemetry arrived in 0.142.0; candidate requires OTel API >=1.44.0 |
| OTel API / SDK / OTLP exporter family | 1.39.1 | 1.45.0 | SDK pins API and semantic conventions; resolve as one family |
| OTel instrumentation family | 0.60b1 | 0.66b0 | Keep HTTPX, Requests, SQLAlchemy and required instrumentation transitives aligned |

The current SDK pins API 1.39.1 and semantic conventions 0.60b1, so upgrading FastAPI alone conflicts with the lock. FastAPI 0.137 also changed included-router internals. Contrib instrumentation 0.64b0 fixed route resolution for that change. Existing API, OpenAPI, router dependency, authentication, CSRF, and negative tenant tests remain upgrade gates.

Sources: [FastAPI releases](https://fastapi.tiangolo.com/release-notes/#01422), [FastAPI 0.142.2 manifest](https://raw.githubusercontent.com/fastapi/fastapi/0.142.2/pyproject.toml), [SDK registry](https://pypi.org/project/opentelemetry-sdk/), [instrumentation registry](https://pypi.org/project/opentelemetry-instrumentation-fastapi/), [contrib router fix](https://github.com/open-telemetry/opentelemetry-python-contrib/releases/tag/v0.64b0).

## Current pipeline

- `apps/api/app/core/telemetry.py:37` requires `OTEL_ENABLED` and a nonempty endpoint, creates a `ParentBased(TraceIdRatioBased(...))` provider, adds one HTTP trace exporter, and instruments FastAPI, SQLAlchemy, HTTPX and Requests.
- `apps/api/app/main.py:271` initializes it during import. The application lifespan does not explicitly flush or shut down this provider.
- `apps/api/app/worker_service.py:51` has its own FastAPI app and no telemetry setup. Worker jobs have no request-to-job trace propagation.
- `apps/api/app/core/config.py:288` and `.env.example:288` default tracing off. No OTel meter or logger provider is configured.
- `infra/terraform/locals.tf:26` declares GCP monitoring but no OTel endpoint, enable flag, or exporter secret. Live production OTel state is unknown.

## Proposed API wiring

Use the verified public FastAPI 0.142.2 constructor and the existing provider/exporter concepts. This excerpt specifies wiring; provider ownership and redaction are required implementation work.

```python
from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

enabled = settings.OTEL_ENABLED and bool(settings.OTEL_EXPORTER_OTLP_ENDPOINT)
provider = None
if enabled:
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.OTEL_SERVICE_NAME}),
        sampler=ParentBased(TraceIdRatioBased(settings.OTEL_SAMPLE_RATE)),
    )
    exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        headers=_parse_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
    )
    # Attach this exporter only after the redaction contract below is implemented.
    provider.add_span_processor(BatchSpanProcessor(exporter))

app = FastAPI(
    lifespan=lifespan,
    telemetry={
        "tracer_provider": provider,
        "tracing": enabled,
        "operation_spans": enabled,
        "metrics": False,
        "logs": False,
        "auto_configure": False,
        "exclude": lambda scope: scope.get("path") in {
            "/healthz", "/readyz", "/health/live", "/health/ready", "/health",
        },
    },
)
```

Preserve the existing environment resource attribute and service-name fallback when implementing the factory. Pass the same explicit provider to SQLAlchemy, HTTPX and Requests if their existing tracing is retained; do not add a second provider/exporter. Remove `FastAPIInstrumentor.instrument_app` and its direct package dependency when native tracing owns API requests.

Use this explicit configuration on the worker health app during the upgrade:

```python
app = FastAPI(
    lifespan=lifespan,
    telemetry={
        "tracing": False,
        "operation_spans": False,
        "metrics": False,
        "logs": False,
        "auto_configure": False,
    },
)
```

Native automatic setup reads endpoint environment variables independently of the custom `OTEL_ENABLED` setting. `auto_configure=False` is necessary on both apps. Native FastAPI detects legacy OTel middleware, but automatic setup can still add exporters to configured providers. Explicit ownership prevents duplicate destinations.

Sources: [FastAPI guide](https://fastapi.tiangolo.com/advanced/opentelemetry/), [constructor](https://raw.githubusercontent.com/fastapi/fastapi/0.142.2/fastapi/applications.py), [configuration type](https://raw.githubusercontent.com/fastapi/fastapi/0.142.2/fastapi/telemetry/_api.py), [automatic setup](https://raw.githubusercontent.com/fastapi/fastapi/0.142.2/fastapi/telemetry/_runtime.py).

## Redaction gate

Use route templates and fixed operation identifiers for diagnostics. Remove raw URLs, query strings, token-bearing paths, SQL text, parameters, exception messages and stack traces from exported telemetry. Apply this to attributes, span names, events, status descriptions, links and resource attributes; a header-only filter is insufficient.

Required cases:

- Server attributes: `url.path`, `url.query`, `url.full`, `http.url`, `http.target`, and captured request/response headers. Native FastAPI records raw path/query; its cloud-signature redaction does not cover CRM search or OAuth values.
- Token-bearing paths: tracking open/click, unsubscribe, public messaging consent, and booking self-service management/reschedule/cancel. Matched route templates may remain; unmatched token paths must not survive through fallback values.
- Query data: OAuth `code`/`state`, search `q`, surrogate filters, export tokens, and signed provider URLs.
- Client spans: HTTPX and Requests URL attributes plus exception events and status descriptions. Provider credentials, body contents, and authorization/cookie headers must never be exported.
- Database spans: `db.statement`, `db.query.text`, connection strings and parameter values. SQLAlchemy `hide_parameters=True` does not suppress OTel statement attributes; inline SQL literals remain sensitive.
- Native logs remain disabled. Do not export `get_telemetry_data()` request bodies, arguments or validation inputs. Tenant labels, if later approved, derive only from authenticated membership or validated token-bound resources.

A public custom `Sampler` can remove initial native URL attributes by returning a filtered `SamplingResult`; SDK 1.45 initializes span attributes from that result. It cannot remove SQL/client attributes or exception data added later. It is not a complete redaction solution for the existing pipeline.

Do not mutate private span fields, override private exporter methods, or depend on SDK `_on_ending`. `on_end` receives read-only spans, and SDK documentation discourages constructing `ReadableSpan` directly. Choose and test a supported application export transformation or an approved collector transformation before retaining the full enabled pipeline. Collector redaction alone permits raw data to leave the application and needs an explicit trust-boundary decision.

Sources: [native URL collection](https://raw.githubusercontent.com/fastapi/fastapi/0.142.2/fastapi/telemetry/_asgi.py), [SDK 1.45 trace API](https://raw.githubusercontent.com/open-telemetry/opentelemetry-python/v1.45.0/opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py), [sampling API](https://raw.githubusercontent.com/open-telemetry/opentelemetry-python/v1.45.0/opentelemetry-sdk/src/opentelemetry/sdk/trace/sampling.py).

## Endpoint and lifecycle gate

The existing `OTLPSpanExporter(endpoint=...)` contract uses the full trace signal URL, including `/v1/traces`. The linked FastAPI guide uses a base endpoint and appends the signal path. Preserve the current explicit endpoint contract and document it. A base-URL migration requires a distinct setting or an explicit migration of operator values.

Application-created providers remain application-owned. Store the provider handle, flush pending spans during lifespan shutdown off the event loop, and explicitly close instrumentation/exporter resources. Validate repeated startup/shutdown without duplicate processors or retained instrumentation. `force_flush(timeout_millis=...)` exposes a deadline; `TracerProvider.shutdown()` has no timeout parameter, so do not claim bounded shutdown solely from a timed flush.

Cloud Run API CPU defaults to request-only allocation (`variables.tf:394`); the worker defaults to continuously allocated CPU (`variables.tf:126`). Measure export behavior under the actual platform policy before changing CPU allocation. The worker currently allows seven seconds to drain jobs; telemetry must not consume that budget or revive work after shutdown.

## Acceptance tests

1. With `OTEL_ENABLED=False` and endpoint environment variables present, API and worker create no exporters, emit no telemetry, and make no collector requests.
2. With synthetic enabled settings and an in-memory exporter, one request produces exactly one server span plus expected dependency, endpoint and serialization spans; IDs and parent relationships remain valid.
3. BackgroundTasks remain in the request trace after the server response span ends. Normal WebSocket disconnects are not errors. Health routes produce no spans; adjacent routes still do.
4. Canary tokens, search terms, cookies, authorization values, PII bodies, exception text and inline SQL literals are absent from the complete exported representation, including names, status descriptions, events and resources. Exercise both matched and unmatched routes, server errors, SQL errors and outbound HTTP failures.
5. Retained HTTPX, Requests and SQLAlchemy spans use the same provider and parent correctly. Export failures do not expose endpoint credentials or provider messages in logs.
6. Startup failure, cancellation, normal shutdown and repeated lifespan runs release task-owned telemetry resources within the chosen budget. No duplicate exporter registration or global-provider warning occurs.
7. Run affected API suites, router/OpenAPI contracts, auth/CSRF and cross-organization negatives, worker lifecycle tests and Ruff. Record actual-library evidence separately from mocked wiring tests.

## Stages and activation

| Stage | Scope | Completion evidence |
|---|---|---|
| 1 | Resolve compatible FastAPI/OTel versions; explicitly disable native auto setup on both apps | Frozen lock, installed versions, affected suites green; external gate remains off |
| 2 | Implement native API spans, redaction and application-owned lifecycle | Acceptance tests above pass; no live collector calls |
| 3 | Operator-approved activation | Verified destination, full trace URL, secret handling, access/retention policy and runtime export behavior |

Metrics/log exporters, collector provisioning, Cloud Run CPU changes, per-tenant dashboards, and worker job tracing/propagation are infrastructure or product decisions. They are not prerequisites for local native trace tests and are not authorized by a version upgrade.
