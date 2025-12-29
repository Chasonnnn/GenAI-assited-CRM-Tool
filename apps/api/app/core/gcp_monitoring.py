"""GCP monitoring helpers for Cloud Logging and Error Reporting."""

from dataclasses import dataclass
import logging
import os
import random
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitoringClients:
    """Holds optional GCP monitoring clients."""

    error_reporter: Any | None
    logging_enabled: bool


def _monitoring_enabled() -> bool:
    if settings.ENV == "dev":
        return False
    if os.getenv("TESTING", "").lower() in ("1", "true", "yes"):
        return False
    return settings.GCP_MONITORING_ENABLED


def _should_sample() -> bool:
    rate = settings.GCP_ERROR_REPORTING_SAMPLE_RATE
    if rate >= 1:
        return True
    if rate <= 0:
        return False
    return random.random() < rate


def _build_user_context(
    request: Any | None, request_id: str | None = None
) -> str | None:
    if request is None:
        return None

    session = getattr(request.state, "user_session", None)
    if not session:
        return None

    parts = [
        f"user_id={session.user_id}",
        f"org_id={session.org_id}",
        f"role={session.role.value}",
    ]
    if request_id:
        parts.append(f"request_id={request_id}")
    return " ".join(parts)


def _build_request_id(request: Any | None) -> str | None:
    if request is None:
        return None

    return (
        request.headers.get("x-request-id")
        or request.headers.get("X-Cloud-Trace-Context")
        or request.headers.get("traceparent")
    )


def setup_gcp_monitoring(service_name: str) -> MonitoringClients:
    """
    Initialize GCP Cloud Logging and Error Reporting.

    Returns MonitoringClients with logging_enabled and an optional error_reporter.
    """
    if not _monitoring_enabled():
        return MonitoringClients(error_reporter=None, logging_enabled=False)

    project_id = settings.gcp_project_id
    logging_enabled = False
    error_reporter = None

    try:
        from google.cloud import logging as cloud_logging
        from google.cloud import error_reporting
    except Exception as exc:
        logger.warning("GCP monitoring dependencies unavailable: %s", exc)
        return MonitoringClients(error_reporter=None, logging_enabled=False)

    try:
        cloud_client = cloud_logging.Client(project=project_id or None)
        cloud_client.setup_logging()
        logging_enabled = True
    except Exception as exc:
        logger.warning("GCP logging setup failed: %s", exc)

    try:
        error_reporter = error_reporting.Client(
            project=project_id or None,
            service=service_name,
            version=settings.VERSION,
        )
    except Exception as exc:
        logger.warning("GCP error reporting setup failed: %s", exc)

    return MonitoringClients(
        error_reporter=error_reporter,
        logging_enabled=logging_enabled,
    )


def report_exception(error_reporter: Any | None, request: Any | None = None) -> None:
    """Report the current exception to GCP Error Reporting."""
    if not error_reporter or not _should_sample():
        return

    http_context = None
    if request is not None:
        http_context = {
            "method": request.method,
            "url": str(request.url.path),
            "userAgent": request.headers.get("user-agent"),
        }

    try:
        request_id = _build_request_id(request)
        user = _build_user_context(request, request_id)
        if user:
            try:
                error_reporter.report_exception(http_context=http_context, user=user)
                return
            except TypeError:
                pass
        error_reporter.report_exception(http_context=http_context)
    except Exception as exc:
        logger.warning("Failed to report exception: %s", exc)
