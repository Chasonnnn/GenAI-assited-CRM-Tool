"""Provider-boundary contracts for Twilio messaging transport."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from requests import exceptions as requests_exceptions
from twilio.base.exceptions import TwilioRestException

ACCOUNT_SID = "AC" + "1" * 32
API_KEY_SID = "RK" + "2" * 32
API_SECRET = "restricted-api-secret"
MESSAGE_SID = "SM" + "3" * 32
INBOUND_MESSAGE_SID = "MM" + "4" * 32
MEDIA_SID = "ME" + "5" * 32
MESSAGING_SERVICE_SID = "MG" + "6" * 32
TO_NUMBER = "+14155550101"
FROM_NUMBER = "+14155550102"
BODY = "Private appointment reminder"
STATUS_CALLBACK = "https://api.example.test/webhooks/twilio/status"


class _FakeMessages:
    def __init__(self, *, create_result=None, create_error: Exception | None = None):
        self.create_result = create_result
        self.create_error = create_error
        self.create_calls: list[dict[str, object]] = []
        self.context_calls: list[str] = []
        self.media_context = _FakeMediaContext()

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        if self.create_error is not None:
            raise self.create_error
        return self.create_result

    def __call__(self, message_sid: str):
        self.context_calls.append(message_sid)
        return SimpleNamespace(media=lambda media_sid: self.media_context.bind(media_sid))


class _FakeMediaContext:
    def __init__(self):
        self.media_sids: list[str] = []
        self.fetch_calls = 0
        self.delete_calls = 0
        self.fetch_result = SimpleNamespace(
            sid=MEDIA_SID,
            parent_sid=INBOUND_MESSAGE_SID,
            content_type="image/jpeg",
            date_created=datetime(2026, 7, 31, 12, 30, tzinfo=UTC),
            uri=f"/private/{TO_NUMBER}/{BODY}",
        )
        self.delete_result = True

    def bind(self, media_sid: str):
        self.media_sids.append(media_sid)
        return self

    def fetch(self):
        self.fetch_calls += 1
        return self.fetch_result

    def delete(self):
        self.delete_calls += 1
        return self.delete_result


class _FakeBulkConsents:
    def __init__(self, response_factory=None):
        self.create_calls: list[list[object]] = []
        self.response_factory = response_factory or self._success_response

    @staticmethod
    def _success_response(items):
        return SimpleNamespace(
            items=[
                {
                    "correlation_id": item["correlation_id"],
                    "error_code": 0,
                    "error_messages": [],
                }
                for item in items
            ]
        )

    def create(self, *, items):
        self.create_calls.append(items)
        return self.response_factory(items)


class _FakeClient:
    def __init__(self, *, messages=None, bulk_consents=None):
        self.messages = messages or _FakeMessages()
        self.accounts = SimpleNamespace(
            v1=SimpleNamespace(bulk_consents=bulk_consents or _FakeBulkConsents())
        )


class _ClientFactory:
    def __init__(self, client: _FakeClient):
        self.client = client
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.client


def _credentials():
    from app.services.twilio_transport import TwilioCredentials

    return TwilioCredentials(
        account_sid=ACCOUNT_SID,
        api_key_sid=API_KEY_SID,
        api_secret=API_SECRET,
    )


def _assert_restricted_client_call(factory: _ClientFactory) -> None:
    assert len(factory.calls) == 1
    args, kwargs = factory.calls[0]
    assert args == (API_KEY_SID, API_SECRET, ACCOUNT_SID)
    assert set(kwargs) == {"http_client"}
    http_client = kwargs["http_client"]
    assert http_client.timeout == 20.0
    assert http_client.session.adapters["https://"].max_retries.total == 0


def test_send_sms_uses_restricted_key_and_exact_sender_with_messaging_service(monkeypatch):
    from app.services import twilio_transport

    messages = _FakeMessages(create_result=SimpleNamespace(sid=MESSAGE_SID, status="accepted"))
    factory = _ClientFactory(_FakeClient(messages=messages))
    monkeypatch.setattr(twilio_transport, "Client", factory)

    result = twilio_transport.send_message(
        credentials=_credentials(),
        to=TO_NUMBER,
        from_=FROM_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        body=BODY,
        status_callback=STATUS_CALLBACK,
    )

    _assert_restricted_client_call(factory)
    assert messages.create_calls == [
        {
            "to": TO_NUMBER,
            "from_": FROM_NUMBER,
            "messaging_service_sid": MESSAGING_SERVICE_SID,
            "body": BODY,
            "status_callback": STATUS_CALLBACK,
        }
    ]
    assert result.success is True
    assert result.message_sid == MESSAGE_SID
    assert result.initial_status == "accepted"
    assert result.retryable is False
    assert result.ambiguous is False
    assert API_SECRET not in repr(result)
    assert TO_NUMBER not in repr(result)
    assert FROM_NUMBER not in repr(result)
    assert BODY not in repr(result)
    assert API_SECRET not in repr(_credentials())


def test_send_mms_passes_optional_media_urls_exactly(monkeypatch):
    from app.services import twilio_transport

    messages = _FakeMessages(create_result=SimpleNamespace(sid=MESSAGE_SID, status="accepted"))
    monkeypatch.setattr(
        twilio_transport,
        "Client",
        _ClientFactory(_FakeClient(messages=messages)),
    )
    media_urls = [
        "https://media.example.test/one.jpg",
        "https://media.example.test/two.png",
    ]

    result = twilio_transport.send_message(
        credentials=_credentials(),
        to=TO_NUMBER,
        from_=FROM_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        body=None,
        status_callback=STATUS_CALLBACK,
        media_urls=media_urls,
    )

    assert result.success is True
    assert messages.create_calls[0] == {
        "to": TO_NUMBER,
        "from_": FROM_NUMBER,
        "messaging_service_sid": MESSAGING_SERVICE_SID,
        "status_callback": STATUS_CALLBACK,
        "media_url": media_urls,
    }


def test_provider_21610_is_a_terminal_opt_out_without_sensitive_error_detail(monkeypatch):
    from app.services import twilio_transport

    error = TwilioRestException(
        status=400,
        uri=f"/Messages?To={TO_NUMBER}",
        msg=f"{BODY} using {API_SECRET}",
        code=21610,
        method="POST",
    )
    messages = _FakeMessages(create_error=error)
    monkeypatch.setattr(
        twilio_transport,
        "Client",
        _ClientFactory(_FakeClient(messages=messages)),
    )

    result = twilio_transport.send_message(
        credentials=_credentials(),
        to=TO_NUMBER,
        from_=FROM_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        body=BODY,
        status_callback=STATUS_CALLBACK,
    )

    assert result.success is False
    assert result.failure_reason == twilio_transport.TwilioFailureReason.PROVIDER_OPT_OUT
    assert result.provider_error_code == 21610
    assert result.provider_opt_out is True
    assert result.retryable is False
    assert result.ambiguous is False
    assert all(
        sensitive not in repr(result) for sensitive in (API_SECRET, TO_NUMBER, FROM_NUMBER, BODY)
    )


@pytest.mark.parametrize(
    "transport_error",
    [
        requests_exceptions.ReadTimeout(
            f"response lost after accepting {TO_NUMBER} {BODY} {API_SECRET}"
        ),
        requests_exceptions.ConnectionError(
            f"connection dropped after write {TO_NUMBER} {BODY} {API_SECRET}"
        ),
    ],
)
def test_transport_failure_after_possible_acceptance_is_ambiguous_without_retry(
    monkeypatch,
    transport_error,
):
    from app.services import twilio_transport

    messages = _FakeMessages(create_error=transport_error)
    monkeypatch.setattr(
        twilio_transport,
        "Client",
        _ClientFactory(_FakeClient(messages=messages)),
    )

    result = twilio_transport.send_message(
        credentials=_credentials(),
        to=TO_NUMBER,
        from_=FROM_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        body=BODY,
        status_callback=STATUS_CALLBACK,
    )

    assert result.success is False
    assert result.failure_reason == twilio_transport.TwilioFailureReason.AMBIGUOUS_TRANSPORT
    assert result.retryable is False
    assert result.ambiguous is True
    assert all(
        sensitive not in repr(result) for sensitive in (API_SECRET, TO_NUMBER, FROM_NUMBER, BODY)
    )
    assert len(messages.create_calls) == 1


def test_explicit_rate_limit_response_is_the_only_safe_retry_class(monkeypatch):
    from app.services import twilio_transport

    error = TwilioRestException(
        status=429,
        uri="/Messages",
        msg="rate limited",
        code=20429,
        method="POST",
    )
    messages = _FakeMessages(create_error=error)
    monkeypatch.setattr(
        twilio_transport,
        "Client",
        _ClientFactory(_FakeClient(messages=messages)),
    )

    result = twilio_transport.send_message(
        credentials=_credentials(),
        to=TO_NUMBER,
        from_=FROM_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        body=BODY,
        status_callback=STATUS_CALLBACK,
    )

    assert result.failure_reason == twilio_transport.TwilioFailureReason.RATE_LIMITED
    assert result.retryable is True
    assert result.ambiguous is False
    assert len(messages.create_calls) == 1


def test_server_error_is_not_blindly_retried_without_provider_idempotency(monkeypatch):
    from app.services import twilio_transport

    error = TwilioRestException(
        status=503,
        uri="/Messages",
        msg=f"unknown state for {TO_NUMBER} {BODY} {API_SECRET}",
        code=20503,
        method="POST",
    )
    messages = _FakeMessages(create_error=error)
    monkeypatch.setattr(
        twilio_transport,
        "Client",
        _ClientFactory(_FakeClient(messages=messages)),
    )

    result = twilio_transport.send_message(
        credentials=_credentials(),
        to=TO_NUMBER,
        from_=FROM_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        body=BODY,
        status_callback=STATUS_CALLBACK,
    )

    assert result.failure_reason == twilio_transport.TwilioFailureReason.PROVIDER_REJECTED
    assert result.retryable is False
    assert result.ambiguous is False
    assert len(messages.create_calls) == 1
    assert all(sensitive not in repr(result) for sensitive in (API_SECRET, TO_NUMBER, BODY))


def test_send_rejects_non_e164_destination_before_provider_io(monkeypatch):
    from app.services import twilio_transport

    factory = _ClientFactory(_FakeClient())
    monkeypatch.setattr(twilio_transport, "Client", factory)

    with pytest.raises(ValueError, match="destination must use E.164"):
        twilio_transport.send_message(
            credentials=_credentials(),
            to="415-555-0101",
            from_=FROM_NUMBER,
            messaging_service_sid=MESSAGING_SERVICE_SID,
            body=BODY,
            status_callback=STATUS_CALLBACK,
        )

    assert factory.calls == []


def test_bulk_consent_upsert_submits_service_and_exact_sender_with_unique_ids(monkeypatch):
    from app.services import twilio_transport

    bulk_consents = _FakeBulkConsents()
    factory = _ClientFactory(_FakeClient(bulk_consents=bulk_consents))
    monkeypatch.setattr(twilio_transport, "Client", factory)
    consented_at = datetime(2026, 7, 31, 12, 30, tzinfo=UTC)

    result = twilio_transport.upsert_route_consent(
        credentials=_credentials(),
        contact_id=TO_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        sender_phone=FROM_NUMBER,
        status="opt-in",
        source="website",
        date_of_consent=consented_at,
        route_marker="10dlc",
    )

    assert result.success is True
    _assert_restricted_client_call(factory)
    assert len(bulk_consents.create_calls) == 1
    items = bulk_consents.create_calls[0]
    assert [item["sender_id"] for item in items] == [
        MESSAGING_SERVICE_SID,
        FROM_NUMBER,
    ]
    assert all(item["contact_id"] == TO_NUMBER for item in items)
    assert all(item["status"] == "opt-in" for item in items)
    assert all(item["source"] == "website" for item in items)
    assert all(item["date_of_consent"] == "2026-07-31T12:30:00Z" for item in items)
    correlation_ids = [item["correlation_id"] for item in items]
    assert correlation_ids == list(result.correlation_ids)
    assert len(set(correlation_ids)) == 2
    assert all(len(value) == 32 for value in correlation_ids)
    assert all(value.isalnum() for value in correlation_ids)
    assert all(
        sensitive not in repr(result) for sensitive in (API_SECRET, TO_NUMBER, FROM_NUMBER, BODY)
    )


def test_bulk_consent_requires_both_correlated_items_to_succeed(monkeypatch):
    from app.services import twilio_transport

    def partial_failure(items):
        return SimpleNamespace(
            items=[
                {
                    "correlation_id": items[0]["correlation_id"],
                    "error_code": 0,
                    "error_messages": [],
                },
                {
                    "correlation_id": items[1]["correlation_id"],
                    "error_code": 30646,
                    "error_messages": [f"INVALID_CONTACT_ID {TO_NUMBER} {API_SECRET}"],
                },
            ]
        )

    bulk_consents = _FakeBulkConsents(response_factory=partial_failure)
    monkeypatch.setattr(
        twilio_transport,
        "Client",
        _ClientFactory(_FakeClient(bulk_consents=bulk_consents)),
    )

    result = twilio_transport.upsert_route_consent(
        credentials=_credentials(),
        contact_id=TO_NUMBER,
        messaging_service_sid=MESSAGING_SERVICE_SID,
        sender_phone=FROM_NUMBER,
        status="opt-out",
        source="opt-out-message",
        date_of_consent=datetime(2026, 7, 31, 12, 30, tzinfo=UTC),
        route_marker="10dlc",
    )

    assert result.success is False
    assert result.failure_reason == twilio_transport.TwilioFailureReason.CONSENT_ITEM_REJECTED
    assert result.item_error_codes == (0, 30646)
    assert result.retryable is False
    assert all(
        sensitive not in repr(result) for sensitive in (API_SECRET, TO_NUMBER, FROM_NUMBER, BODY)
    )


@pytest.mark.parametrize(
    "route_marker",
    ["toll-free", "toll_free", "tollfree", "us-toll-free-number"],
)
def test_bulk_consent_rejects_toll_free_route_markers_before_provider_io(
    monkeypatch,
    route_marker,
):
    from app.services import twilio_transport

    factory = _ClientFactory(_FakeClient())
    monkeypatch.setattr(twilio_transport, "Client", factory)

    with pytest.raises(ValueError, match="toll-free routes"):
        twilio_transport.upsert_route_consent(
            credentials=_credentials(),
            contact_id=TO_NUMBER,
            messaging_service_sid=MESSAGING_SERVICE_SID,
            sender_phone=FROM_NUMBER,
            status="opt-in",
            source="offline",
            date_of_consent=datetime(2026, 7, 31, 12, 30, tzinfo=UTC),
            route_marker=route_marker,
        )

    assert factory.calls == []


def test_fetch_inbound_media_uses_authenticated_sdk_and_returns_bounded_metadata(monkeypatch):
    from app.services import twilio_transport

    messages = _FakeMessages()
    messages.media_context.fetch_result.content_type = "private/" + BODY * 100
    factory = _ClientFactory(_FakeClient(messages=messages))
    monkeypatch.setattr(twilio_transport, "Client", factory)

    result = twilio_transport.fetch_inbound_media_metadata(
        credentials=_credentials(),
        message_sid=INBOUND_MESSAGE_SID,
        media_sid=MEDIA_SID,
    )

    _assert_restricted_client_call(factory)
    assert messages.context_calls == [INBOUND_MESSAGE_SID]
    assert messages.media_context.media_sids == [MEDIA_SID]
    assert messages.media_context.fetch_calls == 1
    assert result.success is True
    assert result.media_sid == MEDIA_SID
    assert result.content_type == "application/octet-stream"
    assert len(repr(result)) < 500
    assert all(
        sensitive not in repr(result) for sensitive in (API_SECRET, TO_NUMBER, FROM_NUMBER, BODY)
    )


def test_delete_inbound_media_uses_authenticated_sdk_without_file_io(monkeypatch):
    from app.services import twilio_transport

    messages = _FakeMessages()
    factory = _ClientFactory(_FakeClient(messages=messages))
    monkeypatch.setattr(twilio_transport, "Client", factory)

    result = twilio_transport.delete_inbound_media(
        credentials=_credentials(),
        message_sid=INBOUND_MESSAGE_SID,
        media_sid=MEDIA_SID,
    )

    assert result.success is True
    _assert_restricted_client_call(factory)
    assert messages.context_calls == [INBOUND_MESSAGE_SID]
    assert messages.media_context.media_sids == [MEDIA_SID]
    assert messages.media_context.delete_calls == 1
