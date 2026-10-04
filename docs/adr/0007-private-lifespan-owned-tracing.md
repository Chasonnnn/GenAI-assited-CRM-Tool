# Private, lifespan-owned tracing

Date: 2026-10-01

Status: Accepted

## Decision

FastAPI 0.142.2 owns server and operation spans. The application owns its OpenTelemetry provider, outbound HTTP/database instrumentation, exporter transport and shutdown. The worker health app disables native telemetry. Both apps disable automatic configuration, native logs and native metrics; the SDK and outbound instrumentors receive a no-op meter provider. Exact health paths also suppress child instrumentation, including readiness database queries.

Health suppression surrounds all request middleware and is entered explicitly inside the request-metrics worker thread. Metric writes remain intact. The worker does not copy authenticated request context variables merely to control tracing.

Tracing remains enabled only when `OTEL_ENABLED` and `OTEL_EXPORTER_OTLP_ENDPOINT` are configured. The endpoint remains a complete OTLP/HTTP traces URL, including `/v1/traces`. Credentials belong in `OTEL_EXPORTER_OTLP_HEADERS`, stored as `SecretStr`; endpoint credentials, query strings and fragments are rejected. Sampling remains parent-based with a validated ratio from zero to one.

An application-owned public `SpanProcessor` uses the public OTLP encoder and sanitizes the resulting protobuf before queueing. Exported data retains trace relationships, timing, span kind/status, registered route templates, fixed operation names, known HTTP methods/status codes and database-system names. Raw paths, URLs, query strings, headers, SQL, exception details, arbitrary attributes, events, tracestate and unapproved resource/scope metadata are removed. Resource identity comes only from the configured service and environment. Transport and encoder logging are suppressed only within telemetry work; application errors remain visible through the existing logging system.

Each lifespan creates a fresh SDK provider and async HTTPX transport. FastAPI receives a stable public provider facade; HTTPX, Requests and SQLAlchemy receive that lifespan's SDK provider. The process-global trace provider is not replaced. Startup failures unwind owned instrumentation and transport; shutdown drains or cancels export and attempts transport closure within the remaining configured budget. Repeated lifespans must continue to export through the new provider.

The exporter uses a bounded queue of 256 sanitized spans, batches up to 128 entries, and makes one bounded attempt per batch. It does not read collector response bodies or follow redirects. Instrumentation is suppressed around collector requests. Queue overflow and export failures produce fixed messages without payloads or credentials.

## Reason

[FastAPI native telemetry](https://fastapi.tiangolo.com/advanced/opentelemetry/) adds dependency, endpoint, serialization and background-task spans. Its automatic environment configuration and native exception logging would bypass this application's opt-in and privacy contracts.

OpenTelemetry SDK 1.45.0 does not enforce the supplied batch flush/export timeout as a total shutdown deadline. A lifespan-owned async transport gives cancellation and resource ownership a testable boundary. The implementation uses public encoder, processor, protobuf, instrumentation and HTTPX APIs; it does not mutate SDK span internals or install another global provider.

## Constraints

Telemetry is best effort: saturated queues, failed requests and shutdown deadlines may drop spans. This is preferable to delaying API shutdown or retaining unbounded memory. Fixed span names and removed attributes limit ad hoc debugging; trace structure, route latency and failure status remain available.

This migration does not activate a production collector. Existing Sentry, structured logging, request metrics and Cloud Run configuration retain their own controls.

Replace the application-owned export loop when the supported SDK provides a verifiable total shutdown deadline and an equivalent privacy boundary. Retain the serialized-payload, failure-log, disabled-provider and repeated-lifespan regressions during that replacement.
