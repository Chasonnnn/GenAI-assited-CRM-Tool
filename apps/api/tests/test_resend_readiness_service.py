"""Behavioral contracts for live, read-only Resend readiness probes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.db.models import (
    PlatformEmailTemplate,
    PlatformSystemEmailTemplate,
    ResendSettings,
)
from app.services import (
    resend_control_plane,
    resend_event_contract,
    resend_readiness_snapshot_service,
    resend_settings_service,
)


@dataclass
class _FakeControlPlaneClient:
    domain_list_result: resend_control_plane.ResendControlPlaneResult
    domain_results: dict[str, resend_control_plane.ResendControlPlaneResult]
    webhook_result: resend_control_plane.ResendControlPlaneResult
    init_kwargs: dict[str, object] = field(default_factory=dict)
    requested_domain_ids: list[str] = field(default_factory=list)
    expected_webhook_endpoints: list[str] = field(default_factory=list)
    before_list_domains: Callable[[], None] | None = None

    async def list_domains(self):
        if self.before_list_domains is not None:
            self.before_list_domains()
        return self.domain_list_result

    async def get_domain(self, domain_id: str):
        self.requested_domain_ids.append(domain_id)
        return self.domain_results[domain_id]

    async def list_webhooks(self, *, expected_endpoint: str):
        self.expected_webhook_endpoints.append(expected_endpoint)
        return self.webhook_result


def _client_factory(client: _FakeControlPlaneClient):
    def factory(**kwargs):
        client.init_kwargs = kwargs
        return client

    return factory


def _domain(
    *,
    name: str,
    status: str = "verified",
    sending: str = "enabled",
    receiving: str = "disabled",
    open_tracking: bool = True,
    click_tracking: bool = True,
    spf_status: str = "verified",
    dkim_status: str = "verified",
) -> tuple[
    resend_control_plane.ResendDomainState,
    resend_control_plane.ResendDomainDetailState,
]:
    domain_id = str(uuid4())
    return (
        resend_control_plane.ResendDomainState(
            id=domain_id,
            name=name,
            status=status,
            sending=sending,
            receiving=receiving,
        ),
        resend_control_plane.ResendDomainDetailState(
            id=domain_id,
            name=name,
            status=status,
            sending=sending,
            receiving=receiving,
            open_tracking=open_tracking,
            click_tracking=click_tracking,
            spf_status=spf_status,
            dkim_status=dkim_status,
        ),
    )


def _webhook(
    *,
    status: str = "enabled",
    endpoint_matches: bool = True,
    events: tuple[str, ...] | None = None,
) -> resend_control_plane.ResendWebhookState:
    return resend_control_plane.ResendWebhookState(
        id=str(uuid4()),
        status=status,
        endpoint_matches=endpoint_matches,
        events=events or tuple(sorted(resend_event_contract.RESEND_OUTBOUND_READINESS_EVENT_TYPES)),
    )


def _configure_org_resend(db, organization_id: UUID, *, domain: str = "mail.example.com"):
    settings_row = ResendSettings(
        organization_id=organization_id,
        email_provider="resend",
        api_key_encrypted=resend_settings_service.encrypt_api_key("re_org_readiness"),
        from_email=f"ops@{domain}",
        verified_domain=domain,
        webhook_id=str(uuid4()),
        webhook_secret_encrypted=resend_settings_service.encrypt_api_key("whsec_org_readiness"),
    )
    db.add(settings_row)
    db.flush()
    return settings_row


@pytest.mark.asyncio
async def test_verified_org_route_persists_ready_capabilities(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    configured = _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(name="mail.example.com")
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.persisted is True
    assert refresh.probe.overall_status == "ready"
    assert refresh.probe.domain_status == "ready"
    assert refresh.probe.sending_status == "ready"
    assert refresh.probe.webhook_status == "ready"
    assert refresh.probe.delivery_tracking_status == "ready"
    assert refresh.probe.engagement_tracking_status == "ready"
    assert refresh.probe.verified_domain_count == 1
    assert refresh.probe.enabled_webhook_count == 1
    assert refresh.probe.issue_codes == ()
    assert refresh.retry_after_seconds is None
    assert client.init_kwargs["provider_account_id"] == f"organization:{test_org.id}"
    assert client.init_kwargs["api_key"] == "re_org_readiness"
    assert client.expected_webhook_endpoints == [
        f"https://api.surrogacyforce.test/webhooks/resend/{configured.webhook_id}"
    ]

    snapshot = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint=refresh.probe.config_fingerprint,
        now=refresh.probe.checked_at,
    )
    assert snapshot.overall_status == "ready"


@pytest.mark.asyncio
async def test_partial_receiving_state_does_not_block_valid_sending(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(
        name="mail.example.com",
        status="partially_verified",
        receiving="disabled",
    )
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.domain_status == "ready"
    assert refresh.probe.sending_status == "ready"
    assert refresh.probe.overall_status == "ready"


@pytest.mark.asyncio
async def test_missing_configured_domain_is_actionable_without_probing_another_domain(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id, domain="configured.example.com")
    other_domain, other_detail = _domain(name="other.example.com")
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(other_domain,),
        ),
        domain_results={
            other_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=other_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.domain_status == "needs_attention"
    assert refresh.probe.sending_status == "needs_attention"
    assert refresh.probe.issue_codes == ("domain_not_verified",)
    assert client.requested_domain_ids == []


@pytest.mark.asyncio
async def test_verified_domain_with_sending_disabled_is_not_send_ready(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(
        name="mail.example.com",
        sending="disabled",
    )
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.domain_status == "ready"
    assert refresh.probe.sending_status == "needs_attention"
    assert refresh.probe.issue_codes == ("sending_disabled",)


@pytest.mark.asyncio
async def test_from_address_must_use_the_configured_domain(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    configured = _configure_org_resend(db, test_org.id)
    configured.from_email = "ops@different.example.com"
    db.flush()
    listed_domain, domain_detail = _domain(name="mail.example.com")
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.domain_status == "ready"
    assert refresh.probe.sending_status == "needs_attention"
    assert refresh.probe.issue_codes == ("sending_disabled",)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("webhooks", "expected_issue"),
    [
        ((), "webhook_missing"),
        ((_webhook(status="disabled"),), "webhook_disabled"),
        ((_webhook(endpoint_matches=False),), "webhook_missing"),
    ],
    ids=("missing", "disabled", "endpoint-mismatch"),
)
async def test_webhook_must_be_enabled_and_match_the_exact_local_route(
    db,
    test_org,
    monkeypatch,
    webhooks,
    expected_issue,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(name="mail.example.com")
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=webhooks,
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.webhook_status == "needs_attention"
    assert refresh.probe.delivery_tracking_status == "needs_attention"
    assert refresh.probe.engagement_tracking_status == "needs_attention"
    assert refresh.probe.issue_codes == (expected_issue,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("missing_event", "expected_delivery", "expected_engagement", "expected_issue"),
    [
        ("email.bounced", "needs_attention", "ready", "delivery_events_missing"),
        ("email.clicked", "ready", "needs_attention", "engagement_events_missing"),
    ],
    ids=("delivery-event", "engagement-event"),
)
async def test_delivery_and_engagement_webhook_event_coverage_are_independent(
    db,
    test_org,
    monkeypatch,
    missing_event,
    expected_delivery,
    expected_engagement,
    expected_issue,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(name="mail.example.com")
    events = tuple(
        sorted(resend_event_contract.RESEND_OUTBOUND_READINESS_EVENT_TYPES - {missing_event})
    )
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(events=events),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.delivery_tracking_status == expected_delivery
    assert refresh.probe.engagement_tracking_status == expected_engagement
    assert refresh.probe.issue_codes == (expected_issue,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("open_tracking", "click_tracking"),
    [(False, True), (True, False)],
    ids=("open-disabled", "click-disabled"),
)
async def test_domain_engagement_tracking_must_enable_open_and_click(
    db,
    test_org,
    monkeypatch,
    open_tracking,
    click_tracking,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(
        name="mail.example.com",
        open_tracking=open_tracking,
        click_tracking=click_tracking,
    )
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.delivery_tracking_status == "ready"
    assert refresh.probe.engagement_tracking_status == "needs_attention"
    assert refresh.probe.issue_codes == ("engagement_events_missing",)


@pytest.mark.asyncio
async def test_tracking_needs_a_local_signing_secret_even_when_remote_webhook_is_ready(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    configured = _configure_org_resend(db, test_org.id)
    configured.webhook_secret_encrypted = None
    db.flush()
    listed_domain, domain_detail = _domain(name="mail.example.com")
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.webhook_status == "ready"
    assert refresh.probe.delivery_tracking_status == "needs_attention"
    assert refresh.probe.engagement_tracking_status == "needs_attention"
    assert refresh.probe.issue_codes == ("webhook_missing",)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "provider_result",
        "expected_probe_status",
        "expected_overall",
        "expected_capability",
        "expected_issue",
        "expected_retry_after",
    ),
    [
        (
            resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.LIMITED
            ),
            "limited",
            "limited",
            "limited",
            "limited_visibility",
            None,
        ),
        (
            resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.FAIL
            ),
            "failed",
            "needs_attention",
            "unknown",
            "credential_rejected",
            None,
        ),
        (
            resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.UNKNOWN,
                reason=resend_control_plane.ResendControlPlaneReason.TIMEOUT,
            ),
            "failed",
            "unknown",
            "unknown",
            "timeout",
            None,
        ),
        (
            resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.UNKNOWN,
                provider_status_code=429,
                retry_after_seconds=23,
            ),
            "failed",
            "unknown",
            "unknown",
            "provider_unavailable",
            23,
        ),
    ],
    ids=("restricted", "invalid", "timeout", "rate-limited"),
)
async def test_provider_access_outcomes_are_controlled_and_persisted(
    db,
    test_org,
    monkeypatch,
    provider_result,
    expected_probe_status,
    expected_overall,
    expected_capability,
    expected_issue,
    expected_retry_after,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id)
    client = _FakeControlPlaneClient(
        domain_list_result=provider_result,
        domain_results={},
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.UNKNOWN,
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.persisted is True
    assert refresh.probe.probe_status == expected_probe_status
    assert refresh.probe.overall_status == expected_overall
    assert refresh.probe.domain_status == expected_capability
    assert refresh.probe.webhook_status == expected_capability
    assert refresh.probe.sending_status == expected_capability
    assert refresh.probe.delivery_tracking_status == expected_capability
    assert refresh.probe.engagement_tracking_status == expected_capability
    assert refresh.probe.issue_codes == (expected_issue,)
    assert refresh.retry_after_seconds == expected_retry_after
    assert client.expected_webhook_endpoints == []


@pytest.mark.asyncio
async def test_platform_probe_checks_every_distinct_effective_template_domain(
    db,
    monkeypatch,
):
    from pydantic import SecretStr

    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    monkeypatch.setattr(settings, "PLATFORM_RESEND_API_KEY", SecretStr("re_platform"))
    monkeypatch.setattr(
        settings,
        "PLATFORM_RESEND_WEBHOOK_SECRET",
        SecretStr("whsec_platform"),
    )
    monkeypatch.setattr(
        settings,
        "PLATFORM_EMAIL_FROM",
        "SurrogacyForce <hello@fallback.example.com>",
    )
    db.add_all(
        [
            PlatformSystemEmailTemplate(
                system_key="readiness-system-explicit",
                name="Explicit system",
                subject="Subject",
                body="<p>Body</p>",
                from_email="system@system.example.com",
                is_active=True,
            ),
            PlatformSystemEmailTemplate(
                system_key="readiness-system-fallback",
                name="Fallback system",
                subject="Subject",
                body="<p>Body</p>",
                from_email=None,
                is_active=True,
            ),
            PlatformSystemEmailTemplate(
                system_key="readiness-system-inactive",
                name="Inactive system",
                subject="Subject",
                body="<p>Body</p>",
                from_email="ignore@inactive.example.com",
                is_active=False,
            ),
            PlatformEmailTemplate(
                name="Published campaign",
                subject="Subject",
                body="<p>Draft</p>",
                published_name="Published campaign",
                published_subject="Published subject",
                published_body="<p>Published</p>",
                published_from_email="campaign@campaign.example.com",
                published_version=1,
                status="published",
            ),
            PlatformEmailTemplate(
                name="Published fallback",
                subject="Subject",
                body="<p>Draft</p>",
                published_name="Published fallback",
                published_subject="Published subject",
                published_body="<p>Published</p>",
                published_from_email=None,
                published_version=1,
                status="published",
            ),
            PlatformEmailTemplate(
                name="Draft only",
                subject="Subject",
                body="<p>Draft</p>",
                from_email="ignore@draft.example.com",
                published_version=0,
                status="draft",
            ),
        ]
    )
    db.flush()

    domain_pairs = [
        _domain(name="campaign.example.com"),
        _domain(name="fallback.example.com"),
        _domain(name="system.example.com"),
    ]
    listed_domains = tuple(pair[0] for pair in domain_pairs)
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=listed_domains,
        ),
        domain_results={
            listed.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=detail,
            )
            for listed, detail in domain_pairs
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_platform_readiness(
        db,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.persisted is True
    assert refresh.probe.overall_status == "ready"
    assert refresh.probe.verified_domain_count == 3
    assert set(client.requested_domain_ids) == {listed.id for listed in listed_domains}
    assert client.init_kwargs["provider_account_id"] == "platform:default"
    assert client.init_kwargs["api_key"] == "re_platform"
    assert client.expected_webhook_endpoints == [
        "https://api.surrogacyforce.test/webhooks/resend/platform"
    ]

    snapshot = resend_readiness_snapshot_service.get_platform_snapshot(
        db,
        current_config_fingerprint=refresh.probe.config_fingerprint,
        now=refresh.probe.checked_at,
    )
    assert snapshot.overall_status == "ready"


@pytest.mark.asyncio
async def test_organization_probe_never_reads_or_writes_another_org_route(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.db.models import Organization, ResendReadinessSnapshot
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    _configure_org_resend(db, test_org.id, domain="target.example.com")
    other_org = Organization(
        id=uuid4(),
        name="Other readiness organization",
        slug=f"other-readiness-{uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    _configure_org_resend(
        db, other_org.id, domain="other.example.com"
    ).api_key_encrypted = resend_settings_service.encrypt_api_key("re_other_org")
    db.flush()

    listed_domain, domain_detail = _domain(name="target.example.com")
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert client.init_kwargs["api_key"] == "re_org_readiness"
    snapshots = db.query(ResendReadinessSnapshot).all()
    assert len(snapshots) == 1
    assert snapshots[0].organization_id == test_org.id
    assert snapshots[0].provider_account_id == f"organization:{test_org.id}"
    other_view = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=other_org.id,
        current_config_fingerprint=refresh.probe.config_fingerprint,
        now=refresh.probe.checked_at,
    )
    assert other_view.freshness == "never_checked"


@pytest.mark.asyncio
async def test_configuration_change_during_provider_io_discards_the_probe(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.db.models import ResendReadinessSnapshot
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.surrogacyforce.test")
    configured = _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(name="mail.example.com")

    def rotate_sender_configuration() -> None:
        configured.from_email = "ops@rotated.example.com"
        configured.verified_domain = "rotated.example.com"
        db.flush()

    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(_webhook(),),
        ),
        before_list_domains=rotate_sender_configuration,
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert len(refresh.probe.config_fingerprint) == 64
    assert refresh.persisted is False
    assert db.query(ResendReadinessSnapshot).count() == 0


@pytest.mark.asyncio
async def test_org_without_resend_configuration_is_persisted_without_provider_io(
    db,
    test_org,
):
    from app.services import resend_readiness_service

    def forbidden_client_factory(**_kwargs):
        raise AssertionError("provider I/O must not run for an unconfigured route")

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=forbidden_client_factory,
    )

    assert refresh.persisted is True
    assert refresh.probe.probe_status == "succeeded"
    assert refresh.probe.overall_status == "not_configured"
    assert refresh.probe.domain_status == "not_configured"
    assert refresh.probe.webhook_status == "not_configured"
    assert refresh.probe.sending_status == "not_configured"
    assert refresh.probe.delivery_tracking_status == "not_configured"
    assert refresh.probe.engagement_tracking_status == "not_configured"
    assert refresh.probe.issue_codes == ()


@pytest.mark.asyncio
async def test_selected_resend_route_without_a_usable_key_fails_before_provider_io(
    db,
    test_org,
):
    from app.services import resend_readiness_service

    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=None,
            from_email="ops@example.com",
            verified_domain="example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()

    def forbidden_client_factory(**_kwargs):
        raise AssertionError("provider I/O must not run without a credential")

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=forbidden_client_factory,
    )

    assert refresh.persisted is True
    assert refresh.probe.probe_status == "failed"
    assert refresh.probe.overall_status == "needs_attention"
    assert refresh.probe.issue_codes == ("credential_unavailable",)


@pytest.mark.asyncio
async def test_missing_local_webhook_url_does_not_issue_an_invalid_remote_request(
    db,
    test_org,
    monkeypatch,
):
    from app.core.config import settings
    from app.services import resend_readiness_service

    monkeypatch.setattr(settings, "API_BASE_URL", "")
    monkeypatch.setattr(settings, "FRONTEND_URL", "")
    _configure_org_resend(db, test_org.id)
    listed_domain, domain_detail = _domain(name="mail.example.com")
    client = _FakeControlPlaneClient(
        domain_list_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.OK,
            value=(listed_domain,),
        ),
        domain_results={
            listed_domain.id: resend_control_plane.ResendControlPlaneResult(
                status=resend_control_plane.ResendControlPlaneStatus.OK,
                value=domain_detail,
            )
        },
        webhook_result=resend_control_plane.ResendControlPlaneResult(
            status=resend_control_plane.ResendControlPlaneStatus.FAIL,
        ),
    )

    refresh = await resend_readiness_service.refresh_organization_readiness(
        db,
        organization_id=test_org.id,
        control_plane_client_factory=_client_factory(client),
    )

    assert refresh.probe.sending_status == "ready"
    assert refresh.probe.webhook_status == "needs_attention"
    assert refresh.probe.issue_codes == ("webhook_missing",)
    assert client.expected_webhook_endpoints == []
