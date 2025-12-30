"""OpenTelemetry tracing setup."""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from app.core.config import settings

logger = logging.getLogger(__name__)


def _parse_headers(value: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not value:
        return headers
    for item in value.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, val = item.split("=", 1)
        headers[key.strip()] = val.strip()
    return headers


def configure_telemetry(app, engine) -> None:
    """Initialize OpenTelemetry tracing when enabled."""
    if not settings.OTEL_ENABLED or not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return

    try:
        resource = Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: settings.OTEL_SERVICE_NAME
                or settings.GCP_SERVICE_NAME
                or "crm-api",
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT: settings.ENV,
            }
        )
        sampler = ParentBased(TraceIdRatioBased(settings.OTEL_SAMPLE_RATE))
        provider = TracerProvider(resource=resource, sampler=sampler)

        exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers=_parse_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        SQLAlchemyInstrumentor().instrument(engine=engine)
        HTTPXClientInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        logger.info("OpenTelemetry tracing enabled")
    except Exception:
        logger.exception("Failed to initialize OpenTelemetry tracing")
