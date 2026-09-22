from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from google.cloud.error_reporting.util import HTTPContext


def test_report_exception_uses_sdk_http_context(monkeypatch):
    from app.core import gcp_monitoring

    reported: list[tuple[HTTPContext | None, str | None]] = []

    class StrictErrorReporter:
        def report_exception(
            self,
            http_context: HTTPContext | None = None,
            user: str | None = None,
        ) -> None:
            if http_context is not None and not isinstance(http_context, HTTPContext):
                raise TypeError("http_context must be an HTTPContext")
            reported.append((http_context, user))

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/webhooks/resend/platform"),
        headers={
            "user-agent": "Svix-Webhooks/test",
            "x-request-id": "request-123",
        },
        state=SimpleNamespace(
            user_session=SimpleNamespace(
                user_id=uuid4(),
                org_id=uuid4(),
                role=SimpleNamespace(value="admin"),
            )
        ),
    )
    monkeypatch.setattr(gcp_monitoring, "_should_sample", lambda: True)

    gcp_monitoring.report_exception(StrictErrorReporter(), request)

    assert len(reported) == 1
    http_context, user = reported[0]
    assert isinstance(http_context, HTTPContext)
    assert vars(http_context) == {
        "method": "POST",
        "url": "/webhooks/resend/platform",
        "userAgent": "Svix-Webhooks/test",
        "referrer": None,
        "responseStatusCode": None,
        "remoteIp": None,
    }
    assert user is not None and "request_id=request-123" in user


def test_report_exception_serializes_through_the_real_sdk(monkeypatch):
    from google.auth.credentials import AnonymousCredentials
    from google.cloud.error_reporting import Client
    from google.cloud.error_reporting._gapic import _ErrorReportingGapicApi

    from app.core import gcp_monitoring
    from app.core.protobuf_guard import apply_protobuf_json_depth_guard

    apply_protobuf_json_depth_guard()
    rpc = Mock()
    reporter = Client(
        project="test-project", credentials=AnonymousCredentials(), service="test-api"
    )
    reporter._report_errors_api = _ErrorReportingGapicApi(rpc, "test-project")
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/health/ready"),
        headers={},
        state=SimpleNamespace(),
    )
    monkeypatch.setattr(gcp_monitoring, "_should_sample", lambda: True)

    try:
        raise RuntimeError("Synthetic reporting regression")
    except RuntimeError:
        gcp_monitoring.report_exception(reporter, request)

    rpc.report_error_event.assert_called_once()
    event = rpc.report_error_event.call_args.kwargs["event"]
    assert "Synthetic reporting regression" in event.message
    assert event.service_context.service == "test-api"
    assert event.context.http_request.method == "GET"
    assert event.context.http_request.url == "/health/ready"
