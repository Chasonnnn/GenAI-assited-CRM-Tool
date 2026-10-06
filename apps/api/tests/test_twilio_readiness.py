"""Cache-only readiness contracts for organization Twilio messaging."""

from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock, Thread
from time import sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import JobType
from app.db.models import Job, Organization, TwilioRoute, TwilioSettings


def _route_by_purpose(settings: TwilioSettings, purpose: str) -> TwilioRoute:
    return next(route for route in settings.routes if route.purpose == purpose)


def _configured_toll_free_settings(organization_id):
    from app.services import twilio_settings_service

    encrypt = twilio_settings_service.encrypt_credential
    settings = TwilioSettings(
        organization_id=organization_id,
        enabled=True,
        current_version=1,
        account_sid_encrypted=encrypt("AC" + "1" * 32),
        api_key_sid_encrypted=encrypt("SK" + "2" * 32),
        api_secret_encrypted=encrypt("private-api-secret"),
        auth_token_encrypted=encrypt("private-auth-token"),
        legal_messaging_brand="Example Agency",
        operational_disclosure="Operational disclosure",
        sms_terms_url="https://example.org/terms",
        privacy_policy_url="https://example.org/privacy",
        support_contact="help@example.org",
        expected_frequency="Message frequency varies",
        counsel_approved_at=datetime.now(UTC),
        phi_enabled=False,
    )
    settings.routes = [
        TwilioRoute(
            organization_id=settings.organization_id,
            purpose=purpose,
            webhook_id=uuid4().hex,
            enabled=purpose == "operational",
            a2p_status="unconfigured",
            advanced_opt_out_status="verified",
            consent_management_status="unknown",
        )
        for purpose in ("promotional", "operational")
    ]
    route = _route_by_purpose(settings, "operational")
    route.messaging_service_sid_encrypted = encrypt("MG" + "3" * 32)
    route.sender_phone_encrypted = encrypt("+18005550199")
    route.capability_evidence = {
        "provider": {
            "account_active": True,
            "service_verified": True,
            "sender_in_pool": True,
            "sms": True,
            "mms": True,
            "sender_type": "toll_free",
            "a2p_status": None,
            "toll_free_verification_status": "TWILIO_APPROVED",
            "inbound_webhook_matches": True,
            "status_callback_matches": True,
            "checked_at": datetime.now(UTC).isoformat(),
            "settings_version": settings.current_version,
        },
    }
    return settings


@pytest.fixture
def toll_free_settings(monkeypatch):
    monkeypatch.setenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", "true")
    return _configured_toll_free_settings(uuid4())


@pytest.mark.parametrize("consent_status", ["unknown", "unavailable", "available"])
def test_approved_toll_free_does_not_require_a2p_or_consent_api(toll_free_settings, consent_status):
    from app.services.twilio_readiness_service import route_send_blockers

    route = _route_by_purpose(toll_free_settings, "operational")
    route.consent_management_status = consent_status
    assert route_send_blockers(toll_free_settings, route) == []


@pytest.mark.parametrize("status", ["PENDING_REVIEW", "IN_REVIEW", "TWILIO_REJECTED", None])
def test_toll_free_requires_approved_verification(toll_free_settings, status):
    from app.services.twilio_readiness_service import route_send_blockers

    route = _route_by_purpose(toll_free_settings, "operational")
    route.capability_evidence["provider"]["toll_free_verification_status"] = status
    # An approved 10DLC campaign must not authorize a toll-free sender.
    route.capability_evidence["provider"]["a2p_status"] = "VERIFIED"
    assert [code for code, _ in route_send_blockers(toll_free_settings, route)] == [
        "operational_toll_free_unverified"
    ]


@pytest.mark.parametrize("fence", ["age", "version"])
def test_toll_free_approval_requires_fresh_version_matched_evidence(toll_free_settings, fence):
    from app.services.twilio_readiness_service import route_send_blockers

    route = _route_by_purpose(toll_free_settings, "operational")
    if fence == "age":
        route.capability_evidence["provider"]["checked_at"] = (
            datetime.now(UTC) - timedelta(hours=25)
        ).isoformat()
    else:
        route.capability_evidence["provider"]["settings_version"] = 0
    assert "operational_provider_evidence_stale" in dict(
        route_send_blockers(toll_free_settings, route)
    )


@pytest.mark.parametrize(
    "target,field,value,code",
    [
        ("route", "advanced_opt_out_status", "enabled", "operational_advanced_opt_out_unverified"),
        ("settings", "counsel_approved_at", None, "counsel_approval_missing"),
        ("settings", "sms_terms_url", None, "public_legal_urls_missing"),
        (
            "env",
            "MESSAGING_DELIVERY_DISPATCH_ENABLED",
            "false",
            "messaging_dispatch_worker_disabled",
        ),
    ],
)
def test_toll_free_keeps_other_send_gates(
    toll_free_settings, monkeypatch, target, field, value, code
):
    from app.services.twilio_readiness_service import route_send_blockers

    route = _route_by_purpose(toll_free_settings, "operational")
    if target == "env":
        monkeypatch.setenv(field, value)
    else:
        setattr(route if target == "route" else toll_free_settings, field, value)
    assert code in dict(route_send_blockers(toll_free_settings, route))


def test_10dlc_still_requires_a2p_and_consent_api(toll_free_settings):
    from app.services.twilio_readiness_service import route_send_blockers

    route = _route_by_purpose(toll_free_settings, "operational")
    route.capability_evidence["provider"]["sender_type"] = "10dlc"
    assert set(dict(route_send_blockers(toll_free_settings, route))) == {
        "operational_a2p_unverified",
        "operational_consent_api_unavailable",
    }


def _mock_toll_free_provider(monkeypatch, settings, *, status="TWILIO_APPROVED", error=None):
    from app.services import twilio_settings_service, twilio_transport

    route = _route_by_purpose(settings, "operational")
    calls = []
    service_sid = twilio_settings_service.decrypt_credential(route.messaging_service_sid_encrypted)

    def list_verifications(**kwargs):
        calls.append(kwargs)
        if error:
            raise error
        return (
            [SimpleNamespace(tollfree_phone_number_sid="PN" + "4" * 32, status=status)]
            if status is not None
            else []
        )

    def no_campaign_query(**_kwargs):
        raise AssertionError("Toll-free verification must not query 10DLC campaigns")

    service = SimpleNamespace(
        fetch=lambda: SimpleNamespace(
            sid=service_sid,
            inbound_request_url=twilio_settings_service.route_webhook_url(
                route.webhook_id, "inbound"
            ),
            inbound_method="POST",
            use_inbound_webhook_on_number=False,
            status_callback=twilio_settings_service.route_webhook_url(route.webhook_id, "status"),
        ),
        phone_numbers=SimpleNamespace(
            list=lambda **_kwargs: [
                SimpleNamespace(
                    sid="PN" + "4" * 32, phone_number="+18005550199", capabilities=["SMS"]
                )
            ]
        ),
        us_app_to_person=SimpleNamespace(list=no_campaign_query),
    )
    client = SimpleNamespace(
        api=SimpleNamespace(
            accounts=lambda _sid: SimpleNamespace(fetch=lambda: SimpleNamespace(status="active"))
        ),
        messaging=SimpleNamespace(
            v1=SimpleNamespace(
                services=lambda _sid: service,
                tollfree_verifications=SimpleNamespace(list=list_verifications),
            )
        ),
    )
    monkeypatch.setattr(twilio_transport, "Client", lambda *_args, **_kwargs: client)
    return calls


@pytest.mark.parametrize(
    "status", ["TWILIO_APPROVED", "PENDING_REVIEW", "IN_REVIEW", "TWILIO_REJECTED", None]
)
def test_provider_checks_exact_toll_free_number_without_promotional_route(
    toll_free_settings, monkeypatch, status
):
    from app.services import twilio_provider_service

    calls = _mock_toll_free_provider(monkeypatch, toll_free_settings, status=status)
    result = twilio_provider_service.test_configuration(toll_free_settings)
    assert result.valid is (status == "TWILIO_APPROVED")
    assert result.error is None
    assert calls == [{"tollfree_phone_number_sid": "PN" + "4" * 32, "limit": 2}]
    provider = result.route_capabilities["operational"]
    assert provider["sender_type"] == "toll_free"
    assert provider["toll_free_verification_status"] == status
    assert provider["a2p_status"] is None


@pytest.mark.parametrize("failure", ["rest", "timeout"])
def test_toll_free_api_failure_revokes_approval_without_sensitive_output(
    db, test_org, toll_free_settings, monkeypatch, caplog, failure
):
    from requests.exceptions import ReadTimeout
    from twilio.base.exceptions import TwilioRestException

    from app.services import twilio_readiness_service

    settings = toll_free_settings
    settings.organization_id = test_org.id
    for route in settings.routes:
        route.organization_id = test_org.id
    db.add(settings)
    db.commit()
    private = "private-api-secret private-auth-token +18005550199"
    error = (
        TwilioRestException(status=403, uri=private, msg=private, code=20003)
        if failure == "rest"
        else ReadTimeout(private)
    )
    _mock_toll_free_provider(monkeypatch, settings, error=error)
    assert twilio_readiness_service.refresh_readiness(
        db, organization_id=test_org.id, expected_settings_version=settings.current_version
    )
    snapshot = _route_by_purpose(settings, "operational").capability_evidence["readiness"]
    assert snapshot["error_code"] == (
        "twilio_20003" if failure == "rest" else "twilio_request_failed"
    )
    assert "operational_toll_free_unverified" in dict(
        twilio_readiness_service.route_send_blockers(
            settings, _route_by_purpose(settings, "operational")
        )
    )
    assert (
        not twilio_readiness_service.get_readiness(db, test_org.id)
        .provider.routes["operational"]
        .can_send_sms
    )
    for sensitive in private.split():
        assert (
            sensitive
            not in str(_route_by_purpose(settings, "operational").capability_evidence) + caplog.text
        )


async def test_operational_only_toll_free_readiness_is_scoped_to_authenticated_org(
    db, test_org, authed_client, toll_free_settings, monkeypatch
):
    from app.services import twilio_readiness_service

    settings = toll_free_settings
    settings.organization_id = test_org.id
    for route in settings.routes:
        route.organization_id = test_org.id
    db.add(settings)
    db.commit()
    _mock_toll_free_provider(monkeypatch, settings)
    assert twilio_readiness_service.refresh_readiness(
        db, organization_id=test_org.id, expected_settings_version=settings.current_version
    )
    assert _route_by_purpose(settings, "operational").a2p_status == "unconfigured"
    assert _route_by_purpose(settings, "promotional").a2p_status == "unconfigured"
    response = await authed_client.get("/twilio/readiness")
    assert response.status_code == 200
    ready = response.json()
    assert ready["overall_status"] == "ready"
    assert ready["issues"] == []
    operational = ready["provider"]["routes"]["operational"]
    assert operational["can_send_sms"] is operational["can_receive"] is True
    assert operational["sender_type"] == "toll_free"
    assert operational["toll_free_verification_status"] == "TWILIO_APPROVED"
    assert ready["provider"]["routes"]["promotional"]["status"] == "not_configured"
    assert {gate["status"] for gate in ready["gates"]} <= {"pass", "skipped"}
    assert [gate["key"] for gate in ready["gates"] if gate["route"] == "promotional"] == []

    other = Organization(id=uuid4(), name="Other Agency", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    other_settings = _configured_toll_free_settings(other.id)
    db.add(other_settings)
    db.commit()
    _mock_toll_free_provider(monkeypatch, other_settings, status="TWILIO_REJECTED")
    assert twilio_readiness_service.refresh_readiness(
        db, organization_id=other.id, expected_settings_version=other_settings.current_version
    )
    # Org B's rejection cannot block org A's approved route.
    assert (await authed_client.get("/twilio/readiness")).json() == ready
    blocked = twilio_readiness_service.get_readiness(db, other.id)
    assert blocked.overall_status == "blocked"
    assert blocked.provider.routes["operational"].can_send_sms is False
    assert blocked.provider.routes["operational"].toll_free_verification_status == "TWILIO_REJECTED"
    assert "operational_toll_free_unverified" in {issue.code for issue in blocked.issues}

    # Refreshing org A's approval cannot authorize org B's rejected route.
    _mock_toll_free_provider(monkeypatch, settings)
    assert twilio_readiness_service.refresh_readiness(
        db, organization_id=test_org.id, expected_settings_version=settings.current_version
    )
    assert twilio_readiness_service.get_readiness(db, other.id) == blocked
    current = (await authed_client.get("/twilio/readiness")).json()
    assert current["overall_status"] == "ready"
    assert current["provider"]["routes"]["operational"] == operational


@pytest.mark.parametrize("status", ["TWILIO_APPROVED", "PENDING_REVIEW", "TWILIO_REJECTED"])
def test_toll_free_refresh_clears_previous_10dlc_status(
    db, test_org, toll_free_settings, monkeypatch, status
):
    from app.services import twilio_readiness_service, twilio_settings_service

    settings = toll_free_settings
    settings.organization_id = test_org.id
    for route in settings.routes:
        route.organization_id = test_org.id
    route = _route_by_purpose(settings, "operational")
    route.a2p_status = "approved"
    db.add(settings)
    db.commit()
    _mock_toll_free_provider(monkeypatch, settings, status=status)

    assert twilio_readiness_service.refresh_readiness(
        db, organization_id=test_org.id, expected_settings_version=settings.current_version
    )

    db.refresh(route)
    assert route.a2p_status == "unconfigured"
    assert route.capability_evidence["provider"]["toll_free_verification_status"] == status
    projected = twilio_settings_service.project_settings(settings)
    assert projected.routes["operational"].a2p_status == "unconfigured"


@pytest.mark.parametrize("purpose", ["operational", "promotional"])
def test_overall_readiness_includes_configured_route_status(
    db, test_org, toll_free_settings, monkeypatch, purpose
):
    from copy import deepcopy

    from app.services import twilio_readiness_service

    settings = toll_free_settings
    settings.organization_id = test_org.id
    for route in settings.routes:
        route.organization_id = test_org.id
    db.add(settings)
    db.commit()
    _mock_toll_free_provider(monkeypatch, settings)
    assert twilio_readiness_service.refresh_readiness(
        db, organization_id=test_org.id, expected_settings_version=settings.current_version
    )
    operational = _route_by_purpose(settings, "operational")
    route = _route_by_purpose(settings, purpose)
    route.enabled = True
    route.messaging_service_sid_encrypted = operational.messaging_service_sid_encrypted
    route.sender_phone_encrypted = operational.sender_phone_encrypted
    route.capability_evidence = deepcopy(operational.capability_evidence)
    settings.promotional_disclosure = "Promotional disclosure"
    route.advanced_opt_out_status = "enabled"
    db.commit()
    # A blocked route must still block overall readiness if summary issues are omitted.
    monkeypatch.setattr(twilio_readiness_service, "_append_issue", lambda *_args, **_kwargs: None)

    readiness = twilio_readiness_service.get_readiness(db, test_org.id)

    assert readiness.issues == []
    assert readiness.provider.status == "ready"
    assert readiness.provider.routes[purpose].status == "blocked"
    assert readiness.overall_status == "blocked"


@pytest.mark.parametrize("partial", ["enabled", "service", "sender"])
def test_incomplete_promotional_route_still_blocks_readiness(
    db, test_org, toll_free_settings, monkeypatch, partial
):
    from app.services import twilio_provider_service, twilio_readiness_service

    settings = toll_free_settings
    settings.organization_id = test_org.id
    for route in settings.routes:
        route.organization_id = test_org.id
    promotional = _route_by_purpose(settings, "promotional")
    if partial == "enabled":
        promotional.enabled = True
    elif partial == "service":
        promotional.messaging_service_sid_encrypted = _route_by_purpose(
            settings, "operational"
        ).messaging_service_sid_encrypted
    else:
        promotional.sender_phone_encrypted = _route_by_purpose(
            settings, "operational"
        ).sender_phone_encrypted
    db.add(settings)
    db.commit()
    _mock_toll_free_provider(monkeypatch, settings)
    assert twilio_provider_service.test_configuration(settings).valid is False
    twilio_readiness_service.refresh_readiness(
        db, organization_id=test_org.id, expected_settings_version=settings.current_version
    )
    readiness = twilio_readiness_service.get_readiness(db, test_org.id)
    assert readiness.overall_status == "blocked"
    assert "promotional_route_missing" in {issue.code for issue in readiness.issues}


async def test_get_twilio_readiness_is_local_only_and_not_configured_by_default(
    authed_client,
    monkeypatch,
):
    from app.services import twilio_provider_service

    def fail_if_provider_called(*_args, **_kwargs):
        raise AssertionError("GET readiness must never contact Twilio")

    monkeypatch.setattr(
        twilio_provider_service,
        "test_configuration",
        fail_if_provider_called,
    )

    response = await authed_client.get("/twilio/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] == "not_configured"
    assert payload["checked_at"] is None
    assert payload["provider"] == {
        "status": "not_configured",
        "credentials_valid": False,
        "account_status": None,
        "checked_at": None,
        "capabilities": {
            "send_sms": False,
            "send_mms": False,
            "receive_sms": False,
            "receive_mms": False,
            "status_callbacks": False,
        },
        "routes": {
            "operational": {
                "status": "not_configured",
                "can_send_sms": False,
                "can_send_mms": False,
                "can_receive": False,
                "sender_type": None,
                "toll_free_verification_status": None,
                "issues": ["Messaging Service and sender are not configured."],
            },
            "promotional": {
                "status": "not_configured",
                "can_send_sms": False,
                "can_send_mms": False,
                "can_receive": False,
                "sender_type": None,
                "toll_free_verification_status": None,
                "issues": ["Messaging Service and sender are not configured."],
            },
        },
    }
    assert payload["local"] == {
        "queue": {
            "status": "ready",
            "queued_count": 0,
            "processing_count": 0,
            "failed_count": 0,
            "oldest_queued_at": None,
        },
        "reconciliation": {
            "status": "ready",
            "action_required_count": 0,
            "unresolved_event_count": 0,
            "last_reconciled_at": None,
        },
    }
    assert {issue["code"] for issue in payload["issues"]} == {
        "twilio_disabled",
        "twilio_credentials_missing",
        "operational_route_missing",
    }


def test_twilio_settings_cold_start_is_safe_under_concurrent_reads(
    db_engine,
    monkeypatch,
) -> None:
    from app.db.session import SessionLocal
    from app.services import twilio_settings_service

    organization_id = uuid4()
    setup = SessionLocal(bind=db_engine)
    setup.add(
        Organization(
            id=organization_id,
            name="Concurrent Twilio Settings",
            slug=f"concurrent-twilio-{uuid4().hex[:8]}",
        )
    )
    setup.commit()
    setup.close()

    original_get_settings = twilio_settings_service.get_settings

    def widen_missing_row_window(session, organization_id):
        result = original_get_settings(session, organization_id)
        if result is None:
            sleep(0.2)
        return result

    monkeypatch.setattr(twilio_settings_service, "get_settings", widen_missing_row_window)

    ready = Barrier(2)
    result_lock = Lock()
    settings_ids: list[object] = []
    failures: list[BaseException] = []

    def create_settings() -> None:
        session = SessionLocal(bind=db_engine)
        try:
            ready.wait()
            settings = twilio_settings_service.get_or_create_settings(session, organization_id)
            with result_lock:
                settings_ids.append(settings.id)
        except BaseException as exc:  # pragma: no cover - asserted below
            with result_lock:
                failures.append(exc)
        finally:
            session.close()

    threads = [Thread(target=create_settings), Thread(target=create_settings)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert failures == []
    assert len(set(settings_ids)) == 1

    verification = SessionLocal(bind=db_engine)
    try:
        assert (
            verification.query(TwilioSettings)
            .filter(TwilioSettings.organization_id == organization_id)
            .count()
            == 1
        )
        assert (
            verification.query(TwilioRoute)
            .filter(TwilioRoute.organization_id == organization_id)
            .count()
            == 2
        )
    finally:
        verification.query(TwilioRoute).filter(
            TwilioRoute.organization_id == organization_id
        ).delete()
        verification.query(TwilioSettings).filter(
            TwilioSettings.organization_id == organization_id
        ).delete()
        verification.query(Organization).filter(Organization.id == organization_id).delete()
        verification.commit()
        verification.close()


async def test_post_readiness_coalesces_one_durable_no_send_job(authed_client, db) -> None:
    first = await authed_client.post("/twilio/readiness")
    second = await authed_client.post("/twilio/readiness")

    assert first.status_code == second.status_code == 202
    assert first.json()["check_status"] == "queued"
    assert second.json()["check_status"] == "queued"
    jobs = db.query(Job).filter(Job.job_type == JobType.TWILIO_READINESS_CHECK.value).all()
    assert len(jobs) == 1
    assert jobs[0].payload["provider_scope"] == "organization"
    assert jobs[0].payload["settings_version"] >= 1
    assert "secret" not in str(jobs[0].payload).lower()


def _persist_configured_settings(db, organization_id, *, enabled: bool = True) -> TwilioSettings:
    from app.services import twilio_settings_service

    encrypt = twilio_settings_service.encrypt_credential
    settings = twilio_settings_service.get_or_create_settings(db, organization_id)
    settings.enabled = enabled
    settings.account_sid_encrypted = encrypt("AC" + ("1" * 32))
    settings.api_key_sid_encrypted = encrypt("SK" + ("2" * 32))
    settings.api_secret_encrypted = encrypt("secret")
    settings.auth_token_encrypted = encrypt("auth-token")
    for route in settings.routes:
        route.enabled = True
        route.messaging_service_sid_encrypted = encrypt("MG" + ("3" * 32))
        route.sender_phone_encrypted = encrypt("+18005550199")
    db.commit()
    return settings


def _set_provider_evidence(
    db,
    settings,
    *,
    checked_at: datetime | None,
    settings_version: int,
    error_code: str | None = None,
):
    for route in settings.routes:
        route.capability_evidence = {
            "provider": {
                "sender_type": "toll_free",
                "checked_at": checked_at.isoformat() if checked_at else None,
                "settings_version": settings_version,
            },
            "readiness": {
                "checked_at": checked_at.isoformat() if checked_at else None,
                "settings_version": settings_version,
                "error_code": error_code,
            },
        }
    db.commit()


def _readiness_jobs(db, organization_id) -> list[Job]:
    return (
        db.query(Job)
        .filter(
            Job.job_type == JobType.TWILIO_READINESS_CHECK.value,
            Job.organization_id == organization_id,
        )
        .all()
    )


@pytest.mark.parametrize(
    ("evidence_age", "version_lag", "expected_jobs"),
    [
        pytest.param(timedelta(hours=1), 0, 0, id="fresh"),
        pytest.param(timedelta(hours=13), 0, 1, id="older-than-half-the-window"),
        pytest.param(None, 0, 1, id="never-checked"),
        pytest.param(timedelta(hours=1), 1, 1, id="settings-version-changed"),
    ],
)
def test_scheduled_refresh_queues_one_check_before_provider_evidence_expires(
    db, test_org, evidence_age, version_lag, expected_jobs
) -> None:
    from app.services import twilio_readiness_orchestration_service

    now = datetime.now(UTC)
    settings = _persist_configured_settings(db, test_org.id)
    _set_provider_evidence(
        db,
        settings,
        checked_at=now - evidence_age if evidence_age else None,
        settings_version=settings.current_version - version_lag,
    )

    queued = twilio_readiness_orchestration_service.queue_due_refreshes(db, now=now)
    # A second pass inside the same hour must coalesce onto the active job.
    twilio_readiness_orchestration_service.queue_due_refreshes(db, now=now)

    assert queued == expected_jobs
    jobs = _readiness_jobs(db, test_org.id)
    assert len(jobs) == expected_jobs
    for job in jobs:
        assert job.payload == {
            "provider_scope": "organization",
            "settings_version": settings.current_version,
        }


@pytest.mark.parametrize("reason", ["disabled", "route_unconfigured", "organization_deleted"])
def test_scheduled_refresh_skips_organizations_that_cannot_send(db, test_org, reason) -> None:
    from app.services import twilio_readiness_orchestration_service

    settings = _persist_configured_settings(db, test_org.id, enabled=reason != "disabled")
    if reason == "route_unconfigured":
        for route in settings.routes:
            route.messaging_service_sid_encrypted = None
        db.commit()
    if reason == "organization_deleted":
        test_org.deleted_at = datetime.now(UTC)
        db.commit()
    _set_provider_evidence(db, settings, checked_at=None, settings_version=settings.current_version)

    queued = twilio_readiness_orchestration_service.queue_due_refreshes(db, now=datetime.now(UTC))

    assert queued == 0
    assert _readiness_jobs(db, test_org.id) == []


def test_scheduled_refresh_retries_a_probe_that_failed_part_way(db, test_org) -> None:
    from app.services import twilio_readiness_orchestration_service

    now = datetime.now(UTC)
    settings = _persist_configured_settings(db, test_org.id)
    # Fresh timestamp, but the toll-free lookup timed out and left the facts incomplete.
    _set_provider_evidence(
        db,
        settings,
        checked_at=now - timedelta(hours=1),
        settings_version=settings.current_version,
        error_code="twilio_timeout",
    )

    queued = twilio_readiness_orchestration_service.queue_due_refreshes(db, now=now)

    assert queued == 1
    assert len(_readiness_jobs(db, test_org.id)) == 1


def test_scheduled_refresh_queues_a_bounded_batch_per_pass(db, test_org) -> None:
    from app.services import twilio_readiness_orchestration_service

    now = datetime.now(UTC)
    organizations = [test_org]
    for index in range(2):
        organization = Organization(
            id=uuid4(),
            name=f"Tenant {index}",
            slug=f"tenant-{uuid4().hex[:8]}",
            ai_enabled=True,
        )
        db.add(organization)
        db.flush()
        organizations.append(organization)
    for organization in organizations:
        settings = _persist_configured_settings(db, organization.id)
        _set_provider_evidence(
            db, settings, checked_at=None, settings_version=settings.current_version
        )

    passes = [
        twilio_readiness_orchestration_service.queue_due_refreshes(db, now=now, limit=2)
        for _ in range(3)
    ]

    assert passes == [2, 1, 0]
    assert all(len(_readiness_jobs(db, organization.id)) == 1 for organization in organizations)


def test_readiness_probe_uses_a_bounded_twilio_client(toll_free_settings, monkeypatch) -> None:
    from twilio.base.exceptions import TwilioRestException

    from app.services import twilio_provider_service, twilio_transport

    calls: list[tuple[tuple, dict]] = []

    class _Accounts:
        def __call__(self, _sid):
            return self

        def fetch(self):
            raise TwilioRestException(503, "/accounts", msg="unavailable")

    def fake_client(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(api=SimpleNamespace(accounts=_Accounts()))

    monkeypatch.setattr(twilio_transport, "Client", fake_client)

    result = twilio_provider_service.test_configuration(toll_free_settings)

    assert result.valid is False
    assert len(calls) == 1
    http_client = calls[0][1]["http_client"]
    assert http_client.timeout == twilio_transport.TWILIO_REQUEST_TIMEOUT_SECONDS
    assert http_client.session.adapters["https://"].max_retries.total == 0


def test_refresh_skips_an_organization_deleted_after_its_check_was_queued(
    db, test_org, monkeypatch
) -> None:
    from app.services import twilio_provider_service, twilio_readiness_service

    settings = _persist_configured_settings(db, test_org.id)
    version = settings.current_version
    test_org.deleted_at = datetime.now(UTC)
    db.commit()

    def fail_probe(*_args, **_kwargs):
        raise AssertionError("Deleted organizations must not be probed")

    monkeypatch.setattr(twilio_provider_service, "test_configuration", fail_probe)

    persisted = twilio_readiness_service.refresh_readiness(
        db, organization_id=test_org.id, expected_settings_version=version
    )

    assert persisted is False


@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        pytest.param("ConnectTimeout", "twilio_timeout", id="timeout"),
        pytest.param("ConnectionError", "twilio_connection_failed", id="connection"),
    ],
)
def test_readiness_probe_sanitizes_transport_failures(
    toll_free_settings, monkeypatch, exception_type, expected_error
) -> None:
    from requests import exceptions as requests_exceptions

    from app.services import twilio_provider_service, twilio_transport

    # Requests errors quote the URL, which carries the Account SID.
    account_sid = "AC" + ("1" * 32)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"

    class _Accounts:
        def __call__(self, _sid):
            return self

        def fetch(self):
            raise getattr(requests_exceptions, exception_type)(
                f"Max retries exceeded with url: {url}"
            )

    monkeypatch.setattr(
        twilio_transport,
        "Client",
        lambda *_args, **_kwargs: SimpleNamespace(api=SimpleNamespace(accounts=_Accounts())),
    )

    result = twilio_provider_service.test_configuration(toll_free_settings)

    assert result.valid is False
    assert result.error == expected_error
    assert account_sid not in result.model_dump_json()
    assert "api.twilio.com" not in result.model_dump_json()


async def test_readiness_worker_persists_sanitized_provider_snapshot(
    authed_client,
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.core.config import settings as app_settings
    from app.jobs.handlers import twilio as twilio_job_handler
    from app.schemas.twilio import TwilioSettingsTestResponse
    from app.services import twilio_provider_service, twilio_settings_service

    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    monkeypatch.setattr(app_settings, "ATTACHMENT_SCAN_ENABLED", False)
    settings.enabled = True
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential("AC" + ("1" * 32))
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential("SK" + ("2" * 32))
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential("secret")
    settings.auth_token_encrypted = twilio_settings_service.encrypt_credential("auth-token")
    for route in settings.routes:
        route.enabled = True
        route.messaging_service_sid_encrypted = twilio_settings_service.encrypt_credential(
            "MG" + (("3" if route.purpose == "operational" else "4") * 32)
        )
        route.sender_phone_encrypted = twilio_settings_service.encrypt_credential("+14155550199")
        route.sender_phone_hash = "a" * 64
        route.sender_phone_last4 = "0199"
        route.a2p_status = "approved"
        route.advanced_opt_out_status = "verified"
    db.commit()
    monkeypatch.setattr(
        twilio_provider_service,
        "test_configuration",
        lambda *_args, **_kwargs: TwilioSettingsTestResponse(
            valid=True,
            account_status="active",
            twilio_edition=None,
            capabilities={
                "account_api": True,
                "messaging_services": True,
                "webhook_validation": True,
            },
            route_capabilities={
                purpose: {
                    "service_verified": True,
                    "sender_in_pool": True,
                    "sms": True,
                    "mms": True,
                    "a2p_status": "VERIFIED",
                    "inbound_webhook_matches": True,
                    "status_callback_matches": True,
                }
                for purpose in ("operational", "promotional")
            },
            error=None,
            warning=None,
        ),
    )
    job = SimpleNamespace(
        organization_id=test_org.id,
        job_scope="organization",
        payload={
            "provider_scope": "organization",
            "settings_version": settings.current_version,
        },
    )

    await twilio_job_handler.process_twilio_readiness_check(db, job)
    response = await authed_client.get("/twilio/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checked_at"] is not None
    assert payload["provider"]["credentials_valid"] is True
    assert payload["provider"]["account_status"] == "active"
    assert payload["provider"]["status"] == "ready"
    for purpose in ("operational", "promotional"):
        route = next(item for item in settings.routes if item.purpose == purpose)
        assert route.a2p_status == "approved"
        assert route.capability_evidence["provider"]["sender_in_pool"] is True
        assert route.capability_evidence["provider"]["account_active"] is True
        assert route.capability_evidence["provider"]["mms"] is True
    assert payload["overall_status"] == "blocked"
    assert {
        "legal_messaging_brand_missing",
        "operational_disclosure_missing",
        "promotional_disclosure_missing",
        "public_legal_urls_missing",
        "counsel_approval_missing",
        "messaging_dispatch_worker_disabled",
        "operational_consent_api_unavailable",
        "promotional_consent_api_unavailable",
    }.issubset({issue["code"] for issue in payload["issues"]})

    settings.legal_messaging_brand = "Example Agency"
    settings.operational_disclosure = "Operational disclosure"
    settings.promotional_disclosure = "Promotional disclosure"
    settings.sms_terms_url = "https://example.org/sms-terms"
    settings.privacy_policy_url = "https://example.org/privacy"
    settings.support_contact = "help@example.org"
    settings.expected_frequency = "Message frequency varies"
    settings.counsel_approved_at = datetime.now(UTC)
    for route in settings.routes:
        route.consent_management_status = "available"
        route.capability_evidence = {
            **(route.capability_evidence or {}),
            "sender_type": "10dlc",
            "mms": True,
            **({"meta_consent_mapping_verified": True} if route.purpose == "operational" else {}),
        }
    monkeypatch.setenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", "true")
    monkeypatch.setattr(app_settings, "ATTACHMENT_SCAN_ENABLED", True)
    db.commit()

    ready_response = await authed_client.get("/twilio/readiness")
    assert ready_response.status_code == 200
    assert ready_response.json()["overall_status"] == "ready"
    assert ready_response.json()["issues"] == []


async def test_settings_version_change_invalidates_cached_provider_readiness(
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.jobs.handlers import twilio as twilio_job_handler
    from app.schemas.twilio import TwilioSettingsTestResponse, TwilioSettingsUpdate
    from app.services import (
        twilio_provider_service,
        twilio_readiness_service,
        twilio_settings_service,
    )

    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential("AC" + ("1" * 32))
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential("SK" + ("2" * 32))
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential("secret")
    db.commit()
    monkeypatch.setattr(
        twilio_provider_service,
        "test_configuration",
        lambda *_args, **_kwargs: TwilioSettingsTestResponse(
            valid=True,
            account_status="active",
            twilio_edition=None,
            capabilities={
                "account_api": True,
                "messaging_services": True,
                "webhook_validation": False,
            },
            error=None,
            warning=None,
        ),
    )
    await twilio_job_handler.process_twilio_readiness_check(
        db,
        SimpleNamespace(
            organization_id=test_org.id,
            job_scope="organization",
            payload={
                "provider_scope": "organization",
                "settings_version": settings.current_version,
            },
        ),
    )
    assert twilio_readiness_service.get_readiness(db, test_org.id).checked_at is not None

    twilio_settings_service.update_settings(
        db,
        test_org.id,
        TwilioSettingsUpdate(
            expected_version=settings.current_version,
            legal_messaging_brand="Changed after provider probe",
        ),
    )

    readiness = twilio_readiness_service.get_readiness(db, test_org.id)
    assert readiness.checked_at is None
    assert readiness.provider.checked_at is None
    assert readiness.provider.credentials_valid is False


def _operational_gates(settings, **overrides):
    from app.services.twilio_readiness_service import build_readiness_gates, route_send_blockers

    route = _route_by_purpose(settings, "operational")
    kwargs = {
        "route_blockers": {"operational": route_send_blockers(settings, route)},
        "snapshot": {"credentials_valid": True},
        "credentials_valid": True,
        "account_status": "active",
    }
    kwargs.update(overrides)
    return {gate.key: gate for gate in build_readiness_gates(settings, **kwargs)}


def test_readiness_gates_mirror_toll_free_blockers(toll_free_settings):
    route = _route_by_purpose(toll_free_settings, "operational")
    route.sender_phone_last4 = "0199"

    gates = _operational_gates(toll_free_settings)

    assert list(gates) == [
        "messaging_enabled",
        "connection",
        "consent_record",
        "counsel_approval",
        "dispatch_worker",
        "operational_route",
        "operational_sender_registration",
        "operational_advanced_opt_out",
        "operational_consent_api",
        "operational_provider_evidence",
    ]
    assert gates["operational_consent_api"].status == "skipped"
    assert all(
        gate.status == "pass" for key, gate in gates.items() if key != "operational_consent_api"
    )
    assert gates["operational_sender_registration"].label == "Toll-free verification"
    assert gates["operational_route"].detail == "+1•••0199 · toll-free"
    assert gates["connection"].detail == "Account AC11...1111 is active."
    assert all(
        gate.route == "operational" for key, gate in gates.items() if key.startswith("operational_")
    )


@pytest.mark.parametrize("status", ["IN_REVIEW", "TWILIO_REJECTED"])
def test_readiness_gates_flag_unapproved_toll_free(toll_free_settings, status):
    route = _route_by_purpose(toll_free_settings, "operational")
    route.capability_evidence["provider"]["toll_free_verification_status"] = status

    gates = _operational_gates(toll_free_settings)

    assert gates["operational_sender_registration"].status == "fail"
    assert "TWILIO_APPROVED" in str(gates["operational_sender_registration"].detail)
    assert gates["operational_provider_evidence"].status == "pass"


def test_readiness_gates_pend_until_evidence_matches_the_settings_version(toll_free_settings):
    route = _route_by_purpose(toll_free_settings, "operational")
    route.capability_evidence["provider"]["settings_version"] = 0

    gates = _operational_gates(toll_free_settings, snapshot=None, credentials_valid=False)

    assert gates["connection"].status == "pending"
    assert gates["operational_sender_registration"].status == "pending"
    assert gates["operational_provider_evidence"].status == "pending"
    assert gates["operational_advanced_opt_out"].status == "pass"


def test_readiness_gates_flag_disabled_dispatch_worker(toll_free_settings, monkeypatch):
    monkeypatch.setenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", "false")

    gates = _operational_gates(toll_free_settings)

    assert gates["dispatch_worker"].status == "fail"
    assert gates["dispatch_worker"].detail == "The messaging dispatch worker is disabled."


def test_readiness_gates_use_a2p_and_consent_api_for_10dlc(toll_free_settings):
    route = _route_by_purpose(toll_free_settings, "operational")
    provider = route.capability_evidence["provider"]
    provider.update(
        {"sender_type": "10dlc", "a2p_status": "VERIFIED", "toll_free_verification_status": None}
    )
    route.consent_management_status = "unavailable"

    gates = _operational_gates(toll_free_settings)

    assert gates["operational_sender_registration"].label == "A2P campaign"
    assert gates["operational_sender_registration"].status == "pass"
    assert gates["operational_consent_api"].status == "fail"


def test_readiness_gates_include_an_enabled_but_unconfigured_promotional_route(toll_free_settings):
    _route_by_purpose(toll_free_settings, "promotional").enabled = True

    gates = _operational_gates(toll_free_settings)

    assert gates["promotional_route"].status == "fail"
    assert gates["promotional_route"].route == "promotional"
    assert "promotional_sender_registration" not in gates
