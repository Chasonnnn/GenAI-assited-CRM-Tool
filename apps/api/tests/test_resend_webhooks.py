"""Tests for Resend webhook handler."""

import base64
import hashlib
import hmac
import time
import uuid

import pytest


def _generate_svix_signature(body: bytes, secret: str, timestamp: str) -> str:
    """Generate a valid Svix signature for testing."""
    msg_id = str(uuid.uuid4())
    signed_payload = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"

    def _pad_b64(value: str) -> str:
        return value + "=" * (-len(value) % 4)

    # Handle whsec_ prefix (Svix uses base64 urlsafe)
    if secret.startswith("whsec_"):
        secret = secret[6:]
        try:
            secret_bytes = base64.urlsafe_b64decode(_pad_b64(secret))
        except Exception:
            secret_bytes = secret.encode("utf-8")
    else:
        try:
            secret_bytes = base64.b64decode(secret)
        except Exception:
            secret_bytes = secret.encode("utf-8")

    signature = hmac.new(
        secret_bytes,
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return msg_id, f"v1,{signature_b64}"


class TestResendWebhookSignature:
    """Test signature verification."""

    def test_verify_svix_signature_valid(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        secret = "test_secret_key_for_testing"
        timestamp = str(int(time.time()))

        msg_id, signature = _generate_svix_signature(body, secret, timestamp)

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": signature,
        }

        is_valid = _verify_svix_signature(body, headers, secret)
        assert is_valid is True

    def test_verify_svix_signature_invalid(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        timestamp = str(int(time.time()))

        headers = {
            "svix-id": str(uuid.uuid4()),
            "svix-timestamp": timestamp,
            "svix-signature": "v1,invalid_signature",
        }

        is_valid = _verify_svix_signature(body, headers, "correct_secret")
        assert is_valid is False

    def test_verify_svix_signature_missing_headers(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'

        # Missing svix-id
        headers = {
            "svix-timestamp": str(int(time.time())),
            "svix-signature": "v1,signature",
        }

        is_valid = _verify_svix_signature(body, headers, "secret")
        assert is_valid is False

    def test_verify_svix_signature_rejects_stale_timestamp(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        secret = "test_secret_key_for_testing"
        stale_timestamp = str(int(time.time()) - 3600)

        msg_id, signature = _generate_svix_signature(body, secret, stale_timestamp)

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": stale_timestamp,
            "svix-signature": signature,
        }

        is_valid = _verify_svix_signature(body, headers, secret)
        assert is_valid is False

    def test_verify_svix_signature_rejects_malformed_whsec_secret(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        malformed_secret = "whsec_invalid@secret!!"
        timestamp = str(int(time.time()))
        msg_id = str(uuid.uuid4())

        # Signature generated with raw malformed secret bytes (legacy/fail-open behavior).
        signed_payload = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"
        raw_secret_bytes = malformed_secret.removeprefix("whsec_").encode("utf-8")
        signature = base64.b64encode(
            hmac.new(
                raw_secret_bytes,
                signed_payload.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": f"v1,{signature}",
        }

        is_valid = _verify_svix_signature(body, headers, malformed_secret)
        assert is_valid is False


class TestResendWebhookHandler:
    """Test webhook event processing."""

    @pytest.fixture
    def setup_email_log(self, db, test_org):
        """Create an EmailLog for testing webhook events."""
        import base64

        from app.db.models import EmailLog
        from app.db.enums import EmailStatus
        from app.services import resend_settings_service

        # Create Resend settings
        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )
        webhook_secret_bytes = b"test_webhook_secret_for_resend"
        webhook_secret = "whsec_" + base64.urlsafe_b64encode(webhook_secret_bytes).decode(
            "utf-8"
        ).rstrip("=")
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_org.id,
            email_provider="resend",
            api_key="re_test_key",
            from_email="no-reply@example.com",
            verified_domain="example.com",
            webhook_signing_secret=webhook_secret,
        )

        db.refresh(settings)

        # Create an EmailLog
        email_log = EmailLog(
            organization_id=test_org.id,
            recipient_email="test@recipient.com",
            subject="Test Email",
            body="<p>Test body</p>",
            status=EmailStatus.SENT.value,
            external_id="resend_msg_123",  # Resend message ID
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)

        return email_log, settings, webhook_secret

    @pytest.mark.asyncio
    async def test_webhook_unknown_webhook_id(self, db, test_org, client):
        """Test that unknown webhook IDs are silently accepted."""
        from app.services import resend_settings_service

        # Create settings to ensure they exist
        resend_settings_service.get_or_create_resend_settings(db, test_org.id, test_org.id)

        payload = {"type": "email.delivered", "data": {"email_id": "msg_123"}}

        response = await client.post(
            "/webhooks/resend/invalid-webhook-id",
            json=payload,
        )

        # Should return 200 even for invalid webhook ID
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_webhook_delivered_event(self, db, test_org, client, setup_email_log):
        """Test that delivered events update EmailLog."""
        import json

        email_log, settings, webhook_secret = setup_email_log

        payload = {
            "type": "email.delivered",
            "data": {"email_id": email_log.external_id},
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        # Refresh and check status
        db.refresh(email_log)
        assert email_log.resend_status == "delivered"
        assert email_log.delivered_at is not None

    @pytest.mark.asyncio
    async def test_webhook_rejects_missing_signature_when_secret_configured(
        self, db, test_org, client, setup_email_log
    ):
        """If a signing secret is configured, requests without Svix headers must be rejected."""
        import json

        email_log, settings, _webhook_secret = setup_email_log

        payload = {
            "type": "email.delivered",
            "data": {"email_id": email_log.external_id},
        }
        body = json.dumps(payload).encode("utf-8")

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_delivered_updates_campaign_run_counts(
        self, db, test_org, test_user, client, setup_email_log
    ):
        """Delivered webhook should update campaign recipient + run delivered_count."""
        import json
        from uuid import uuid4

        from app.db.models import Campaign, CampaignRun, CampaignRecipient, EmailTemplate

        email_log, settings, webhook_secret = setup_email_log

        template = EmailTemplate(
            id=uuid4(),
            organization_id=test_org.id,
            name="Webhook Campaign Template",
            subject="Hello",
            body="<p>Test body</p>",
            is_active=True,
        )
        db.add(template)
        db.flush()

        campaign = Campaign(
            id=uuid4(),
            organization_id=test_org.id,
            name="Webhook Campaign",
            email_template_id=template.id,
            recipient_type="case",
            filter_criteria={},
            status="sending",
            created_by_user_id=test_user.id,
        )
        db.add(campaign)
        db.flush()

        run = CampaignRun(
            id=uuid4(),
            organization_id=test_org.id,
            campaign_id=campaign.id,
            status="running",
            total_count=1,
            sent_count=1,
            failed_count=0,
            skipped_count=0,
            opened_count=0,
            clicked_count=0,
        )
        db.add(run)
        db.flush()

        recipient = CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email="test@recipient.com",
            status="sent",
            external_message_id=str(email_log.id),
        )
        db.add(recipient)
        db.commit()

        payload = {
            "type": "email.delivered",
            "data": {"email_id": email_log.external_id},
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        db.refresh(recipient)
        db.refresh(run)
        assert recipient.status == "delivered"
        assert run.delivered_count == 1
        assert run.sent_count == 1

    @pytest.mark.asyncio
    async def test_webhook_bounced_hard_adds_suppression(
        self, db, test_org, client, setup_email_log
    ):
        """Test that hard bounces add email to suppression list."""
        import json
        from app.db.models import EmailSuppression

        email_log, settings, webhook_secret = setup_email_log

        payload = {
            "type": "email.bounced",
            "data": {
                "email_id": email_log.external_id,
                "bounce": {"type": "hard"},
            },
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        # Check suppression was added
        suppression = (
            db.query(EmailSuppression)
            .filter(
                EmailSuppression.organization_id == test_org.id,
                EmailSuppression.email == email_log.recipient_email.lower(),
            )
            .first()
        )
        assert suppression is not None
        assert suppression.reason == "bounced"

    @pytest.mark.asyncio
    async def test_webhook_complained_adds_suppression(self, db, test_org, client, setup_email_log):
        """Test that complaints add email to suppression list."""
        import json
        from app.db.models import EmailSuppression

        email_log, settings, webhook_secret = setup_email_log

        payload = {
            "type": "email.complained",
            "data": {"email_id": email_log.external_id},
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        # Check suppression was added
        suppression = (
            db.query(EmailSuppression)
            .filter(
                EmailSuppression.organization_id == test_org.id,
                EmailSuppression.email == email_log.recipient_email.lower(),
            )
            .first()
        )
        assert suppression is not None
        assert suppression.reason == "complaint"

    @pytest.mark.asyncio
    async def test_webhook_no_email_log_found(self, db, test_org, client):
        """Test that webhook handles missing EmailLog gracefully."""
        from app.services import resend_settings_service

        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )

        payload = {
            "type": "email.delivered",
            "data": {"email_id": "nonexistent_msg_id"},
        }

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            json=payload,
        )

        # Should return 200 even if EmailLog not found
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCampaignRunProviderLock:
    """Test that email provider is locked on CampaignRun creation."""

    def test_enqueue_campaign_locks_provider(self, db, test_org, test_user):
        """Test that enqueue_campaign_send locks the email provider on the run."""
        from app.db.models import Campaign, CampaignRun, EmailTemplate
        from app.db.enums import CampaignStatus
        from app.services import campaign_service, resend_settings_service

        # Setup: Create Resend settings
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_user.id,
            email_provider="resend",
            api_key="re_test_key",
            from_email="no-reply@example.com",
            verified_domain="example.com",
        )

        # Create template
        template = EmailTemplate(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            name="Test Template",
            subject="Test",
            body="<p>Test</p>",
            is_active=True,
        )
        db.add(template)
        db.flush()

        # Create campaign
        campaign = Campaign(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            email_template_id=template.id,
            name="Test Campaign",
            recipient_type="case",
            status=CampaignStatus.DRAFT.value,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        # Enqueue the campaign
        message, run_id, _ = campaign_service.enqueue_campaign_send(
            db, test_org.id, campaign.id, test_user.id, send_now=True
        )

        # Check that provider was locked on the run
        run = db.query(CampaignRun).filter(CampaignRun.id == run_id).first()
        assert run is not None
        assert run.email_provider == "resend"

    def test_enqueue_campaign_fails_without_provider(self, db, test_org, test_user):
        """Test that enqueue fails if email provider not configured."""
        from app.db.models import Campaign, EmailTemplate
        from app.db.enums import CampaignStatus
        from app.services import campaign_service, resend_settings_service

        # Create settings without provider
        resend_settings_service.get_or_create_resend_settings(db, test_org.id, test_user.id)

        # Create template and campaign
        template = EmailTemplate(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            name="Test Template 2",
            subject="Test",
            body="<p>Test</p>",
            is_active=True,
        )
        db.add(template)
        db.flush()

        campaign = Campaign(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            email_template_id=template.id,
            name="Test Campaign 2",
            recipient_type="case",
            status=CampaignStatus.DRAFT.value,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        # Should fail because no provider configured
        with pytest.raises(ValueError) as exc:
            campaign_service.enqueue_campaign_send(
                db, test_org.id, campaign.id, test_user.id, send_now=True
            )

        assert "not configured" in str(exc.value).lower()
