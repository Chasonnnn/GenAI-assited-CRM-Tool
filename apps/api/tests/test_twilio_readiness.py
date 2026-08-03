"""Cache-only readiness contracts for organization Twilio messaging."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.db.enums import JobType
from app.db.models import Job


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
                "issues": ["Messaging Service and sender are not configured."],
            },
            "promotional": {
                "status": "not_configured",
                "can_send_sms": False,
                "can_send_mms": False,
                "can_receive": False,
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
        "promotional_route_missing",
    }


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
    assert payload["overall_status"] == "blocked"
    assert {
        "legal_messaging_brand_missing",
        "messaging_disclosures_missing",
        "public_legal_urls_missing",
        "counsel_approval_missing",
        "messaging_dispatch_worker_disabled",
        "media_scanning_disabled",
        "operational_consent_api_unavailable",
        "promotional_consent_api_unavailable",
        "operational_sender_not_10dlc",
        "promotional_sender_not_10dlc",
        "operational_mms_unverified",
        "promotional_mms_unverified",
        "meta_consent_mapping_unverified",
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
            **(
                {"meta_consent_mapping_verified": True}
                if route.purpose == "operational"
                else {}
            ),
        }
    monkeypatch.setenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", "true")
    monkeypatch.setattr(app_settings, "ATTACHMENT_SCAN_ENABLED", True)
    db.commit()

    ready_response = await authed_client.get("/twilio/readiness")
    assert ready_response.status_code == 200
    assert ready_response.json()["overall_status"] == "ready"
    assert ready_response.json()["issues"] == []
